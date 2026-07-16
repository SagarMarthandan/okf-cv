"""
zvec_hybrid_search.py — Hybrid Portfolio Search (OKF Phrase Matching + Zvec Semantic Embeddings).

Combines the precision of OKF's 4-layer phrase matching with the semantic recall
of Zvec's sentence embeddings. Runs both engines, fuses scores, and returns the
best-ranked projects.

Score fusion:
  final_score = (okf_score * OKF_WEIGHT) + (zvec_sim * ZVEC_WEIGHT)
  Defaults: OKF_WEIGHT=0.6, ZVEC_WEIGHT=0.4

The OKF component provides:
  - Exact phrase matching, synonym expansion, light stemming, fuzzy typo tolerance
  - Archetype-boosted scoring (+10 primary, +5 secondary)
  - Jaccard-style normalization
  - Full match diagnostics (explainability)

The Zvec component provides:
  - Semantic similarity via all-MiniLM-L6-v2 sentence embeddings
  - Catches conceptual matches OKF can't see (e.g., "event streaming" → Kafka)
  - Persistent vector database under okf/zvec_db/

Usage:
  python zvec_hybrid_search.py <job_description_path> <output_project_info_path> [ats_report_path] [top_k]
"""
import os
import re
import sys
import json
import shutil
import hashlib
import socket
import subprocess
import threading
import time
import tempfile
from typing import List, Dict, Set, Tuple, Optional
from contextlib import contextmanager

import yaml

from config import DEFAULT_PORTFOLIO_DIR, SKILL_DIR, ZVEC_DB_PATH, EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION, HYBRID_OKF_WEIGHT, HYBRID_ZVEC_WEIGHT
from okf_portfolio_search import (
    search_relevant_projects,
    distill_project,
    parse_okf_file,
    load_jd_archetype,
    tokenize,
)

# ─── Config ───────────────────────────────────────────────────────────────────

# Config values imported from config.py: ZVEC_DB_PATH, EMBEDDING_MODEL_NAME,
# EMBEDDING_DIMENSION, HYBRID_OKF_WEIGHT, HYBRID_ZVEC_WEIGHT

# ─── Cross-process file lock ──────────────────────────────────────────────────
# Prevents concurrent Zvec DB access when multiple agents run the pipeline in parallel.

_ZVEC_LOCK_PATH = os.path.join(os.path.dirname(ZVEC_DB_PATH), "zvec_db.lock")
_ZVEC_LOCK_TIMEOUT = None  # None = wait indefinitely until the lock is released
_ZVEC_LOCK_RETRY_INTERVAL = 2.0  # seconds between retry attempts (relaxed polling)


@contextmanager
def zvec_db_lock(timeout: float = _ZVEC_LOCK_TIMEOUT):
    """Acquire an exclusive cross-process lock for Zvec DB operations.

    Uses a lock file with OS-level locking (msvcrt on Windows, fcntl on Unix).
    Other processes will wait until the lock is released, then proceed.
    """
    os.makedirs(os.path.dirname(_ZVEC_LOCK_PATH), exist_ok=True)
    lock_fd = open(_ZVEC_LOCK_PATH, 'w')
    acquired = False
    logged = False
    try:
        deadline = time.time() + timeout if timeout is not None else None
        while True:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (OSError, IOError):
                if deadline is not None and time.time() >= deadline:
                    print(f"Warning: Zvec DB lock timeout after {timeout}s. Proceeding without lock (risk of concurrent access).")
                    break
                if not logged:
                    print("Zvec DB busy (another agent is using it). Waiting for lock...")
                    logged = True
                time.sleep(_ZVEC_LOCK_RETRY_INTERVAL)
        yield
    finally:
        if acquired:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except (OSError, IOError):
                pass
        lock_fd.close()

# ─── Zvec imports (lazy) ──────────────────────────────────────────────────────

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

_model_instance = None
_model_lock = threading.Lock()
_zvec = None


def _get_zvec():
    """Lazy import zvec."""
    global _zvec
    if _zvec is None:
        import zvec as _z
        _zvec = _z
    return _zvec

def _get_model():
    """Thread-safe lazy initialization of SentenceTransformer model (fallback only).

    Used when the embedding daemon is not available. If the daemon is running,
    get_embedding / get_embeddings_batch route through it instead and never
    call this function.
    """
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                from sentence_transformers import SentenceTransformer
                print(f"Loading SentenceTransformer model '{EMBEDDING_MODEL_NAME}'...")
                _model_instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_instance


# ─── Embedding daemon client ──────────────────────────────────────────────────
# Tries to use a local embedding_server.py daemon (holds the model in memory,
# eliminating ~21s model load per process). Falls back to direct _get_model()
# if the daemon is unavailable — the pipeline still works, just slower.

_DAEMON_STATE_FILE = os.path.join(SKILL_DIR, "okf", ".embedding_server.json")
_DAEMON_LOG_FILE = os.path.join(SKILL_DIR, "okf", ".embedding_server.log")
_daemon_status = "unknown"  # "unknown" | "available" | "unavailable"


def _read_daemon_state():
    """Read the daemon state file. Returns dict with port/pid or None."""
    try:
        with open(_DAEMON_STATE_FILE, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _daemon_request(req: dict, timeout: float = 120) -> Optional[dict]:
    """Send one JSON-line request to the daemon. Returns response dict or None."""
    state = _read_daemon_state()
    if state is None:
        return None
    port = state.get("port")
    if not port:
        return None
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.sendall((json.dumps(req) + "\n").encode('utf-8'))
            data = b""
            while b"\n" not in data:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
            return json.loads(data.decode('utf-8'))
    except (ConnectionRefusedError, socket.timeout, OSError, json.JSONDecodeError):
        return None


def _start_daemon() -> bool:
    """Start the embedding daemon in a detached background process."""
    server_path = os.path.join(SKILL_DIR, "embedding_server.py")
    if not os.path.exists(server_path):
        return False
    os.makedirs(os.path.dirname(_DAEMON_LOG_FILE), exist_ok=True)
    try:
        log_fd = open(_DAEMON_LOG_FILE, 'a')
        if sys.platform == 'win32':
            # CREATE_BREAKAWAY_FROM_JOB (0x01000000) — escape the parent's Job
            #   Object so the daemon survives after the calling process exits.
            # CREATE_NO_WINDOW (0x08000000) — no console window (the daemon
            #   redirects its own stdout/stderr to the log file internally).
            # CREATE_NEW_PROCESS_GROUP (0x00000200) — independent process group.
            creationflags = 0x01000000 | 0x08000000 | 0x00000200
            subprocess.Popen(
                [sys.executable, server_path],
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [sys.executable, server_path],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        return True
    except Exception as e:
        print(f"Warning: Failed to start embedding daemon: {e}")
        return False


def _ensure_daemon() -> bool:
    """Ensure the daemon is running and responsive. Returns True if available.

    1. Ping existing daemon (if state file exists).
    2. If no response, start a new daemon.
    3. Wait up to 30s for it to become responsive (ping).
    4. If still no response, mark unavailable (caller falls back to direct load).
    """
    global _daemon_status
    if _daemon_status == "available":
        return True
    if _daemon_status == "unavailable":
        return False

    # Try to ping an existing daemon
    resp = _daemon_request({"method": "ping"}, timeout=5)
    if resp and resp.get("pong"):
        _daemon_status = "available"
        return True

    # Try to start a new daemon
    if _start_daemon():
        for attempt in range(60):  # 60 * 0.5s = 30s max wait
            time.sleep(0.5)
            resp = _daemon_request({"method": "ping"}, timeout=5)
            if resp and resp.get("pong"):
                _daemon_status = "available"
                print("Embedding daemon started and ready.")
                return True

    _daemon_status = "unavailable"
    print("Embedding daemon unavailable — falling back to direct model loading.")
    return False


def _daemon_embed_batch(texts: List[str]) -> Optional[List[List[float]]]:
    """Embed texts via daemon. Returns list of embeddings or None on failure."""
    resp = _daemon_request({"method": "embed_batch", "texts": texts}, timeout=120)
    if resp and resp.get("error") is None:
        return resp.get("embeddings")
    return None


def get_embedding(text: str) -> List[float]:
    """Fetch vector embedding for a single text.

    Tries the embedding daemon first (model held in memory, ~0.03s).
    Falls back to direct model loading (~21s) if daemon unavailable.
    """
    if _ensure_daemon():
        result = _daemon_embed_batch([text])
        if result is not None:
            return result[0]
        # Daemon failed mid-request — mark unavailable and fall back
        global _daemon_status
        _daemon_status = "unavailable"
    model = _get_model()
    vector = model.encode(text)
    return [float(x) for x in vector]


def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Batch embed multiple texts for better performance.

    Tries the embedding daemon first (model held in memory).
    Falls back to direct model loading if daemon unavailable.
    """
    if _ensure_daemon():
        result = _daemon_embed_batch(texts)
        if result is not None:
            return result
        # Daemon failed mid-request — mark unavailable and fall back
        global _daemon_status
        _daemon_status = "unavailable"
    model = _get_model()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return [[float(x) for x in emb] for emb in embeddings]
# ─── Portfolio ingestion ──────────────────────────────────────────────────────

def _project_hash(filepath: str) -> str:
    """Compute MD5 hash of file content for change detection."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return hashlib.md5(f.read().encode('utf-8')).hexdigest()


def _load_hash_index() -> Dict[str, str]:
    """Load the file→hash index from disk."""
    index_path = os.path.join(ZVEC_DB_PATH, "hash_index.json")
    if os.path.exists(index_path):
        import json
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_hash_index(index: Dict[str, str]):
    """Save the file→hash index to disk."""
    import json
    os.makedirs(ZVEC_DB_PATH, exist_ok=True)
    index_path = os.path.join(ZVEC_DB_PATH, "hash_index.json")
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)


def _build_project_text(proj: Dict) -> str:
    """Build the text to embed for a project (frontmatter + body)."""
    parts = [
        proj.get("title", ""),
        proj.get("description", ""),
        proj.get("technologies", ""),
        " ".join(str(k) for k in proj.get("keywords", [])),
        " ".join(str(a) for a in proj.get("archetypes", [])),
        proj.get("body", "")[:2000],  # Cap body to keep embeddings focused
    ]
    return "\n".join(p for p in parts if p)


def ingest_portfolio(portfolio_dir: str = DEFAULT_PORTFOLIO_DIR, force_recreate: bool = False):
    """Embed all OKF portfolio files into a Zvec vector database.

    Only re-embeds files that have changed (based on content hash).
    Thread-safe and process-safe via zvec_db_lock.
    """
    zvec = _get_zvec()

    # Hash detection and embedding happen outside the lock (CPU-bound, no DB access)
    if force_recreate and os.path.exists(ZVEC_DB_PATH):
        shutil.rmtree(ZVEC_DB_PATH, ignore_errors=True)

    # Load existing hash index
    hash_index = _load_hash_index()

    # Parse all portfolio files
    md_files = sorted(f for f in os.listdir(portfolio_dir) if f.endswith('.md'))
    if not md_files:
        print(f"No .md files found in {portfolio_dir}")
        return

    # Detect which files need re-embedding
    changed_files = []
    unchanged_files = []
    for filename in md_files:
        filepath = os.path.join(portfolio_dir, filename)
        current_hash = _project_hash(filepath)
        if filename not in hash_index or hash_index[filename] != current_hash:
            changed_files.append(filename)
            hash_index[filename] = current_hash
        else:
            unchanged_files.append(filename)

    db_exists = any(f.startswith('manifest.') for f in os.listdir(ZVEC_DB_PATH)) if os.path.exists(ZVEC_DB_PATH) else False

    if not changed_files and db_exists:
        print(f"Zvec database up-to-date ({len(md_files)} files, 0 changed). Skipping ingestion.")
        return

    print(f"Ingesting portfolio: {len(md_files)} files, {len(changed_files)} changed/re-embedding.")

    # Parse all projects
    projects = []
    for filename in md_files:
        filepath = os.path.join(portfolio_dir, filename)
        proj = parse_okf_file(filepath)
        proj["_filename"] = filename
        projects.append(proj)

    # Embed all projects in batch (outside lock — CPU-bound, no DB access)
    # get_embeddings_batch handles model loading (daemon or direct) internally.
    texts = [_build_project_text(p) for p in projects]
    embeddings = get_embeddings_batch(texts)

    # DB operations — acquire cross-process lock
    with zvec_db_lock():
        collection = None
        if db_exists and not force_recreate:
            # Open existing collection and upsert changed documents
            try:
                lock_path = os.path.join(ZVEC_DB_PATH, "LOCK")
                if not os.path.exists(lock_path):
                    os.makedirs(ZVEC_DB_PATH, exist_ok=True)
                    with open(lock_path, 'w') as f:
                        pass
                collection = zvec.open(path=ZVEC_DB_PATH)
            except Exception as e:
                print(f"Warning: Failed to open existing Zvec database ({e}). Recreating from scratch...")
                collection = None

        if collection is not None:
            for idx, proj in enumerate(projects):
                if proj["_filename"] in changed_files:
                    doc = zvec.Doc(
                        id=f"proj_{idx}",
                        vectors={"embedding": embeddings[idx]},
                        fields={
                            "title": proj.get("title", ""),
                            "text": texts[idx][:5000],
                            "filename": proj["_filename"],
                        }
                    )
                    collection.upsert([doc])
        else:
            # Create fresh collection — zvec creates the directory itself
            if os.path.exists(ZVEC_DB_PATH):
                shutil.rmtree(ZVEC_DB_PATH, ignore_errors=True)
            schema = zvec.CollectionSchema(
                name="portfolio",
                fields=[
                    zvec.FieldSchema(name="title", data_type=zvec.DataType.STRING),
                    zvec.FieldSchema(name="text", data_type=zvec.DataType.STRING),
                    zvec.FieldSchema(name="filename", data_type=zvec.DataType.STRING),
                ],
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, EMBEDDING_DIMENSION),
            )
            collection = zvec.create_and_open(path=ZVEC_DB_PATH, schema=schema)

            docs = []
            for idx, proj in enumerate(projects):
                docs.append(zvec.Doc(
                    id=f"proj_{idx}",
                    vectors={"embedding": embeddings[idx]},
                    fields={
                        "title": proj.get("title", ""),
                        "text": texts[idx][:5000],
                        "filename": proj["_filename"],
                    }
                ))
            collection.insert(docs)

        _save_hash_index(hash_index)
        if 'collection' in locals():
            del collection
            import gc
            gc.collect()
    print(f"Zvec ingestion complete: {len(projects)} projects embedded.")


def reembed_file(filepath: str, portfolio_dir: str = DEFAULT_PORTFOLIO_DIR):
    """Re-embed a single portfolio file after okf_learn.py modifies it."""
    zvec = _get_zvec()
    filename = os.path.basename(filepath)

    if not (os.path.exists(ZVEC_DB_PATH) and any(f.startswith('manifest.') for f in os.listdir(ZVEC_DB_PATH))):
        # Database doesn't exist yet — do full ingestion
        ingest_portfolio(portfolio_dir, force_recreate=False)
        return

    proj = parse_okf_file(filepath)
    text = _build_project_text(proj)
    embedding = get_embedding(text)

    # Find the project index by filename
    md_files = sorted(f for f in os.listdir(portfolio_dir) if f.endswith('.md'))
    try:
        idx = md_files.index(filename)
    except ValueError:
        print(f"Warning: {filename} not found in portfolio directory. Skipping re-embed.")
        return

    # DB operations — acquire cross-process lock
    with zvec_db_lock():
        collection = zvec.open(path=ZVEC_DB_PATH)
        doc = zvec.Doc(
            id=f"proj_{idx}",
            vectors={"embedding": embedding},
            fields={
                "title": proj.get("title", ""),
                "text": text[:5000],
                "filename": filename,
            }
        )
        collection.upsert([doc])

        # Update hash index
        hash_index = _load_hash_index()
        hash_index[filename] = _project_hash(filepath)
        _save_hash_index(hash_index)

        del collection
        import gc
        gc.collect()

    print(f"Re-embedded {filename} into Zvec database.")


# ─── Semantic search ──────────────────────────────────────────────────────────

def semantic_search(
    jd_text: str,
    top_k: int = 10,
) -> List[Dict[str, any]]:
    """Query Zvec for semantic similarity matches.

    Returns list of {title, filename, score} sorted by cosine similarity.
    Process-safe via zvec_db_lock.
    """
    zvec = _get_zvec()

    if not (os.path.exists(ZVEC_DB_PATH) and any(f.startswith('manifest.') for f in os.listdir(ZVEC_DB_PATH))):
        print("Zvec database not found. Running ingestion first...")
        ingest_portfolio()

    # Compute JD embedding outside the lock (CPU-bound, no DB access)
    jd_embedding = get_embedding(jd_text)

    # DB query — acquire cross-process lock
    with zvec_db_lock():
        lock_path = os.path.join(ZVEC_DB_PATH, "LOCK")
        if not os.path.exists(lock_path):
            os.makedirs(ZVEC_DB_PATH, exist_ok=True)
            with open(lock_path, 'w') as f:
                pass

        collection = zvec.open(path=ZVEC_DB_PATH)
        results = collection.query(
            zvec.Query(field_name="embedding", vector=jd_embedding),
            topk=top_k
        )

        matched = []
        for doc in results:
            matched.append({
                "id": doc.id,
                "zvec_score": float(doc.score),
                "title": doc.fields.get("title", ""),
                "filename": doc.fields.get("filename", ""),
            })

        del collection
        import gc
        gc.collect()

    return matched


# ─── Hybrid search (score fusion) ─────────────────────────────────────────────

def hybrid_search(
    jd_text: str,
    portfolio_dir: str = DEFAULT_PORTFOLIO_DIR,
    top_k: int = 4,
    jd_primary_archetype: Optional[str] = None,
    jd_secondary_archetype: Optional[str] = None,
    okf_weight: float = HYBRID_OKF_WEIGHT,
    zvec_weight: float = HYBRID_ZVEC_WEIGHT,
) -> List[Dict[str, any]]:
    """Run both OKF and Zvec search, fuse scores, and return top_k projects.

    Score fusion:
      final_score = (okf_score * okf_weight) + (zvec_sim * zvec_weight)

    OKF score is the normalized phrase-match score (typically 0-25 range).
    Zvec score is cosine similarity (0-1 range), scaled to match OKF range
    by multiplying by max_okf_score for comparability.

    Returns projects sorted by fused score, with full diagnostics from both engines.
    """
    # --- Run OKF search (get more than top_k to allow fusion to re-rank) ---
    okf_top = max(top_k * 3, 10)
    okf_results = search_relevant_projects(
        jd_text, portfolio_dir, top_k=okf_top,
        jd_primary_archetype=jd_primary_archetype,
        jd_secondary_archetype=jd_secondary_archetype,
    )

    # --- Run Zvec semantic search ---
    zvec_results = semantic_search(jd_text, top_k=okf_top)

    # --- Build lookup maps ---
    okf_by_title = {}
    for proj in okf_results:
        okf_by_title[proj["title"].lower().strip()] = proj

    zvec_by_title = {}
    for zr in zvec_results:
        zvec_by_title[zr["title"].lower().strip()] = zr

    # --- Find max OKF score for Zvec scaling ---
    max_okf_score = max(
        (p.get("_match_diagnostics", {}).get("score", 0) for p in okf_results),
        default=1.0
    )
    if max_okf_score == 0:
        max_okf_score = 1.0

    # --- Fuse scores ---
    all_titles = set(okf_by_title.keys()) | set(zvec_by_title.keys())
    fused_projects = []

    for title_key in all_titles:
        okf_proj = okf_by_title.get(title_key)
        zvec_match = zvec_by_title.get(title_key)

        okf_score = 0.0
        zvec_score = 0.0
        proj_data = None

        if okf_proj:
            okf_score = okf_proj.get("_match_diagnostics", {}).get("score", 0.0)
            proj_data = okf_proj

        if zvec_match:
            # Scale Zvec cosine similarity (0-1) to OKF score range
            zvec_score = zvec_match["zvec_score"] * max_okf_score

        # If project only found by Zvec (not in OKF top results), load it
        if proj_data is None and zvec_match:
            filepath = os.path.join(portfolio_dir, zvec_match["filename"])
            if os.path.exists(filepath):
                proj_data = parse_okf_file(filepath)
                proj_data["_match_diagnostics"] = {
                    "score": 0.0,
                    "keyword_matches": 0,
                    "tech_matches": 0,
                    "archetype_match_count": 0,
                    "archetype_boost": 0.0,
                    "normalized_overlap": 0.0,
                    "matched_archetypes": [],
                }

        if proj_data is None:
            continue

        # Fused score
        fused_score = (okf_score * okf_weight) + (zvec_score * zvec_weight)

        # Enrich diagnostics with Zvec info
        diag = proj_data.get("_match_diagnostics", {})
        diag["fused_score"] = fused_score
        diag["okf_score"] = okf_score
        diag["zvec_score"] = zvec_score
        diag["zvec_cosine"] = zvec_match["zvec_score"] if zvec_match else 0.0
        proj_data["_match_diagnostics"] = diag

        arch_count = diag.get("archetype_match_count", 0)
        tech_count = diag.get("tech_matches", 0)
        fused_projects.append((fused_score, arch_count, tech_count, proj_data))

    # Sort: fused score desc, then archetype match count desc, then tech match count desc, then alphabetical
    fused_projects.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]["title"]))

    return [item[3] for item in fused_projects[:top_k]]


# ─── Distill with hybrid diagnostics ──────────────────────────────────────────

def distill_project_hybrid(proj: Dict[str, any]) -> str:
    """Formats hybrid search results for project_info.md with both OKF and Zvec diagnostics."""
    title_line = f"# {proj['title']}"
    description = proj.get("description", "").strip()
    techs = proj.get("technologies", "").strip()
    archetypes = proj.get("archetypes", [])
    arch_str = ", ".join(str(a) for a in archetypes) if archetypes else ""

    parts = [title_line]
    if description:
        parts.append(description)
    if techs:
        parts.append(f"Tech: {techs}")
    if arch_str:
        parts.append(f"Archetypes: {arch_str}")

    repo_url = proj.get("repo_url", "").strip()
    if repo_url:
        parts.append(f"Repo: {repo_url}")

    # Body summary
    from okf_portfolio_search import extract_body_summary
    body = proj.get("body", "")
    body_summary = extract_body_summary(body)
    if body_summary:
        parts.append(body_summary)

    # Hybrid match diagnostics
    diag = proj.get("_match_diagnostics", {})
    if diag:
        matched_archs = diag.get("matched_archetypes", [])
        arch_comment = ", ".join(matched_archs) if matched_archs else "none"
        parts.append(
            f"<!-- Match: archetype={arch_comment}, "
            f"{diag.get('keyword_matches', 0)} keyword overlaps, "
            f"{diag.get('tech_matches', 0)} tech overlaps, "
            f"OKF={diag.get('okf_score', 0):.2f}, "
            f"Zvec={diag.get('zvec_cosine', 0):.3f}, "
            f"fused={diag.get('fused_score', 0):.2f} -->"
        )

    return "\n".join(parts)


# ─── Resume-JD similarity (merged from resume_jd_similarity.py) ───────────────
# Computing similarity in the same process as the hybrid search avoids a
# second sentence-transformers model load (saves 3-8 seconds per run).

import math


def _extract_resume_text(resume_path: str) -> str:
    """Extract all text content from a Resume.yaml file or read a markdown file directly."""
    if resume_path.endswith('.md'):
        with open(resume_path, 'r', encoding='utf-8') as f:
            return f.read()
    with open(resume_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return ""

    parts = []

    summary = data.get("summary", "")
    if summary:
        parts.append(str(summary))

    for cat in data.get("technical_skills", []) or []:
        if isinstance(cat, dict):
            parts.append(str(cat.get("category", "")))
            for skill in cat.get("skills", []) or []:
                parts.append(str(skill))

    for proj in data.get("projects", []) or []:
        if isinstance(proj, dict):
            parts.append(str(proj.get("name", "")))
            for tool in proj.get("tools", []) or []:
                parts.append(str(tool))
            for bullet in proj.get("bullets", []) or []:
                parts.append(str(bullet))

    for exp in data.get("professional_experience", []) or []:
        if isinstance(exp, dict):
            parts.append(str(exp.get("company", "")))
            parts.append(str(exp.get("title", "")))
            for bullet in exp.get("bullets", []) or []:
                parts.append(str(bullet))

    for edu in data.get("education", []) or []:
        if isinstance(edu, dict):
            parts.append(str(edu.get("degree", "")))
            parts.append(str(edu.get("university", "")))

    for lang in data.get("languages", []) or []:
        parts.append(str(lang))

    return "\n".join(p for p in parts if p)


def _extract_jd_text(jd_path: str) -> str:
    """Extract all text content from a Job_Description.yaml file."""
    with open(jd_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return ""

    parts = []

    if data.get("position"):
        parts.append(str(data["position"]))
    if data.get("company"):
        parts.append(str(data["company"]))

    for sec in data.get("sections", []) or []:
        if isinstance(sec, dict):
            parts.append(str(sec.get("title", "")))
            parts.append(str(sec.get("content", "")))
            for bullet in sec.get("bullets", []) or []:
                parts.append(str(bullet))

    return "\n".join(p for p in parts if p)


def compute_cosine_similarity(vec_a, vec_b) -> float:
    """Compute cosine similarity between two embedding vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def resume_jd_similarity(resume_path: str, jd_path: str) -> float:
    """Compute cosine similarity between a resume YAML (or .md) and a JD YAML.

    Returns a float in [0, 1] representing semantic alignment.
    """
    resume_text = _extract_resume_text(resume_path)
    jd_text = _extract_jd_text(jd_path)

    if not resume_text or not jd_text:
        return 0.0

    resume_emb = get_embedding(resume_text)
    jd_emb = get_embedding(jd_text)

    return compute_cosine_similarity(resume_emb, jd_emb)


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    # --similarity mode: compute cosine similarity between a resume and JD
    # Usage: python zvec_hybrid_search.py --similarity <resume_path> <jd_path>
    if '--similarity' in args:
        args.remove('--similarity')
        if len(args) < 2:
            print("Usage: python zvec_hybrid_search.py --similarity <resume_path> <jd_path>", file=sys.stderr)
            sys.exit(1)
        resume_path = args[0]
        jd_path = args[1]
        if not os.path.exists(resume_path):
            print(f"Error: Resume file not found: {resume_path}", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(jd_path):
            print(f"Error: JD file not found: {jd_path}", file=sys.stderr)
            sys.exit(1)
        score = resume_jd_similarity(resume_path, jd_path)
        print(f"resume_jd_semantic_similarity: {score:.4f}")
        sys.exit(0)

    if len(args) < 2:
        print("Usage: python zvec_hybrid_search.py <job_description_path> <output_project_info_path> [ats_report_path] [top_k]")
        print("       python zvec_hybrid_search.py --similarity <resume_path> <jd_path>", file=sys.stderr)
        sys.exit(1)

    jd_path = args[0]
    out_path = args[1]
    ats_report_path = args[2] if len(args) > 2 else None
    top_k = int(args[3]) if len(args) > 3 else 4

    if not os.path.exists(jd_path):
        print(f"Error: Job description file not found at {jd_path}")
        sys.exit(1)

    # Read job description (YAML or raw text)
    if jd_path.lower().endswith(('.yaml', '.yml')):
        try:
            with open(jd_path, 'r', encoding='utf-8') as f:
                jd_data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error parsing YAML job description: {e}")
            sys.exit(1)

        query_parts = []
        if isinstance(jd_data, dict):
            if 'position' in jd_data:
                query_parts.append(f"Position: {jd_data['position']}")
            sections = jd_data.get('sections', [])
            for sec in sections:
                if isinstance(sec, dict):
                    title = sec.get('title', '')
                    content = sec.get('content', '')
                    bullets = sec.get('bullets', [])
                    query_parts.append(f"{title}: {content}")
                    if bullets:
                        query_parts.extend(bullets)
        jd_text = "\n".join(query_parts)
    else:
        with open(jd_path, 'r', encoding='utf-8') as f:
            jd_text = f.read()

    # Load archetype signal from ATS_Report.yaml if provided
    jd_primary, jd_secondary = load_jd_archetype(ats_report_path)
    if jd_primary:
        print(f"Loaded JD archetype: primary={jd_primary}, secondary={jd_secondary}")
    else:
        print("No ATS report provided — using raw JD text for archetype matching")

    try:
        # Ensure Zvec database is up-to-date
        ingest_portfolio(DEFAULT_PORTFOLIO_DIR, force_recreate=False)

        # Run hybrid search
        matched = hybrid_search(
            jd_text, DEFAULT_PORTFOLIO_DIR, top_k=top_k,
            jd_primary_archetype=jd_primary,
            jd_secondary_archetype=jd_secondary,
        )

        # Write distilled output
        portfolio_md = "# Tailored Project Portfolio\n\n"
        for proj in matched:
            portfolio_md += f"{distill_project_hybrid(proj)}\n\n---\n\n"

        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(portfolio_md)

        print(f"Successfully matched and wrote {len(matched)} hybrid-scored projects to {out_path}")

    except Exception as e:
        print(f"Error executing hybrid portfolio search: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
