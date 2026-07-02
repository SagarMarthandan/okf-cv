"""
test_okf_search.py — Test runner for the OKF Portfolio Search tool.

Performs search queries against the OKF portfolio directory to verify:
  1. Data Engineering relevance ranking (with archetype boost)
  2. AI/RAG relevance ranking
  3. Smoke test: generic "Data Engineer with dbt, Snowflake, Airflow" JD
     asserts top-3 results include expected projects
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from okf_portfolio_search import search_relevant_projects, DEFAULT_PORTFOLIO_DIR


def main():
    print(f"Portfolio Directory: {DEFAULT_PORTFOLIO_DIR}")
    if not os.path.exists(DEFAULT_PORTFOLIO_DIR):
        print(f"Error: OKF portfolio directory not found at {DEFAULT_PORTFOLIO_DIR}", file=sys.stderr)
        sys.exit(1)

    # --- Test 1: Data Engineering with archetype boost ---
    print("\n=== Test 1: Data Engineering search (with archetype boost) ===")
    jd_de = (
        "Looking for a Senior Data Engineer experienced in designing ELT/ETL pipelines, "
        "orchestration using Apache Airflow or Dagster, data modeling with dbt, and "
        "warehousing using BigQuery, Snowflake, or Databricks."
    )
    try:
        results = search_relevant_projects(
            jd_de, DEFAULT_PORTFOLIO_DIR, top_k=3,
            jd_primary_archetype="Data Engineering",
        )
        titles = [r['title'].lower() for r in results]
        assert any("data engineering" in t or "elt" in t or "dbt" in t or "airbnb" in t for t in titles), \
            f"DE query assertion failed. Got titles: {titles}"
        for idx, match in enumerate(results):
            print(f"  {idx+1}. {match['title']} (score={match.get('_match_diagnostics', {}).get('score', 0):.2f})")
    except Exception as e:
        print(f"Test 1 failed: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Test 2: AI / RAG Developer ---
    print("\n=== Test 2: AI / RAG Developer search ===")
    jd_ai = (
        "We are hiring an AI Engineer to build Retrieval-Augmented Generation (RAG) systems, "
        "working with vector databases, embeddings, and large language models (LLMs)."
    )
    try:
        results = search_relevant_projects(
            jd_ai, DEFAULT_PORTFOLIO_DIR, top_k=3,
            jd_primary_archetype="AI Engineer",
            jd_secondary_archetype="AI/LLMOps",
        )
        titles = [r['title'].lower() for r in results]
        assert any("retrieval-augmented" in t or "rag" in t for t in titles), \
            f"AI query assertion failed. Got titles: {titles}"
        for idx, match in enumerate(results):
            print(f"  {idx+1}. {match['title']} (score={match.get('_match_diagnostics', {}).get('score', 0):.2f})")
    except Exception as e:
        print(f"Test 2 failed: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Test 3: Smoke test — generic Data Engineer JD ---
    print("\n=== Test 3: Smoke test — generic Data Engineer (dbt, Snowflake, Airflow) ===")
    jd_smoke = (
        "Data Engineer with dbt, Snowflake, Airflow, Docker, PostgreSQL. "
        "Build and orchestrate ELT pipelines, transform data, and maintain data quality."
    )
    expected_substrings = [
        "airbnb",
        "weather",
        "youtube",
        "nyc",
    ]
    try:
        results = search_relevant_projects(
            jd_smoke, DEFAULT_PORTFOLIO_DIR, top_k=3,
            jd_primary_archetype="Data Engineering",
        )
        titles = [r['title'].lower() for r in results]
        # At least 2 of the expected DE projects should appear in top-3
        matches = sum(1 for expected in expected_substrings if any(expected in t for t in titles))
        assert matches >= 2, \
            f"Smoke test failed: expected at least 2 of {expected_substrings} in top-3. Got: {titles}"
        for idx, match in enumerate(results):
            print(f"  {idx+1}. {match['title']} (score={match.get('_match_diagnostics', {}).get('score', 0):.2f})")
    except Exception as e:
        print(f"Smoke test failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n=== OKF Search Verification: ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
