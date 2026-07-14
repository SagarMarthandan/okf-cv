"""
okf_lint.py — Frontmatter linter for OKF portfolio files.

Validates that every portfolio .md file in okf/portfolio/ has clean, well-formed
YAML frontmatter. Fails loud with the offending file + field if any rule is violated.

Usage:
    python okf_lint.py [portfolio_dir]
"""
import os
import re
import sys
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
    portfolio_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORTFOLIO_DIR

    if not os.path.isdir(portfolio_dir):
        print(f"Error: Portfolio directory not found: {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    all_violations = []
    md_files = sorted(f for f in os.listdir(portfolio_dir) if f.endswith('.md'))

    if not md_files:
        print(f"Error: No .md files found in {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    for filename in md_files:
        filepath = os.path.join(portfolio_dir, filename)
        violations = lint_file(filepath)
        all_violations.extend(violations)

    if all_violations:
        print(f"\n=== LINT FAILED: {len(all_violations)} violation(s) ===\n")
        for v in all_violations:
            print(f"  FAIL: {v}")
        sys.exit(1)
    else:
        print(f"\n=== LINT PASSED: {len(md_files)} portfolio files clean ===")
        sys.exit(0)


if __name__ == "__main__":
    main()
