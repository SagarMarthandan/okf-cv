"""
okf_portfolio_search.py — OKF-based Portfolio Search & Matching Tool.

Walks through the portfolio directory, reads Markdown files, parses their
YAML frontmatters, matches them deterministically against a Job Description
based on keywords and archetype, and writes matching projects to project_info.md.

Scoring algorithm:
  - Multi-word phrase matching (no false positives from token splitting)
  - Synonym/alias expansion (bidirectional: kafka ↔ message queue, dbt ↔ transformation framework, etc.)
  - Light stemming (orchestration ↔ orchestrator, pipeline ↔ pipelines)
  - Fuzzy token matching (typo tolerance via difflib, threshold 0.85)
  - Archetype-boosted scoring using JD archetype signal from ATS_Report.yaml
  - Jaccard-style score normalization (prevents JD-length bias)
  - Tiebreaker: archetype match count, then tech match count, then alphabetical
  - Configurable top_k via CLI argument
"""
import os
import re
import sys
import yaml
import difflib
from typing import List, Dict, Set, Tuple, Optional

from config import DEFAULT_PORTFOLIO_DIR


def normalize_phrase(phrase: str) -> str:
    """Normalizes a phrase for substring matching: lowercase, collapse whitespace."""
    return re.sub(r'\s+', ' ', phrase.lower().strip())


# ─── Synonym / alias map (bidirectional) ─────────────────────────────────────
# Maps canonical terms to lists of synonyms. Both directions are used:
#   - Portfolio keyword "kafka" matches JD text containing "message queue"
#   - JD text containing "kafka" matches portfolio keyword "event streaming"
SYNONYM_MAP: Dict[str, List[str]] = {
    "kafka": ["message queue", "event streaming", "pub sub", "event-driven", "event driven"],
    "dbt": ["data build tool", "transformation framework", "data modeling tool"],
    "airflow": ["orchestration", "scheduler", "dag", "workflow orchestration"],
    "dagster": ["orchestration", "data pipeline orchestrator", "asset-based"],
    "snowflake": ["cloud data warehouse", "cloud warehouse", "data warehouse"],
    "bigquery": ["cloud data warehouse", "google warehouse", "gcp warehouse"],
    "databricks": ["data lakehouse", "spark platform", "lakehouse"],
    "docker": ["containerization", "container", "containerized"],
    "kubernetes": ["k8s", "container orchestration", "container orchestration platform"],
    "postgresql": ["postgres", "relational database", "oltp"],
    "mysql": ["relational database", "oltp", "sql database"],
    "power bi": ["business intelligence", "bi dashboard", "bi tool", "data visualization"],
    "tableau": ["business intelligence", "bi dashboard", "data visualization"],
    "apache superset": ["bi dashboard", "data visualization", "dashboard"],
    "looker studio": ["bi dashboard", "data visualization", "dashboard"],
    "terraform": ["infrastructure as code", "iac", "iac tool"],
    "rag": ["retrieval augmented generation", "retrieval-augmented generation", "vector retrieval"],
    "llm": ["large language model", "generative ai", "language model"],
    "faiss": ["vector database", "vector store", "similarity search"],
    "langchain": ["llm framework", "chain of thought", "agent framework"],
    "spark": ["distributed computing", "big data processing", "distributed processing"],
    "delta lake": ["data lakehouse", "acid transactions", "lakehouse storage"],
    "medallion architecture": ["bronze silver gold", "layered architecture", "multi-layer architecture"],
    "unity catalog": ["data governance", "data catalog", "access control"],
    "airbyte": ["data ingestion", "elt ingestion", "open source ingestion"],
    "github actions": ["ci cd", "ci/cd", "continuous integration", "continuous deployment"],
    "jenkins": ["ci cd", "ci/cd", "continuous integration"],
    "redis": ["message broker", "cache", "in-memory store"],
    "numpy": ["numerical computing", "scientific computing", "array processing"],
    "scikit-learn": ["machine learning library", "sklearn", "ml framework"],
    "matplotlib": ["data visualization", "plotting", "charts"],
    "jupyter": ["notebook", "interactive computing", "data science notebook"],
    "latex": ["tex", "typesetting", "document compilation"],
    "streamlit": ["web app", "python web app", "data app", "interactive dashboard"],
    "openai": ["gpt", "llm api", "chatgpt"],
    "elt": ["extract load transform", "etl"],
    "etl": ["extract transform load", "elt"],
    "data warehouse": ["data warehousing", "warehouse", "olap"],
    "data lake": ["data lakehouse", "lake storage", "raw data storage"],
    "data quality": ["data validation", "data testing", "data integrity"],
    "soda": ["data quality", "data testing", "data validation"],
    "window functions": ["analytic functions", "sql window", "partition by"],
    "star schema": ["dimensional modeling", "fact dimension", "data mart modeling"],
    "incremental loading": ["incremental ingestion", "delta loading", "upsert"],
    "scd type 2": ["slowly changing dimension", "dimension history", "versioned dimension"],
    "pyspark": ["spark python", "distributed python", "spark sql"],
    "adls gen2": ["azure data lake", "azure storage", "blob storage"],
    "azure data factory": ["adf", "azure orchestration", "azure pipeline"],
    "azure key vault": ["secrets management", "credential store", "secret manager"],
}

# Build reverse lookup: synonym → canonical term
_REVERSE_SYNONYMS: Dict[str, str] = {}
for _canon, _syns in SYNONYM_MAP.items():
    for _syn in _syns:
        _REVERSE_SYNONYMS[_syn] = _canon
    _REVERSE_SYNONYMS[_canon] = _canon


def get_synonyms(phrase: str) -> List[str]:
    """Returns all synonyms for a phrase (both directions)."""
    norm = normalize_phrase(phrase)
    result = []
    if norm in SYNONYM_MAP:
        result.extend(SYNONYM_MAP[norm])
    if norm in _REVERSE_SYNONYMS:
        canon = _REVERSE_SYNONYMS[norm]
        if canon != norm:
            result.append(canon)
        if canon in SYNONYM_MAP:
            result.extend(SYNONYM_MAP[canon])
    # Deduplicate, preserve order
    seen = set()
    unique = []
    for s in result:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


# ─── Light stemming ──────────────────────────────────────────────────────────
_STEM_SUFFIXES = [
    (r'tion$', 't'),
    (r'ing$', ''),
    (r'er$', ''),
    (r'ed$', ''),
    (r'es$', ''),
    (r's$', ''),
]


def light_stem(word: str) -> str:
    """Strips common English suffixes for morphological variant matching."""
    w = word.lower()
    for pattern, replacement in _STEM_SUFFIXES:
        if re.search(pattern, w) and len(w) > 4:
            return re.sub(pattern, replacement, w)
    return w


# ─── Fuzzy token matching ───────────────────────────────────────────────────
_FUZZY_THRESHOLD = 0.85


def fuzzy_word_in_set(word: str, token_set: Set[str]) -> bool:
    """Checks if a word fuzzy-matches any token in a set (typo tolerance)."""
    if not word or not token_set:
        return False
    w = word.lower()
    if w in token_set:
        return True
    for token in token_set:
        if abs(len(w) - len(token)) <= 2:
            ratio = difflib.SequenceMatcher(None, w, token).ratio()
            if ratio >= _FUZZY_THRESHOLD:
                return True
    return False


def tokenize(text: str) -> Set[str]:
    """Cleans and extracts alphanumeric lowercase tokens from text."""
    if not text:
        return set()
    words = re.findall(r'\b\w+\b', text.lower())
    stopwords = {'and', 'the', 'for', 'with', 'a', 'an', 'to', 'in', 'of', 'on', 'at', 'by', 'is'}
    return {w for w in words if w not in stopwords}


def build_jd_stemmed_tokens(jd_tokens: Set[str]) -> Set[str]:
    """Builds a set of light-stemmed JD tokens for morphological matching."""
    return {light_stem(t) for t in jd_tokens}


def phrase_in_jd(
    phrase: str,
    jd_text_lower: str,
    jd_tokens: Optional[Set[str]] = None,
    jd_stemmed: Optional[Set[str]] = None,
) -> bool:
    """Checks if a phrase appears in the JD text using 4 matching layers:

    1. Exact phrase match (substring for multi-word, word-boundary for single)
    2. Synonym expansion (check all synonyms of the phrase in JD)
    3. Light stemming (orchestrat matches orchestration/orchestrator)
    4. Fuzzy matching (single words only, typo tolerance via difflib)
    """
    norm = normalize_phrase(phrase)
    if not norm:
        return False

    # Layer 1: Exact match
    if ' ' in norm:
        if norm in jd_text_lower:
            return True
    else:
        if re.search(r'\b' + re.escape(norm) + r'\b', jd_text_lower):
            return True

    # Layer 2: Synonym expansion
    synonyms = get_synonyms(norm)
    for syn in synonyms:
        syn_norm = normalize_phrase(syn)
        if ' ' in syn_norm:
            if syn_norm in jd_text_lower:
                return True
        else:
            if re.search(r'\b' + re.escape(syn_norm) + r'\b', jd_text_lower):
                return True

    # Layers 3 & 4: Stemming + fuzzy (single words only)
    if ' ' not in norm and jd_tokens is not None:
        # Layer 3: Stemmed match
        if jd_stemmed is None:
            jd_stemmed = {light_stem(t) for t in jd_tokens}
        stemmed_phrase = light_stem(norm)
        for token in jd_tokens:
            if light_stem(token) == stemmed_phrase:
                return True

        # Layer 4: Fuzzy match
        if fuzzy_word_in_set(norm, jd_tokens):
            return True

    return False


def parse_okf_file(filepath: str) -> Dict[str, any]:
    """Parses a single OKF Markdown file, extracting YAML frontmatter and body."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match YAML frontmatter between triple dashes
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if match:
        yaml_block = match.group(1)
        body = match.group(2).strip()
        try:
            metadata = yaml.safe_load(yaml_block)
        except Exception as e:
            print(f"Warning: Failed to parse YAML frontmatter in {filepath}: {e}")
            metadata = {}
    else:
        metadata = {}
        body = content.strip()

    # Fallbacks if keys are missing
    metadata.setdefault("title", os.path.splitext(os.path.basename(filepath))[0])
    metadata.setdefault("description", "")
    metadata.setdefault("technologies", "")
    metadata.setdefault("keywords", [])
    metadata.setdefault("archetypes", [])
    metadata.setdefault("repo_url", "")
    metadata["body"] = body
    metadata["filepath"] = filepath
    
    return metadata


def load_jd_archetype(ats_report_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Loads primary and secondary archetype from ATS_Report.yaml if available."""
    if not ats_report_path or not os.path.exists(ats_report_path):
        return None, None
    try:
        with open(ats_report_path, 'r', encoding='utf-8') as f:
            report = yaml.safe_load(f)
        if not isinstance(report, dict):
            return None, None
        role_arch = report.get("role_archetype", {})
        primary = role_arch.get("primary") if isinstance(role_arch, dict) else None
        secondary = role_arch.get("secondary") if isinstance(role_arch, dict) else None
        return primary, secondary
    except Exception:
        return None, None


def search_relevant_projects(
    jd_text: str,
    portfolio_dir: str,
    top_k: int = 4,
    jd_primary_archetype: Optional[str] = None,
    jd_secondary_archetype: Optional[str] = None,
) -> List[Dict[str, any]]:
    """Calculates relevance scores for OKF projects against a JD and ranks them.

    Scoring components:
      - Phrase-level matching for keywords (x4), technologies (x3), description (x1)
      - Title token overlap (x5)
      - Archetype boost: +10 for primary match, +5 for secondary match (binary, unnormalized)
      - Jaccard-style normalization on the token-overlap component
      - Tiebreaker: archetype match count desc, tech match count desc, then alphabetical
    """
    if not os.path.exists(portfolio_dir):
        raise ValueError(f"Portfolio directory not found at: {portfolio_dir}")

    jd_text_lower = jd_text.lower()
    jd_tokens = tokenize(jd_text)
    jd_stemmed = build_jd_stemmed_tokens(jd_tokens)
    projects = []

    for filename in os.listdir(portfolio_dir):
        if filename.endswith('.md'):
            filepath = os.path.join(portfolio_dir, filename)
            try:
                proj_data = parse_okf_file(filepath)
                projects.append(proj_data)
            except Exception as e:
                print(f"Error reading file {filename}: {e}")

    scored_projects = []
    for proj in projects:
        # --- Phrase-level matching with synonym/stem/fuzzy layers ---
        keyword_matches = 0
        for kw in proj.get("keywords", []):
            if phrase_in_jd(str(kw), jd_text_lower, jd_tokens, jd_stemmed):
                keyword_matches += 1

        tech_matches = 0
        tech_list = [t.strip() for t in str(proj.get("technologies", "")).split(",") if t.strip()]
        for tech in tech_list:
            if phrase_in_jd(tech, jd_text_lower, jd_tokens, jd_stemmed):
                tech_matches += 1

        desc_matches = 0
        for word in tokenize(proj.get("description", "")):
            if word in jd_tokens:
                desc_matches += 1
            elif light_stem(word) in jd_stemmed:
                desc_matches += 1
            elif fuzzy_word_in_set(word, jd_tokens):
                desc_matches += 1

        title_matches = 0
        for word in tokenize(proj.get("title", "")):
            if word in jd_tokens:
                title_matches += 1
            elif light_stem(word) in jd_stemmed:
                title_matches += 1
            elif fuzzy_word_in_set(word, jd_tokens):
                title_matches += 1

        # --- Raw weighted token-overlap score ---
        raw_overlap = (
            title_matches * 5.0
            + keyword_matches * 4.0
            + tech_matches * 3.0
            + desc_matches * 1.0
        )

        # --- Jaccard-style normalization ---
        total_metadata_tokens = set()
        total_metadata_tokens.update(tokenize(proj.get("title", "")))
        total_metadata_tokens.update(tokenize(proj.get("description", "")))
        total_metadata_tokens.update(tokenize(proj.get("technologies", "")))
        for kw in proj.get("keywords", []):
            total_metadata_tokens.update(tokenize(str(kw)))
        # Also count phrase tokens
        for tech in tech_list:
            total_metadata_tokens.update(tokenize(tech))

        normalization_divisor = max(len(total_metadata_tokens), 1)
        normalized_overlap = raw_overlap / normalization_divisor

        # --- Archetype boost (binary, unnormalized) ---
        archetype_boost = 0.0
        archetype_match_count = 0
        proj_archetypes = [a.lower() for a in proj.get("archetypes", [])]

        if jd_primary_archetype:
            if jd_primary_archetype.lower() in proj_archetypes:
                archetype_boost += 10.0
                archetype_match_count += 1
        if jd_secondary_archetype:
            if jd_secondary_archetype.lower() in proj_archetypes:
                archetype_boost += 5.0
                archetype_match_count += 1

        # Also check raw JD text for archetype phrases (fallback when no ATS report)
        if not jd_primary_archetype:
            for arch in proj.get("archetypes", []):
                if phrase_in_jd(str(arch), jd_text_lower, jd_tokens, jd_stemmed):
                    archetype_boost += 3.0
                    archetype_match_count += 1

        total_score = normalized_overlap + archetype_boost

        # Store match diagnostics for distill output
        proj["_match_diagnostics"] = {
            "score": total_score,
            "keyword_matches": keyword_matches,
            "tech_matches": tech_matches,
            "archetype_match_count": archetype_match_count,
            "archetype_boost": archetype_boost,
            "normalized_overlap": normalized_overlap,
            "matched_archetypes": [
                a for a in proj.get("archetypes", [])
                if (jd_primary_archetype and a.lower() == jd_primary_archetype.lower())
                or (jd_secondary_archetype and a.lower() == jd_secondary_archetype.lower())
                or (not jd_primary_archetype and phrase_in_jd(str(a), jd_text_lower, jd_tokens, jd_stemmed))
            ],
        }

        scored_projects.append((total_score, archetype_match_count, tech_matches, proj))

    # Sort: score desc, then archetype match count desc, then tech match count desc, then alphabetical
    scored_projects.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]["title"]))

    return [item[3] for item in scored_projects[:top_k]]


def extract_body_summary(body: str, max_sentences: int = 2) -> str:
    """Extracts the first 1-2 sentences from the body's opening paragraph.

    Skips markdown headers, images, and badges to find the first prose paragraph.
    """
    lines = body.split('\n')
    prose_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if prose_lines:
                break
            continue
        if stripped.startswith('#') or stripped.startswith('![') or stripped.startswith('[!['):
            continue
        if stripped.startswith('|') or stripped.startswith('```'):
            continue
        prose_lines.append(stripped)

    if not prose_lines:
        return ""

    prose = ' '.join(prose_lines)
    sentences = re.split(r'(?<=[.!?])\s+', prose)
    return ' '.join(sentences[:max_sentences])


def distill_project(proj: Dict[str, any]) -> str:
    """Formats the selected OKF project data for project_info.md.

    Emits:
      - Title
      - Description (from frontmatter)
      - Tech: <technologies>
      - Archetypes: <archetypes>
      - First 1-2 sentences of body opening paragraph (context block)
      - Match diagnostics as a comment line (debuggability)
    """
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

    body = proj.get("body", "")
    body_summary = extract_body_summary(body)
    if body_summary:
        parts.append(body_summary)

    # Match diagnostics as comment (Step 2 ignores comments, free observability)
    diag = proj.get("_match_diagnostics", {})
    if diag:
        matched_archs = diag.get("matched_archetypes", [])
        arch_comment = ", ".join(matched_archs) if matched_archs else "none"
        parts.append(
            f"<!-- Match: archetype={arch_comment}, "
            f"{diag.get('keyword_matches', 0)} keyword overlaps, "
            f"{diag.get('tech_matches', 0)} tech overlaps, "
            f"score={diag.get('score', 0):.2f} -->"
        )

    return "\n".join(parts)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python okf_portfolio_search.py <job_description_path> <output_project_info_path> [ats_report_path] [top_k]")
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
        matched = search_relevant_projects(
            jd_text, DEFAULT_PORTFOLIO_DIR, top_k=top_k,
            jd_primary_archetype=jd_primary,
            jd_secondary_archetype=jd_secondary,
        )

        portfolio_md = "# Tailored Project Portfolio\n\n"
        for proj in matched:
            portfolio_md += f"{distill_project(proj)}\n\n---\n\n"

        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(portfolio_md)

        print(f"Successfully matched and wrote {len(matched)} OKF projects to {out_path}")

    except Exception as e:
        print(f"Error executing OKF portfolio search: {e}")
        sys.exit(1)
