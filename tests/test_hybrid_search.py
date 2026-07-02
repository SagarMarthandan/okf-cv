#!/usr/bin/env python3
"""
test_hybrid_search.py — Test suite for hybrid search (OKF + Zvec score fusion).

Verifies that the hybrid search engine produces sensible rankings for:
1. Data Engineering JD with archetype boost
2. AI/RAG Developer JD with dual archetype
3. Smoke test with generic DE JD

Compares hybrid results against pure OKF results to verify Zvec semantic layer
is contributing to rankings.
"""
import os
import sys

# Ensure skill directory is on the path
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from config import DEFAULT_PORTFOLIO_DIR
from okf_portfolio_search import search_relevant_projects
from zvec_hybrid_search import hybrid_search, ingest_portfolio

PORTFOLIO_DIR = DEFAULT_PORTFOLIO_DIR

# ─── Test JDs ─────────────────────────────────────────────────────────────────

DE_JD = """
Senior Data Engineer

We are looking for a Senior Data Engineer with deep expertise in dbt, Snowflake, and Airflow.
You will build and maintain ELT pipelines, manage data warehouse architecture,
and implement medallion architecture patterns. Experience with Docker, Kubernetes,
and CI/CD pipelines is required. You should be comfortable with Python, SQL,
and incremental loading strategies using SCD Type 2.

Tech Stack: dbt, Snowflake, Apache Airflow, Docker, Kubernetes, Python, SQL, GitHub Actions
"""

AI_RAG_JD = """
AI/RAG Developer

We need an AI engineer with expertise in Retrieval-Augmented Generation (RAG),
LangChain, and LLM integration. You will build chatbots and document query systems
using FAISS, OpenAI API, and HuggingFace models. Experience with Python,
prompt engineering, and agentic AI frameworks is essential.

Tech Stack: LangChain, FAISS, OpenAI, HuggingFace, Python, RAG, LLMs
"""

GENERIC_DE_JD = """
Data Engineer

Looking for a data engineer with experience in dbt, Snowflake, and Airflow.
Must know Python and SQL. Experience with data warehouse, ETL/ELT pipelines,
and data quality testing preferred.

Tech Stack: dbt, Snowflake, Airflow, Python, SQL
"""

# ─── Expected projects ────────────────────────────────────────────────────────

EXPECTED_DE_PROJECTS = [
    "airbnb data engineering project",
    "nyc taxi analytics pipeline",
    "weather data analytics pipeline",
    "youtube e2e advanced data engineering pipeline",
]

EXPECTED_RAG_PROJECT = "retrieval-augmented generation"

# ─── Tests ────────────────────────────────────────────────────────────────────


def test_de_search_hybrid():
    """Test 1: Data Engineering search with archetype boost — hybrid mode."""
    print("\n=== Test 1: Data Engineering search (hybrid, with archetype boost) ===")

    okf_results = search_relevant_projects(
        DE_JD, PORTFOLIO_DIR, top_k=10,
        jd_primary_archetype="Data Engineering",
        jd_secondary_archetype="Analytics Engineering",
    )

    hybrid_results = hybrid_search(
        DE_JD, PORTFOLIO_DIR, top_k=10,
        jd_primary_archetype="Data Engineering",
        jd_secondary_archetype="Analytics Engineering",
    )

    print("\n  OKF-only results:")
    for p in okf_results[:5]:
        diag = p.get("_match_diagnostics", {})
        print(f"  {p['title']} (okf={diag.get('score', 0):.2f})")

    print("\n  Hybrid results:")
    for p in hybrid_results[:5]:
        diag = p.get("_match_diagnostics", {})
        print(f"  {p['title']} (okf={diag.get('okf_score', 0):.2f}, "
              f"zvec={diag.get('zvec_cosine', 0):.3f}, "
              f"fused={diag.get('fused_score', 0):.2f})")

    top3_titles = [p["title"].lower() for p in hybrid_results[:3]]
    de_hits = sum(1 for exp in EXPECTED_DE_PROJECTS if any(exp in t for t in top3_titles))

    assert de_hits >= 2, (
        f"Expected at least 2 DE projects in top-3, got {de_hits}. "
        f"Top-3: {top3_titles}"
    )
    print(f"\n  PASS: {de_hits} DE projects in top-3 (hybrid)")


def test_rag_search_hybrid():
    """Test 2: AI/RAG Developer search — hybrid mode."""
    print("\n=== Test 2: AI/RAG Developer search (hybrid) ===")

    hybrid_results = hybrid_search(
        AI_RAG_JD, PORTFOLIO_DIR, top_k=5,
        jd_primary_archetype="AI Engineer",
        jd_secondary_archetype="AI/LLMOps",
    )

    print("\n  Hybrid results:")
    for p in hybrid_results[:5]:
        diag = p.get("_match_diagnostics", {})
        print(f"  {p['title']} (okf={diag.get('okf_score', 0):.2f}, "
              f"zvec={diag.get('zvec_cosine', 0):.3f}, "
              f"fused={diag.get('fused_score', 0):.2f})")

    top1 = hybrid_results[0]["title"].lower()
    assert EXPECTED_RAG_PROJECT in top1, (
        f"Expected RAG project as #1, got: {top1}"
    )
    print(f"\n  PASS: RAG project ranked #1 (hybrid)")


def test_smoke_generic_de_hybrid():
    """Test 3: Smoke test with generic DE JD — hybrid mode."""
    print("\n=== Test 3: Smoke test — generic Data Engineer (hybrid) ===")

    hybrid_results = hybrid_search(GENERIC_DE_JD, PORTFOLIO_DIR, top_k=5)

    print("\n  Hybrid results:")
    for p in hybrid_results[:5]:
        diag = p.get("_match_diagnostics", {})
        print(f"  {p['title']} (okf={diag.get('okf_score', 0):.2f}, "
              f"zvec={diag.get('zvec_cosine', 0):.3f}, "
              f"fused={diag.get('fused_score', 0):.2f})")

    top3_titles = [p["title"].lower() for p in hybrid_results[:3]]
    de_hits = sum(1 for exp in EXPECTED_DE_PROJECTS if any(exp in t for t in top3_titles))

    assert de_hits >= 2, (
        f"Expected at least 2 DE projects in top-3, got {de_hits}. "
        f"Top-3: {top3_titles}"
    )
    print(f"\n  PASS: {de_hits} DE projects in top-3 (hybrid smoke test)")


def test_zvec_contributes():
    """Test 4: Verify Zvec semantic layer is contributing (zvec_cosine > 0 for all results)."""
    print("\n=== Test 4: Zvec semantic contribution check ===")

    hybrid_results = hybrid_search(DE_JD, PORTFOLIO_DIR, top_k=5)

    all_have_zvec = all(
        p.get("_match_diagnostics", {}).get("zvec_cosine", 0) > 0
        for p in hybrid_results
    )

    assert all_have_zvec, "Some results have zero Zvec cosine similarity"

    print(f"  All {len(hybrid_results)} results have non-zero Zvec cosine similarity")
    print(f"\n  PASS: Zvec semantic layer is contributing to all results")


if __name__ == "__main__":
    print(f"Portfolio Directory: {PORTFOLIO_DIR}")

    # Ensure Zvec database is ingested before tests
    print("\n--- Ingesting portfolio into Zvec (first run may take a few seconds) ---")
    ingest_portfolio(PORTFOLIO_DIR, force_recreate=False)
    print("--- Ingestion complete ---")

    test_de_search_hybrid()
    test_rag_search_hybrid()
    test_smoke_generic_de_hybrid()
    test_zvec_contributes()

    print("\n=== Hybrid Search Verification: ALL TESTS PASSED ===")
