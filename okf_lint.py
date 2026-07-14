"""
okf_lint.py — Frontmatter linter for OKF portfolio files.

Validates that every portfolio .md file in okf/portfolio/ has clean, well-formed
YAML frontmatter. Fails loud with the offending file + field if any rule is violated.

Uses a content-hash cache (okf/.lint_cache.json) to skip files whose frontmatter
hasn't changed since the last successful lint. The cache is invalidated by
okf_learn.py when it modifies portfolio files. Use --force to ignore the cache
and lint all files.

Usage:
    python okf_lint.py [portfolio_dir] [--force]
"""
import os
import re
import sys
import json
import hashlib
import yaml
from typing import List, Tuple

from config import DEFAULT_PORTFOLIO_DIR

CANONICAL_ARCHETYPES = {
    "Data Engineering",
    "Analytics Engineering",
    "Data Analyst",
    "AI Engineer",
    "AI/LLMOps",
    "Agentic/Automation",
    "ML Engineering",
    "Backend/Platform Engineering",
}

DENYLIST_TECH_TOKENS = {
    "2025",
    "project status",
    "screenshot",
    "er diagram",
    "tech stack",
    "complete",
    "youtube",
}

MIN_KEYWORDS = 4
MAX_KEYWORDS = 15
MAX_DESCRIPTION_CHARS = 200

# Cache file path (stored in the okf/ directory next to the portfolio)
_LINT_CACHE_FILENAME = ".lint_cache.json"


def _cache_path(portfolio_dir: str) -> str:
    return os.path.join(os.path.dirname(portfolio_dir), _LINT_CACHE_FILENAME)


def _file_hash(filepath: str) -> str:
    """SHA256 of the file content for change detection."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def _load_cache(portfolio_dir: str) -> dict:
    path = _cache_path(portfolio_dir)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(portfolio_dir: str, cache: dict) -> None:
    path = _cache_path(portfolio_dir)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save lint cache: {e}", file=sys.stderr)


def invalidate_cache(portfolio_dir: str, filenames: list) -> None:
    """Remove specific files from the cache (called by okf_learn.py after enrichment)."""
    cache = _load_cache(portfolio_dir)
    changed = False
    for fn in filenames:
        if fn in cache:
            del cache[fn]
            changed = True
    if changed:
        _save_cache(portfolio_dir, cache)


def tokenize(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r'\b\w+\b', text.lower()))


def lint_file(filepath: str) -> List[str]:
    """Returns a list of violation strings for a single file. Empty list = clean."""
    violations = []
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        violations.append(f"{filename}: No YAML frontmatter block found")
        return violations

    yaml_block = match.group(1)
    try:
        meta = yaml.safe_load(yaml_block)
    except Exception as e:
        violations.append(f"{filename}: YAML parse error: {e}")
        return violations

    if not isinstance(meta, dict):
        violations.append(f"{filename}: Frontmatter is not a dict")
        return violations

    # Check technologies
    techs = meta.get("technologies", "")
    if not techs or not str(techs).strip():
        violations.append(f"{filename}: technologies is empty")
    else:
        tech_str = str(techs).lower()
        for bad in DENYLIST_TECH_TOKENS:
            if bad in tech_str:
                violations.append(f"{filename}: technologies contains denylisted token '{bad}'")

    # Check description
    desc = meta.get("description", "")
    if not desc or not str(desc).strip():
        violations.append(f"{filename}: description is empty")
    elif len(str(desc)) > MAX_DESCRIPTION_CHARS:
        violations.append(f"{filename}: description exceeds {MAX_DESCRIPTION_CHARS} chars ({len(str(desc))})")

    # Check archetypes
    archetypes = meta.get("archetypes", [])
    if not archetypes:
        violations.append(f"{filename}: archetypes is empty")
    else:
        for a in archetypes:
            if a not in CANONICAL_ARCHETYPES:
                violations.append(f"{filename}: archetype '{a}' not in canonical vocabulary {sorted(CANONICAL_ARCHETYPES)}")

    # Check keywords
    keywords = meta.get("keywords", [])
    if not keywords:
        violations.append(f"{filename}: keywords is empty")
    else:
        if len(keywords) < MIN_KEYWORDS:
            violations.append(f"{filename}: keywords has {len(keywords)} entries (min {MIN_KEYWORDS})")
        if len(keywords) > MAX_KEYWORDS:
            violations.append(f"{filename}: keywords has {len(keywords)} entries (max {MAX_KEYWORDS})")

        # Check for title-derived token overlap
        title = meta.get("title", "")
        title_tokens = tokenize(title)
        keyword_tokens = set()
        for kw in keywords:
            keyword_tokens.update(tokenize(str(kw)))
        if title_tokens and keyword_tokens:
            overlap = title_tokens & keyword_tokens
            if len(overlap) > len(title_tokens) * 0.5:
                violations.append(
                    f"{filename}: keywords have >50% overlap with title tokens "
                    f"(overlap: {sorted(overlap)})"
                )

    # Check repo_url (optional, but if present must be a valid URL)
    repo_url = meta.get("repo_url")
    if repo_url is not None:
        repo_url_str = str(repo_url).strip()
        if repo_url_str and not (repo_url_str.startswith("https://github.com/") or repo_url_str.startswith("https://")):
            violations.append(f"{filename}: repo_url must start with 'https://github.com/' or 'https://' (got '{repo_url_str}')")

    return violations


def main():
    args = sys.argv[1:]
    force = False
    if '--force' in args:
        force = True
        args.remove('--force')

    portfolio_dir = args[0] if len(args) > 0 else DEFAULT_PORTFOLIO_DIR

    if not os.path.isdir(portfolio_dir):
        print(f"Error: Portfolio directory not found: {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    all_violations = []
    md_files = sorted(f for f in os.listdir(portfolio_dir) if f.endswith('.md'))

    if not md_files:
        print(f"Error: No .md files found in {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    # Load hash cache for skip-if-unchanged optimization
    cache = _load_cache(portfolio_dir) if not force else {}
    files_to_lint = []
    skipped = 0

    for filename in md_files:
        filepath = os.path.join(portfolio_dir, filename)
        current_hash = _file_hash(filepath)
        if not force and filename in cache and cache[filename] == current_hash:
            skipped += 1
            continue
        files_to_lint.append((filename, filepath, current_hash))

    if skipped > 0:
        print(f"Lint cache: {skipped} file(s) unchanged since last successful lint - skipping.")

    if not files_to_lint:
        print(f"\n=== LINT PASSED: {len(md_files)} portfolio files clean ({skipped} cached) ===")
        sys.exit(0)

    for filename, filepath, current_hash in files_to_lint:
        violations = lint_file(filepath)
        all_violations.extend(violations)

    if all_violations:
        print(f"\n=== LINT FAILED: {len(all_violations)} violation(s) ===\n")
        for v in all_violations:
            print(f"  FAIL: {v}")
        sys.exit(1)
    else:
        # Update cache for successfully linted files
        for filename, filepath, current_hash in files_to_lint:
            cache[filename] = current_hash
        _save_cache(portfolio_dir, cache)
        print(f"\n=== LINT PASSED: {len(files_to_lint)} file(s) linted, {skipped} cached ===")
        sys.exit(0)


if __name__ == "__main__":
    main()
