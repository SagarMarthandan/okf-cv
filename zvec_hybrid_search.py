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
import shutil
import hashlib
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
    """Thread-safe lazy initialization of SentenceTransformer model."""
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                from sentence_transformers import SentenceTransformer
                print(f"Loading local SentenceTransformer model '{EMBEDDING_MODEL_NAME}'...")
                _model_instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_instance


def get_embedding(text: str) -> List[float]:
    """Fetch vector embedding for a single text."""
    model = _get_model()
    vector = model.encode(text)
    return [float(x) for x in vector]


def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Batch embed multiple texts for better performance."""
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
    texts = [_build_project_text(p) for p in projects]
    _get_model()  # Ensure model is loaded
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


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python zvec_hybrid_search.py <job_description_path> <output_project_info_path> [ats_report_path] [top_k]")
        sys.exit(1)

    jd_path = sys.argv[1]
    out_path = sys.argv[2]
    ats_report_path = sys.argv[3] if len(sys.argv) > 3 else None
    top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 4

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
