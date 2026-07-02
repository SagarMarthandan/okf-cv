# OKF Pipeline Improvement Plan

> **Note (v23):** This plan was the roadmap for building OKF as a standalone
> replacement for Zvec. As of v23, the pipeline uses a **hybrid approach**
> (`zvec_hybrid_search.py`) that combines OKF phrase matching with Zvec
> semantic embeddings via score fusion. The phases below were completed in
> v22; the "drop Zvec deps" guidance in Phase 5 is superseded — Zvec is now
> a first-class dependency again. See README.md v23 changelog for details.

> Goal: Make the `okf-cv` pipeline's deterministic, metadata-driven project
> retrieval superior to `yaml-cv-pipeline`'s Zvec semantic embedding search on
> every axis: retrieval accuracy, speed, debuggability, and dependency
> footprint.

## Source of Truth for Frontmatter Curation

The canonical, fully-detailed project descriptions live in:

```
C:\Users\sagar\Documents\YAML-CV\Base Files\Repo Info\repo info.md
```

This single master file contains the rich, human-curated markdown body for
every project (tech stack tables, architecture diagrams, workflow narratives).
It is the **authoritative source** for correcting the broken frontmatter in
`okf/portfolio/*.md`. Every frontmatter field rewritten in Phase 1 must be
derived from the corresponding section in this file, not invented.

Workflow for each OKF portfolio file:
1. Locate the matching `# <Project Title>` section in `repo info.md`.
2. Read the "Tech Stack" table / "Quick Summary" / opening prose.
3. Rewrite `technologies`, `keywords`, `archetypes`, and `description`
   frontmatter to reflect what `repo info.md` actually says the project does.

---

## Phase 1: Frontmatter Curation (data layer)

Highest-leverage fix. OKF's scorer weights `technologies` (x3), `keywords`
(x4), `archetypes` (x3), and `description` (x1). Right now those fields are
noisy, empty, or wrong across the 14 portfolio files, so the scorer has
garbage input.

### 1.1 Audit pass (all 14 files in `okf/portfolio/`)

For each file, produce a corrected frontmatter block. Rules:

- **`technologies`**: comma-separated, canonical-cased, **only real
  tools/frameworks**. Pull the true stack from the "Tech Stack" table in
  `repo info.md`, not from alt-text or labels. Strip leaked values
  (`ER Diagram`, `ATS Resume Pipeline App Screenshot 1`, `2025`,
  `Project Status:`).
- **`keywords`**: 6-12 JD-relevant terms per project, **multi-word phrases
  allowed** (`data build tool`, not `dbt` alone; `medallion architecture`,
  `incremental loading`, `slowly changing dimensions`). These should be terms
  a recruiter or ATS would write in a JD for this kind of role, not title
  tokens.
- **`archetypes`**: prune to **1-2 accurate labels** from the canonical list
  used in Step 1 (`Data Engineering`, `Analytics Engineering`, `Data Analyst`,
  `AI Engineer`, `AI/LLMOps`, `Agentic/Automation`, `ML Engineering`,
  `Backend/Platform Engineering`). Remove wrong tags (e.g. F1 ELT project must
  not carry `AI Engineer` or `Agentic/Automation`).
- **`description`**: one tight sentence (<=200 chars) capturing the project's
  core capability, derived from `repo info.md`'s opening prose. Keyword-dense
  but human-readable.

### 1.2 Specific known fixes

| File | Current problem | Fix (source: `repo info.md`) |
|---|---|---|
| `f1_ingestion` | `technologies: ER Diagram` | `Azure Data Factory, Databricks, Spark, Delta Lake, ADLS, Azure Key Vault, PySpark, Airflow` |
| `ergast_formula_1` | `technologies: ''` | `Databricks, Medallion Architecture, Delta Lake, Spark SQL, PySpark` |
| `sql_practice` | `technologies: ''` | `SQL, PostgreSQL, Window Functions, CTEs, Query Optimization` |
| `ats_resume_pipeline` | image alt-text in technologies | `Streamlit, LaTeX, OpenAI API, PowerShell, Python` |
| `youtube_e2e` | `Project Status:` leaked | `Airflow, Docker, PostgreSQL, dbt, GitHub Actions, DBeaver` |
| `nyc_taxi` | `2025` as a tech | `Airbyte, Airflow, BigQuery, Docker, Terraform, Python, GitHub Actions` |
| `f1_ingestion` archetypes | `AI Engineer, Agentic/Automation` | `Data Engineering` only |

The remaining 7 files need the same audit. Verify each against its
`repo info.md` section even if no obvious breakage was found in the initial
grep.

### 1.3 Canonical archetype vocabulary

Pin allowed archetype strings to exactly the 8 used in Step 1's archetype
detection. Add a validator (Phase 4) that rejects any frontmatter archetype
not in this list, so typos like `Data Eng` or `AI/LLM Ops` can't silently
fail to match.

---

## Phase 2: Scoring Algorithm Rewrite (algorithm layer)

The current `search_relevant_projects` is a flat weighted token-overlap sum.
Four weaknesses to fix.

### 2.1 Multi-word phrase matching

**Problem**: `tokenize()` splits on `\b\w+\b`, so
`keywords: [data build tool]` becomes `{data, build, tool}` and matches any JD
containing the word "data" — false positives everywhere.

**Fix**: Replace token-set intersection with **phrase-level matching**. For
each keyword/technology/archetype phrase, check if the phrase (as a normalized
substring or token sequence) appears in the JD. Score per-phrase, not
per-token. Keep single-word phrases working too.

### 2.2 Archetype-boosted scoring using JD archetype signal

**Problem**: The scorer only sees raw JD text. But Step 1 already computes
`role_archetype.primary` (and optional `secondary`) — the single strongest
signal for which projects fit. This signal is currently thrown away.

**Fix**: Extend the OKF search script's CLI to accept the archetype from
`ATS_Report.yaml`:

```powershell
python "okf_portfolio_search.py" "Job_Description.yaml" "project_info.md" "ATS_Report.yaml"
```

When a project's `archetypes` list contains the JD's primary archetype, apply
a **large flat boost** (e.g. +10, bigger than any token-overlap sum).
Secondary archetype match gets a smaller boost (+5). This makes archetype
alignment the dominant ranking signal, which is exactly right for
role-targeted retrieval.

Update `01_ats_and_jd_archival.md` Step 1 to pass `ATS_Report.yaml` to the
search command after the ATS report is written.

### 2.3 Score normalization

**Problem**: A long JD has more tokens, so token-overlap scores scale with JD
length, not with actual relevance. Two projects can have identical relevance
but different scores because of JD verbosity.

**Fix**: Normalize the token-overlap component by the project's total metadata
token count (Jaccard-style) so a project with 50 keywords doesn't
automatically outscore one with 8 well-chosen keywords. The archetype boost
stays unnormalized (it's a binary signal).

### 2.4 Tiebreaker

**Problem**: Ties break alphabetically by title — arbitrary and can sink a
strong project.

**Fix**: Tiebreaker = number of archetype matches (desc), then number of
technology matches (desc), then alphabetical. This surfaces projects that
align on multiple structured signals.

### 2.5 Keep top_k configurable

Currently hardcoded to 4. Make it a CLI arg or read from config so Step 1's
"3 or 4 if score improves" directive can actually drive it.

---

## Phase 3: Distill Output Enrichment (output layer)

`distill_project` currently emits only `title + description + Tech:
<technologies>`. Zvec's distill extracts the first prose paragraph and first
tech-stack line from the body, which is richer. OKF should do better because
it has structured metadata.

### 3.1 Enrich distill output

Emit:
- Title
- Description (from frontmatter — already cleaner than Zvec's first-paragraph
  heuristic)
- `Tech: <technologies>` (canonical list)
- `Archetypes: <archetypes>` (so Step 2 can see role alignment at a glance)
- **First 1-2 sentences of the body's "Quick Summary" or opening paragraph**
  as a fallback context block, since the body often has detail the frontmatter
  description omits.

This gives Step 2's resume rewriter more signal than Zvec's distill while
staying structured.

### 3.2 Add a relevance score line

Include the match score and which signal drove it (e.g.
`Match: archetype=Data Engineering, 4 tech overlaps`) as a comment in
`project_info.md`. This makes the retrieval debuggable — something Zvec can't
offer cleanly. Step 2 ignores comments, so it's free observability.

---

## Phase 4: Validation & Guardrails (regression prevention)

Without this, the frontmatter will rot again and OKF silently degrades back
to its current state.

### 4.1 Frontmatter linter script

New script `okf_lint.py` that fails the pipeline if any portfolio file has:
- Empty `technologies` or `description`
- `technologies` containing non-tool tokens (maintain a denylist: `2025`,
  `Project Status`, `Screenshot`, `ER Diagram`, image alt-text patterns)
- `archetypes` containing a label not in the canonical 8-archetype vocabulary
- `keywords` with fewer than 4 or more than 15 entries
- `keywords` that are pure title-derived tokens (compare against tokenized
  title, flag if >50% overlap)

Run this in Step 1's pre-scoring dependency check, right after `pip install`.
Fail loud with the offending file + field.

### 4.2 Smoke test

Add a tiny test JD (e.g. a generic "Data Engineer with dbt, Snowflake,
Airflow" prompt) and assert the top-3 results include the expected projects
(`airbnb_data_engineering_project_dbt_snowflake_dagster`,
`weather_data_analytics_pipeline`,
`youtube_e2e_advanced_data_engineering_pipeline`). Run after any frontmatter
or scorer change. This catches both curation regressions and scorer bugs.

---

## Phase 5: Dependency & Config Cleanup

### 5.1 Drop heavy deps from requirements

OKF's `requirements.txt` should **not** include `zvec`,
`sentence-transformers`, `torch`, or `huggingface-hub`. OKF's whole pitch is
lightweight + offline + no model download. Verify the requirements file only
lists `pyyaml`, `reportlab`, `pypdf`. This makes OKF install in seconds vs
Zvec's multi-minute model fetch.

### 5.2 Config consistency

Confirm `config.py` in the okf-cv skill points at `okf/portfolio/` and the
okf base files, with no leftover Zvec paths (`DEFAULT_DB_PATH`,
`EMBEDDING_MODEL_NAME`, `EMBEDDING_DIMENSION` should be absent or unused).

---

## Execution Order

1. **Phase 1** (frontmatter curation, sourced from `repo info.md`) — do this
   first; it's the biggest win and the scorer rewrite is meaningless without
   clean data.
2. **Phase 4.1** (linter) — immediately after, so the curation can't regress.
3. **Phase 2** (scorer rewrite) — with clean data, the archetype boost +
   phrase matching + normalization lands the accuracy jump.
4. **Phase 3** (distill enrichment) — small, do alongside Phase 2.
5. **Phase 4.2** (smoke test) — validates the combined result.
6. **Phase 5** (deps) — cleanup, last.

---

## Success Criteria

Run both pipelines on the same 3 JDs (one Data Engineering, one AI/LLMOps,
one Analytics Engineering) and compare:

- **Retrieval relevance**: top-4 project lists judged against the JD. OKF
  should match or beat Zvec on all 3.
- **Runtime**: OKF should be <2s vs Zvec's model-load + embed time (10-60s).
- **Debuggability**: OKF's `project_info.md` shows match reasons; Zvec shows
  only cosine scores.
- **Install**: OKF `pip install` completes without network access for models.

If OKF wins on all four, it's the superior pipeline and Zvec becomes the
fallback.

---

## Phase 6: Self-Learning Loop (Future)

### Goal

After each application run, the pipeline extracts useful keywords from the
processed JD and enriches the portfolio files' frontmatter. Over time, the
knowledge base becomes better tuned to real-world JDs without manual
intervention.

### Design: `okf_learn.py`

**Trigger:** Post-Step-3 (after cover letter compiles, before folder sort).

**Inputs:**
- `Job_Description.yaml` (from the application folder)
- `ATS_Report.yaml` (contains `role_archetype` for context)
- `project_info.md` (contains the matched project titles + match diagnostics)

**Algorithm:**

1. **Extract JD terms:** Tokenize the JD text. Filter to meaningful terms
   using the existing `tokenize()` + stopword removal. Also extract multi-word
   phrases (bigrams/trigrams) that appear in the JD and match known tech
   patterns (e.g., "data warehouse", "ci/cd", "star schema").

2. **For each matched project** (identified from `project_info.md` titles):
   - Read the full portfolio `.md` file (body + frontmatter)
   - Find JD terms that appear in the project's **body or description or
     technologies** but are **not already in its `keywords` list**
   - These are "genuine but untagged" terms — the project genuinely covers
     the topic (it's in the body) but the keyword wasn't curated
   - Cap: Add at most 3 new keywords per run per project
   - Respect the 15-keyword maximum (linter enforced)

3. **Write changes:**
   - Append new keywords to the portfolio file's YAML frontmatter
   - Preserve existing keywords, formatting, and body content
   - Run `okf_lint.py` after writes to validate

4. **Log to `okf/learning_log.json`:**
   ```json
   {
     "timestamp": "2025-07-01T21:32:00",
     "jd_source": "Applications/2025/07/01/Acme — Data Engineer/",
     "role_archetype": "Data Engineering",
     "changes": [
       {
         "file": "okf/portfolio/nyc_taxi_analytics_pipeline_2025.md",
         "added_keywords": ["data warehousing", "gcp"],
         "reason": "JD mentioned 'data warehousing' and 'gcp'; terms found in project body but not in keywords"
       }
     ]
   }
   ```

5. **Idempotency:** If a keyword already exists in the file's keyword list,
   skip it. If the same JD is processed again, no new keywords are added.

### Safeguards

- **No hallucinated keywords:** Only terms that appear in the project's own
  body/description/technologies are eligible. The script never invents
  keywords from JD context alone.
- **Keyword cap:** 15 keywords max per file (linter enforced). If the file
  is at cap, no new keywords are added.
- **Per-run cap:** Max 3 new keywords per project per run to prevent sudden
  bloat from a single verbose JD.
- **Audit trail:** Every change logged to `learning_log.json` with timestamp,
  JD source, and exact keywords added. Human can review and revert.
- **Linter gate:** `okf_lint.py` runs after enrichment. If any violation
  occurs (e.g., keyword count exceeds 15), the change is rolled back.

### Integration Points

- **`03_cover_letter.md`:** Add Step 4 — "Run `okf_learn.py` with the
  application folder path to enrich portfolio keywords from this JD."
- **`SKILL.md`:** Add `okf_learn.py` to pipeline script structure and
  completion checklist.
- **`organize_applications.py`:** Runs after `okf_learn.py` (unchanged).

### Why Not Auto-Update Archetypes/Technologies?

Keywords are the safest field for auto-enrichment because:
- They're freeform strings (no canonical vocabulary to violate)
- They have a clear cap (15) and quality check (linter)
- They directly impact scoring (x4 weight) so enrichment has immediate ROI

Archetypes use a **canonical vocabulary** — auto-adding would risk
invalid tags. Technologies should match actual tools used — auto-adding
from JD text could introduce false claims. Keywords are the sweet spot.

### Expected Impact

After 10-20 applications:
- Portfolio files accumulate JD-relevant keywords that were missing from
  manual curation
- Retrieval relevance improves for niche JDs that use domain jargon not
  in the original `repo info.md`
- The knowledge base adapts to market terminology trends (e.g., new tool
  names, emerging skill phrases)

### Risk: Overfitting

If the same company type is applied to repeatedly, keywords may overfit
to that company's JD style. Mitigation: the per-run cap (3 keywords) and
the 15-keyword ceiling naturally limit overfitting. The learning log
allows manual review and pruning if needed.
