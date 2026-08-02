"""
okf_utils.py — Shared utilities for OKF-CV pipeline scripts.

Extracted from okf_portfolio_search.py, okf_lint.py, and okf_learn.py to
eliminate triple-duplicated tokenize(), file_hash(), and frontmatter parsing.
"""
import hashlib
import re
from typing import Dict, Set, Optional, Tuple

import yaml


# ─── Stopword sets ────────────────────────────────────────────────────────────

# Minimal stopwords — used by okf_portfolio_search for JD/project matching.
# Only removes the most common function words to keep matching broad.
MINIMAL_STOPWORDS = frozenset({
    'and', 'the', 'for', 'with', 'a', 'an', 'to', 'in', 'of', 'on', 'at', 'by', 'is',
})

# Extended stopwords — used by okf_learn for keyword extraction.
# Removes function words, common verbs, and generic job-description filler
# to avoid enriching portfolio keywords with noise.
EXTENDED_STOPWORDS = frozenset({
    'and', 'the', 'for', 'with', 'a', 'an', 'to', 'in', 'of', 'on',
    'at', 'by', 'is', 'or', 'as', 'we', 'you', 'our', 'your', 'this',
    'that', 'will', 'be', 'are', 'have', 'has', 'was', 'were', 'it',
    'from', 'their', 'they', 'but', 'not', 'can', 'all', 'any', 'if',
    'so', 'do', 'does', 'did', 'about', 'into', 'than', 'then', 'also',
    'more', 'most', 'some', 'such', 'only', 'very', 'over', 'under',
    'up', 'down', 'out', 'off', 'above', 'below', 'between', 'through',
})


# ─── Tokenize ─────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r'\b\w+\b')


def tokenize(
    text: str,
    stopwords: Optional[frozenset] = None,
    min_length: int = 0,
) -> Set[str]:
    """Extract lowercase alphanumeric tokens from text.

    Args:
        text: Input text to tokenize.
        stopwords: Optional set of stopwords to exclude. Pass None for no
            stopword filtering, MINIMAL_STOPWORDS for light filtering, or
            EXTENDED_STOPWORDS for aggressive filtering.
        min_length: Minimum token length (exclusive). 0 = no minimum.
            okf_learn uses min_length=2 to drop 1-2 char tokens.

    Returns:
        Set of lowercase tokens.
    """
    if not text:
        return set()
    words = _TOKEN_RE.findall(text.lower())
    if stopwords is not None:
        return {w for w in words if w not in stopwords and len(w) > min_length}
    return {w for w in words if len(w) > min_length}


# ─── File hashing ─────────────────────────────────────────────────────────────

def file_hash(filepath: str) -> str:
    """SHA256 of file content for change detection.

    Used by okf_lint (lint cache) and zvec_hybrid_search (Zvec hash index).
    """
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


# ─── YAML frontmatter parsing ─────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)


def parse_frontmatter(content: str) -> Tuple[Optional[dict], str]:
    """Split a markdown file into (frontmatter_dict, body_text).

    Returns (None, content) if no frontmatter block is found.
    Returns ({}, body) if frontmatter exists but fails to parse as YAML.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None, content.strip()

    yaml_block = match.group(1)
    body = match.group(2).strip()
    try:
        meta = yaml.safe_load(yaml_block)
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body
