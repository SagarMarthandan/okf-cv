"""
okf_learn.py — Self-learning keyword enrichment for OKF portfolio files.

After each application run, this script extracts useful terms from the
processed Job Description and enriches matched projects' frontmatter keywords
with terms that appear in the project body but were not previously tagged.

Safeguards:
  - Only terms found in the project's own body/description/technologies are eligible
  - Max 3 new keywords per project per run
  - 15 keywords max per file (linter enforced, rollback on violation)
  - Every change logged to okf/learning_log.json
  - Idempotent: won't add duplicate keywords

Usage:
    python okf_learn.py <application_folder_path> [portfolio_dir]
"""
import json
import os
import re
import sys
import yaml
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional

from config import DEFAULT_PORTFOLIO_DIR, SKILL_DIR
from okf_utils import tokenize as _tokenize_base, EXTENDED_STOPWORDS, parse_frontmatter

MAX_NEW_KEYWORDS_PER_RUN = 3
MAX_KEYWORDS_PER_FILE = 15
LEARNING_LOG_PATH = os.path.join(SKILL_DIR, "okf", "learning_log.json")

# Generic words that should never be added as keywords.
# Loaded from okf/noise_words.yaml at import time. Edit that file to tune filtering.
_NOISE_WORDS_PATH = os.path.join(SKILL_DIR, "okf", "noise_words.yaml")

def _load_noise_words() -> frozenset:
    """Load noise words from okf/noise_words.yaml."""
    try:
        with open(_NOISE_WORDS_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and 'words' in data:
            return frozenset(data['words'])
    except Exception as e:
        print(f"Warning: Could not load noise words from {_NOISE_WORDS_PATH}: {e}")
    return frozenset()

NOISE_WORDS = _load_noise_words()

# Domain-relevant bigrams/trigrams to look for in JD text.
# Loaded from okf/phrase_patterns.yaml at import time. Edit that file to tune extraction.
_PHRASE_PATTERNS_PATH = os.path.join(SKILL_DIR, "okf", "phrase_patterns.yaml")

def _load_phrase_patterns() -> list:
    """Load phrase patterns from okf/phrase_patterns.yaml."""
    try:
        with open(_PHRASE_PATTERNS_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and 'patterns' in data:
            return data['patterns']
    except Exception as e:
        print(f"Warning: Could not load phrase patterns from {_PHRASE_PATTERNS_PATH}: {e}")
    return []

PHRASE_PATTERNS = _load_phrase_patterns()


def tokenize(text: str) -> Set[str]:
    """Extract lowercase alphanumeric tokens, minus extended stopwords (min length > 2)."""
    return _tokenize_base(text, stopwords=EXTENDED_STOPWORDS, min_length=2)


def extract_jd_phrases(jd_text: str) -> List[str]:
    """Extract domain-relevant phrases (bigrams/trigrams) from JD text.

    Returns a list of normalized phrases found in the JD.
    """
    jd_lower = jd_text.lower()
    phrases = []
    for pattern in PHRASE_PATTERNS:
        matches = re.findall(pattern, jd_lower)
        for match in matches:
            normalized = re.sub(r'\s+', ' ', match.strip())
            if normalized not in phrases:
                phrases.append(normalized)
    return phrases


def extract_jd_terms(jd_text: str) -> List[str]:
    """Extract all meaningful terms from JD: single tokens + domain phrases.

    Returns a deduplicated list, phrases first (higher value), then single tokens.
    """
    phrases = extract_jd_phrases(jd_text)
    tokens = sorted(tokenize(jd_text))
    # Combine: phrases first, then tokens not already part of a phrase
    phrase_token_set = set()
    for p in phrases:
        phrase_token_set.update(p.split())
    single_tokens = [t for t in tokens if t not in phrase_token_set]
    return phrases + single_tokens


def load_jd_text(app_folder: str) -> Optional[str]:
    """Load JD text from Job_Description.yaml in the application folder."""
    jd_path = os.path.join(app_folder, "Job_Description.yaml")
    if not os.path.exists(jd_path):
        return None
    try:
        with open(jd_path, 'r', encoding='utf-8') as f:
            jd_data = yaml.safe_load(f)
        if not isinstance(jd_data, dict):
            return None
        parts = []
        if jd_data.get('position'):
            parts.append(str(jd_data['position']))
        for sec in jd_data.get('sections', []):
            if isinstance(sec, dict):
                parts.append(str(sec.get('title', '')))
                parts.append(str(sec.get('content', '')))
                for bullet in sec.get('bullets', []):
                    parts.append(str(bullet))
        return "\n".join(parts)
    except Exception:
        return None


def load_role_archetype(app_folder: str) -> Optional[str]:
    """Load primary role archetype from ATS_Report.yaml."""
    ats_path = os.path.join(app_folder, "ATS_Report.yaml")
    if not os.path.exists(ats_path):
        return None
    try:
        with open(ats_path, 'r', encoding='utf-8') as f:
            report = yaml.safe_load(f)
        if isinstance(report, dict):
            role_arch = report.get("role_archetype", {})
            if isinstance(role_arch, dict):
                return role_arch.get("primary")
        return None
    except Exception:
        return None


def load_ats_scores(app_folder: str) -> Dict:
    """Extract pre-rewrite and post-rewrite ATS scores from ATS_Report.yaml.

    Returns a dict with 'pre_rewrite_ats_score' and 'post_rewrite_ats_score' keys.
    Values are None if not present.
    """
    ats_path = os.path.join(app_folder, "ATS_Report.yaml")
    if not os.path.exists(ats_path):
        return {"pre_rewrite_ats_score": None, "post_rewrite_ats_score": None}
    try:
        with open(ats_path, 'r', encoding='utf-8') as f:
            report = yaml.safe_load(f)
        if not isinstance(report, dict):
            return {"pre_rewrite_ats_score": None, "post_rewrite_ats_score": None}

        pre_score = None
        matrix = report.get("ats_score_matrix", {})
        if isinstance(matrix, dict):
            pre_score = matrix.get("total_score")

        post_score = None
        post = report.get("post_rewrite_ats_score", {})
        if isinstance(post, dict):
            post_matrix = post.get("ats_score_matrix", {})
            if isinstance(post_matrix, dict):
                post_score = post_matrix.get("total_score")

        return {
            "pre_rewrite_ats_score": pre_score,
            "post_rewrite_ats_score": post_score,
        }
    except Exception:
        return {"pre_rewrite_ats_score": None, "post_rewrite_ats_score": None}


def load_matched_project_titles(app_folder: str) -> List[str]:
    """Extract project titles from project_info.md."""
    proj_info_path = os.path.join(app_folder, "project_info.md")
    if not os.path.exists(proj_info_path):
        return []
    with open(proj_info_path, 'r', encoding='utf-8') as f:
        content = f.read()
    titles = []
    for match in re.finditer(r'^#\s+(.+)$', content, re.MULTILINE):
        title = match.group(1).strip()
        if title and title.lower() != "tailored project portfolio":
            titles.append(title)
    return titles


def find_portfolio_file_for_title(title: str, portfolio_dir: str) -> Optional[str]:
    """Find the portfolio .md file whose frontmatter title matches the given title."""
    if not os.path.isdir(portfolio_dir):
        return None
    for filename in os.listdir(portfolio_dir):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(portfolio_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if fm_match:
                meta = yaml.safe_load(fm_match.group(1))
                if isinstance(meta, dict) and meta.get("title", "").strip() == title.strip():
                    return filepath
        except Exception:
            continue
    return None


def parse_portfolio_file(filepath: str) -> Tuple[Dict, str, str]:
    """Parse a portfolio file into (metadata, yaml_block, body).

    Returns (metadata_dict, raw_yaml_block, body_text).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, "", content

    yaml_block = match.group(1)
    body = match.group(2)
    meta = yaml.safe_load(yaml_block) or {}
    return meta, yaml_block, body


def find_untagged_terms(
    jd_terms: List[str],
    project_body: str,
    project_desc: str,
    project_techs: str,
    existing_keywords: List[str],
) -> List[str]:
    """Find JD terms that appear in the project body/desc/techs but not in keywords.

    Returns a list of terms eligible for addition, ordered by phrase priority.
    Filters out generic noise words that should never be keywords.
    """
    body_lower = project_body.lower()
    desc_lower = project_desc.lower()
    techs_lower = project_techs.lower()
    existing_lower = {k.lower() for k in existing_keywords}

    untagged = []
    for term in jd_terms:
        if term.lower() in existing_lower:
            continue
        # Skip noise words (single words only)
        if ' ' not in term and term.lower() in NOISE_WORDS:
            continue
        # Skip very short single words (< 4 chars)
        if ' ' not in term and len(term) < 4:
            continue
        # Check if term appears in body, description, or technologies
        if ' ' in term:
            # Multi-word phrase: substring check
            if term in body_lower or term in desc_lower or term in techs_lower:
                untagged.append(term)
        else:
            # Single word: word-boundary check
            pattern = r'\b' + re.escape(term) + r'\b'
            if (re.search(pattern, body_lower) or
                    re.search(pattern, desc_lower) or
                    re.search(pattern, techs_lower)):
                untagged.append(term)

    return untagged


def add_keywords_to_file(filepath: str, new_keywords: List[str]) -> bool:
    """Append new keywords to a portfolio file's YAML frontmatter.

    Uses yaml.safe_load / yaml.safe_dump to modify the frontmatter dict in
    memory, then re-serializes. This replaces the previous fragile line-by-line
    string manipulation that broke on quoted values, multi-line entries, or
    comments in the frontmatter.

    Returns True if the file was modified, False if no change.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^(---\s*\n)(.*?)(\n---\s*\n)(.*)', content, re.DOTALL)
    if not match:
        return False

    yaml_block = match.group(2)
    body = match.group(4)
    meta = yaml.safe_load(yaml_block) or {}
    if not isinstance(meta, dict):
        return False

    existing_keywords = meta.get("keywords", [])
    if not isinstance(existing_keywords, list):
        existing_keywords = []
    existing_lower = {k.lower() for k in existing_keywords}

    # Filter out duplicates
    to_add = [k for k in new_keywords if k.lower() not in existing_lower]
    if not to_add:
        return False

    # Check cap
    if len(existing_keywords) + len(to_add) > MAX_KEYWORDS_PER_FILE:
        space = MAX_KEYWORDS_PER_FILE - len(existing_keywords)
        if space <= 0:
            return False
        to_add = to_add[:space]

    # Update the keywords list in the parsed dict
    meta["keywords"] = existing_keywords + to_add

    # Re-serialize the frontmatter. Use allow_unicode=True to preserve non-ASCII
    # keywords, default_flow_style=False for block format (readable), and
    # sort_keys=False to preserve the original key order.
    new_yaml_block = yaml.safe_dump(
        meta,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip('\n')

    new_content = f"---\n{new_yaml_block}\n---\n{body}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def append_learning_log(entry: Dict) -> None:
    """Append a learning log entry to okf/learning_log.json."""
    log = []
    if os.path.exists(LEARNING_LOG_PATH):
        try:
            with open(LEARNING_LOG_PATH, 'r', encoding='utf-8') as f:
                log = json.load(f)
            if not isinstance(log, list):
                log = []
        except Exception:
            log = []

    log.append(entry)

    os.makedirs(os.path.dirname(LEARNING_LOG_PATH), exist_ok=True)
    with open(LEARNING_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def run_linter(portfolio_dir: str, target_file: Optional[str] = None, baseline_violations: Optional[List[str]] = None) -> bool:
    """Run okf_lint.py on the portfolio directory. Returns True if pass.
    
    If target_file is provided, only checks that specific file via lint_file().
    If baseline_violations is provided, only NEW violations (not in baseline) cause failure.
    """
    if target_file:
        # Lint only the modified file directly
        try:
            from okf_lint import lint_file
            violations = lint_file(target_file)
            if baseline_violations is not None:
                # Only count new violations
                baseline_set = set(baseline_violations)
                new_violations = [v for v in violations if v not in baseline_set]
                return len(new_violations) == 0
            return len(violations) == 0
        except Exception:
            return True
    
    # Full linter run via subprocess
    import subprocess
    linter_path = os.path.join(SKILL_DIR, "okf_lint.py")
    if not os.path.exists(linter_path):
        return True
    try:
        result = subprocess.run(
            [sys.executable, linter_path, portfolio_dir],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return True


def learn_from_application(app_folder: str, portfolio_dir: str) -> Dict:
    """Main learning loop: enrich portfolio keywords from a completed application.

    Returns a summary dict of what was learned.
    """
    # 1. Load JD text
    jd_text = load_jd_text(app_folder)
    if not jd_text:
        return {"error": "Could not load Job_Description.yaml from application folder"}

    # 2. Load role archetype
    role_archetype = load_role_archetype(app_folder)

    # 2b. Load ATS scores for delta tracking
    ats_scores = load_ats_scores(app_folder)

    # 3. Load matched project titles from project_info.md
    matched_titles = load_matched_project_titles(app_folder)
    if not matched_titles:
        return {"error": "No project titles found in project_info.md"}

    # 4. Extract JD terms (phrases first, then single tokens)
    jd_terms = extract_jd_terms(jd_text)

    # 5. For each matched project, find untagged terms and enrich
    changes = []
    files_modified = []

    for title in matched_titles:
        filepath = find_portfolio_file_for_title(title, portfolio_dir)
        if not filepath:
            continue

        meta, yaml_block, body = parse_portfolio_file(filepath)
        existing_keywords = meta.get("keywords", [])

        # Skip if already at cap
        if len(existing_keywords) >= MAX_KEYWORDS_PER_FILE:
            continue

        # Find JD terms in project body/desc/techs but not in keywords
        desc = str(meta.get("description", ""))
        techs = str(meta.get("technologies", ""))
        untagged = find_untagged_terms(jd_terms, body, desc, techs, existing_keywords)

        if not untagged:
            continue

        # Cap at MAX_NEW_KEYWORDS_PER_RUN
        to_add = untagged[:MAX_NEW_KEYWORDS_PER_RUN]

        # Snapshot for rollback
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Capture baseline lint violations (pre-existing issues that shouldn't block enrichment)
        try:
            from okf_lint import lint_file
            baseline_violations = lint_file(filepath)
        except Exception:
            baseline_violations = None

        # Write new keywords
        modified = add_keywords_to_file(filepath, to_add)
        if not modified:
            continue

        # Run linter to validate (only the modified file, only new violations)
        linter_ok = run_linter(portfolio_dir, target_file=filepath, baseline_violations=baseline_violations)
        if not linter_ok:
            # Rollback
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(original_content)
            changes.append({
                "file": os.path.basename(filepath),
                "added_keywords": [],
                "rolled_back": True,
                "reason": "Linter validation failed after enrichment",
            })
            continue

        files_modified.append(filepath)
        changes.append({
            "file": os.path.basename(filepath),
            "added_keywords": to_add,
            "rolled_back": False,
            "reason": f"JD mentioned '{', '.join(to_add)}'; terms found in project body but not in keywords",
        })

    # 6. Re-embed modified files into Zvec database (hybrid search support)
    if files_modified:
        try:
            from zvec_hybrid_search import reembed_file
            for fpath in files_modified:
                reembed_file(fpath, portfolio_dir)
        except Exception as e:
            print(f"Warning: Zvec re-embed failed (non-blocking): {e}")

        # Invalidate lint cache for modified files so the next lint re-checks them
        try:
            from okf_lint import invalidate_cache
            modified_names = [os.path.basename(f) for f in files_modified]
            invalidate_cache(portfolio_dir, modified_names)
        except Exception as e:
            print(f"Warning: Could not invalidate lint cache (non-blocking): {e}")

    # 7. Log to learning_log.json
    log_entry = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "jd_source": os.path.basename(os.path.normpath(app_folder)),
        "role_archetype": role_archetype,
        "pre_rewrite_ats_score": ats_scores["pre_rewrite_ats_score"],
        "post_rewrite_ats_score": ats_scores["post_rewrite_ats_score"],
        "changes": changes,
    }
    append_learning_log(log_entry)

    return {
        "projects_checked": len(matched_titles),
        "projects_enriched": len(files_modified),
        "changes": changes,
        "log_entry": log_entry,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python okf_learn.py <application_folder_path> [portfolio_dir]")
        sys.exit(1)

    app_folder = sys.argv[1]
    portfolio_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORTFOLIO_DIR

    if not os.path.isdir(app_folder):
        print(f"Error: Application folder not found: {app_folder}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(portfolio_dir):
        print(f"Error: Portfolio directory not found: {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Learning from application: {app_folder}")
    print(f"Portfolio directory: {portfolio_dir}")

    result = learn_from_application(app_folder, portfolio_dir)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"\nProjects checked: {result['projects_checked']}")
    print(f"Projects enriched: {result['projects_enriched']}")

    for change in result["changes"]:
        if change.get("rolled_back"):
            print(f"  ROLLED BACK: {change['file']} — {change['reason']}")
        elif change["added_keywords"]:
            print(f"  ENRICHED: {change['file']} — added: {', '.join(change['added_keywords'])}")
        else:
            print(f"  NO CHANGE: {change['file']}")

    print(f"\nLearning log: {LEARNING_LOG_PATH}")


if __name__ == "__main__":
    main()
