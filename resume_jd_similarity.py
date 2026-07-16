"""
resume_jd_similarity.py — Cosine similarity between resume and job description.

This is now a thin shim that delegates to zvec_hybrid_search.resume_jd_similarity().
The implementation was merged into zvec_hybrid_search.py to avoid loading the
sentence-transformers model twice (once for hybrid search, once for similarity).

Usage:
    python resume_jd_similarity.py <resume_yaml_path> <jd_yaml_path>

You can also call the similarity directly via:
    python zvec_hybrid_search.py --similarity <resume_path> <jd_path>
"""
import os
import sys

from zvec_hybrid_search import resume_jd_similarity


def main():
    if len(sys.argv) < 3:
        print("Usage: python resume_jd_similarity.py <resume_yaml_path> <jd_yaml_path>")
        sys.exit(1)

    resume_path = sys.argv[1]
    jd_path = sys.argv[2]

    if not os.path.exists(resume_path):
        print(f"Error: Resume file not found: {resume_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(jd_path):
        print(f"Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)

    score = resume_jd_similarity(resume_path, jd_path)
    print(f"resume_jd_semantic_similarity: {score:.4f}")


if __name__ == '__main__':
    main()
