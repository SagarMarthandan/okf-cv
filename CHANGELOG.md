[//]: # (DEVELOPER DOCUMENTATION ONLY — not part of agent runtime context. Do not read this file during pipeline execution.)
# Changelog

All notable changes to the okf-cv pipeline are documented here.
See [README.md](README.md) for architecture, setup, and usage.

---

## v28.8 — Project Header: Tools Removed + LaTeX Summary on New Line
**Files:** `renderers/resume_latex.py`, `renderers/resume_reportfallback.py`, `README.md`, `CHANGELOG.md`

**Motivation:** The project header in both renderers displayed the tools list inline with the project name (e.g. `RAG PDF-Abfragesystem [GitHub] LangChain,FAISS,OpenAI,PyPDF2,Python`), which cluttered the header and was inconsistent with the desired clean layout. Additionally, in the LaTeX version the project summary (bullets) started on the same line as the project name instead of on the next line.

**Changes:**
- `renderers/resume_reportfallback.py`: Removed the `tools` field read, the compressed-tools formatting logic (NBSP replacement, adaptive font sizing), and the tools `<font>` span from the project header paragraph. The header now renders only the project name + optional `[GitHub]` link.
- `renderers/resume_latex.py`: Removed the `tools`/`tools_str` lines from the project loop and dropped `\projectTools{Tools: ...}` from the `item_tex` template. Added `\par` after `\resumeProject{...}` so the project summary (itemize block) starts on the next line. Removed the now-unused `\newcommand{\projectTools}` definition from the preamble.
- The parseability audit in `resume_latex.py` (lines 57-62) still reads `tools` from the YAML to verify those keywords appear somewhere in the rendered PDF — this verification logic is unchanged.
- Updated `README.md` Step 2 "LaTeX Compilation & Project Format Polish" bullet to reflect that tools are no longer displayed in the project header and that project names render on their own line with the summary starting on the next line.

**Behavior:** Both renderers now produce identical project headers — project name + optional `[GitHub]` link only, no tools. The LaTeX version forces the summary onto the next line via `\par`. Tools remain in the YAML schema for the parseability keyword-recovery audit.

---

## v28.5 — Self-Refresh Trigger + SKILL.md Self-Refresh Section + Stale Planning Docs Removed
**Files:** `SKILL.md`, `README.md`, `CHANGELOG.md`, `IMPLEMENTATION_PLAN.md` (deleted), `OKF_IMPROVEMENT_PLAN.md` (deleted)

**Motivation:** After pulling updates or switching branches, the skill metadata in the active CLI/harness skill store can be stale. Added a `refresh` trigger keyword and a Self-Refresh procedure so the user can reload the skill into the current CLI's skill store on demand. Also removed two completed/stale planning docs that were no longer active references.

**Changes:**
- Added `"refresh"` to the trigger keywords in `SKILL.md` frontmatter description.
- Appended a `## Self-Refresh` section to `SKILL.md` with a 4-step procedure: identify the CLI/harness, copy `SKILL.md` (ground truth) to the CLI's active skill store path, confirm the load via the CLI's skill resolution mechanism, and ingest all supporting `.md` files in `skills/okf-cv/` to load the full pipeline into context. Closes with "Do not perform any other actions."
- Added a `### Self-Refresh` subsection to `README.md` under "How to Run the Pipeline" documenting the `refresh okf-cv` command and the 4-step procedure.
- Deleted `IMPLEMENTATION_PLAN.md` (monoculture countermeasures plan — all features integrated into the pipeline in v22/v23) and `OKF_IMPROVEMENT_PLAN.md` (OKF improvement plan — header note self-declared phases completed in v22, superseded by hybrid approach). Updated `README.md` directory tree to note their removal.

**Behavior:** Typing `refresh okf-cv` (or similar) triggers a metadata/context reload only — it does not run the pipeline or modify any application files. Historical CHANGELOG references to the deleted planning docs remain as-is (they document past state).

---

## v28.4 — Dynamic Section Ordering
**Files:** `renderers/resume_common.py`, `renderers/resume_latex.py`, `renderers/resume_reportfallback.py`, `02_resume_and_visual_audit.md`, `README.md`, `CHANGELOG.md`

**Motivation:** Section order was hardcoded in both renderers (LaTeX joined a fixed list of section strings; ReportFallback appended blocks to `story` in a fixed sequence). This made per-application reordering impossible without code changes.

**Changes:**
- Added `DEFAULT_SECTION_ORDER` list and `get_section_order(data)` helper to `renderers/resume_common.py`. The helper reads an optional top-level `section_order` key from the resume YAML, validates keys against the known set (drops unknown keys), and falls back to the default order when the key is absent or not a list.
- Refactored `renderers/resume_latex.py`: section strings are now collected into a `section_map` dict and emitted in `get_section_order(data)` order instead of a hardcoded list.
- Refactored `renderers/resume_reportfallback.py`: each section's rendering logic extracted into an inner function (`render_summary`, `render_technical_skills`, `render_projects`, `render_professional_experience`, `render_education`, `render_spoken_languages`) returning a list of flowables. The main body iterates `get_section_order(data)` and dispatches through a `section_renderers` dict.
- Updated `02_resume_and_visual_audit.md` spec: documented the `section_order` YAML override and that both renderers share the same source of truth.
- Updated `README.md` Step 2 with a Dynamic Section Ordering bullet.

**Behavior:** Default order unchanged (Summary → Skills → Projects → Experience → Education → Languages). Opt-in override via `section_order` in the resume YAML — the model/harness can emit it when explicitly asked to reorder; otherwise the default applies.

---

## v28 — Pipeline Optimizations + Archetype-Specific Base Resumes + Photo Removal
**Files:** `renderers/resume_latex.py`, `renderers/resume_reportfallback.py`, `yaml_to_pdf.py`, `okf_lint.py`, `okf_learn.py`, `config.py`, `sync_to_obsidian.py`, `resume_parseability.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `SKILL.md`, `README.md`, `CHANGELOG.md`, `.gitignore`, `okf/base_files/english/resume_data_engineer.md` (new), `okf/base_files/english/resume_data_analyst.md` (new), `okf/base_files/english/resume_analytics_engineer.md` (new), `okf/base_files/english/resume_ai_data_engineer.md` (new), `okf/photo/` (deleted)

**Motivation:** Eliminates redundant compilation, auditing, and per-run work that produced no output change. Introduces archetype-specific base resumes to maximize pre-rewrite ATS scores. Removes photo embedding from the pipeline (added manually via PDF editor). Same outputs, less wasted compute, higher starting scores.

**Archetype-Specific Base Resumes:**
- Added 4 archetype-specific base resumes in `okf/base_files/english/`: `resume_data_engineer.md`, `resume_data_analyst.md`, `resume_analytics_engineer.md`, `resume_ai_data_engineer.md`. Each is focused on its archetype's keywords, tools, and projects to score 87-92 pre-rewrite (vs 55-70 when using a single Data Engineer base for cross-archetype JDs).
- Step 1 now detects the JD's primary role archetype and loads the matching base resume. Falls back to the generic `resume.md` for unmatched archetypes.
- German equivalents follow the `_de` suffix convention (e.g. `resume_data_engineer_de.md`).

**Photo Embedding Removed:**
- Removed all photo embedding code from `renderers/resume_latex.py`: photo copy logic, `_cleanup_photo()` function, `has_photo`/`photo_filename` return values, and the `shutil` import. The LaTeX header is now always the no-photo variant (name + contact only).
- Removed `photo_path` from the `Resume.yaml` schema in `02_resume_and_visual_audit.md`. Removed `header_photo_integration` from the visual layout audit checklist.
- Removed `DEFAULT_PHOTO_DIR` from `config.py`. Removed `okf/photo/` folder and its `.gitignore` entry.
- Updated `SKILL.md` (removed photo directory reference and error handling step) and `README.md` (removed photo from directory tree).
- Photos are now added manually via a PDF editor after the pipeline completes.

**Dependency Check 24hr Cache:**
- The import probe in Step 1 section 0b.1 is now cached for 24 hours via `okf/.dep_check.json`. On each run, the pipeline checks the cache timestamp — if less than 24 hours old, the import probe is skipped entirely. If older or missing, the probe runs and the timestamp is updated. Added `okf/.dep_check.json` to `.gitignore`.

**Location Web Search Cache:**
- Added persistent location cache (`okf/.location_cache.json`) to `config.py`. When a job location isn't in the static geocode table, the pipeline checks the cache before doing a web search. If the location was previously resolved via web search, the cached result is returned instantly. After a web search resolves a new location, `cache_location_result()` stores it for future runs. Geography doesn't change, so cache entries are permanent. Step 1 section 5 updated with cache lookup + cache write instructions.

**Font Registration Disk Cache:**
- Added disk cache (`okf/.font_cache.json`) for font path resolution in `renderers/utils.py`. Each `yaml_to_pdf.py` invocation is a new Python process that previously re-walked the filesystem to find TTF font files. Now the resolved font paths are cached to disk — subsequent processes skip the directory scan and go straight to registering the known paths with ReportLab. Cache is validated by checking that the font files still exist. Saves ~0.5-1 second per PDF compilation (2-3 compiles per application).

**ReportFallback Font Size + Education Fixes:**
- Increased all font sizes in `renderers/resume_reportfallback.py` by 1pt (body text 10→11pt, section titles 11→12pt, name 22→23pt, contact 8.5→9.5pt, adaptive project tools 7.5/7.0/6.5→8.5/8.0/7.5pt).
- Education section: university names now use non-breaking spaces to prevent mid-name wrapping. Adaptive font size (10pt→8.5pt based on combined degree+university length) ensures each education entry fits on one line. Left column widened from 387pt→400pt.

**Phase 1 — Duplicate Compilation & Auditing Elimination:**
- **1.1 Dedupe parse-integrity work:** Removed `_write_parse_integrity_report` from `renderers/resume_latex.py`. The in-renderer audit still runs and auto-recovers to ReportLab on failure (fallback trigger preserved), but no longer writes `Layout_Audit_Report.yaml` — the standalone `resume_parseability.py` (Step 2 Section 6) is the sole writer of parse-integrity reports.
- **1.2 ATS Report single recompile:** Removed the duplicate `ATS_Report.pdf` recompile from Step 2 Section 5. The recompile now happens once in Step C (after the post-rewrite score is written to YAML). Section 5 keeps the score-delta YAML write only.
- **1.3 `--tex-only` flag:** Added `--tex-only` flag to `yaml_to_pdf.py` (resume type, LaTeX mode only). Writes the `.tex` source file without running pdflatex. Step A of the resume pipeline now uses `--tex-only` in LaTeX mode, avoiding a throwaway pdflatex run (the PDF gets replaced when the agent edits the `.tex` in Step B and recompiles in Step C). Refactored `resume_latex.py` to extract `_generate_resume_tex()` helper shared by both `create_resume_pdf_latex` and `create_resume_pdf_latex_tex_only`. ReportFallback mode is unchanged (no `.tex` polish step).

**Phase 2 — Per-Run Work Guards:**
- **2.1 Conditional pip install with 24hr cache:** Replaced the unconditional `pip install -r requirements.txt` in Step 1 with a cached import probe. The probe runs once, then the result is cached in `okf/.dep_check.json` for 24 hours. Subsequent runs within 24hrs skip the probe entirely. Only runs `pip install` if an import actually fails.
- **2.4 Location web search cache:** Added `okf/.location_cache.json` to cache web-search-resolved job locations. Locations not in the static geocode table are cached after first web search — future applications with the same location skip the web search entirely. Permanent cache (geography doesn't change).
- **2.5 Font registration disk cache:** Added `okf/.font_cache.json` to cache resolved font file paths. Each new Python process previously re-walked the filesystem to find TTF files — now it reads cached paths and goes straight to ReportLab registration. Saves ~0.5-1s per PDF compilation.
- **2.2 Conditional lint with hash cache:** `okf_lint.py` now uses a content-hash cache (`okf/.lint_cache.json`) to skip files whose content hasn't changed since the last successful lint. `okf_learn.py` invalidates cache entries for files it modifies. Added `--force` flag to ignore the cache and lint all files. First run after deploy does a full lint (no cache yet).
- **2.3 Diversity audit removed from per-application pipeline:** Removed the automatic `okf_diversity_audit.py` run from Step 1 section 0c. The script is now a standalone weekly review tool (documented in README). The prospective monoculture features (application source prompt, weak-tie warning, contact weaving in cover letter) remain in the pipeline.

**Phase 3 — Static Geocode Lookup:**
- **3.1 Candidate-city geocode table:** Added `JOB_LOCATION_TO_CANDIDATE_CITY` dict and `nearest_candidate_city()` function to `config.py`. Maps common German job locations to their nearest candidate city (Kiel, Frankfurt, Berlin, Köln). Step 1 section 5 now checks the static table first, falling back to web search only for unknown locations. Remote/unspecified locations default to Kiel.

**Phase 4 — Incremental Obsidian Sync:**
- **4.1 Targeted sync mode:** Added optional positional argument to `sync_to_obsidian.py`: `sync_to_obsidian.py <application_folder>`. When given, syncs only that application's notes and patches the relevant entity and index notes (append with dedup). Much faster than a full rebuild for a single new application. No-arg call still does a full rebuild. Added `--full` flag to force full rebuild even when a target is given.
- **4.2 Folder sort folded into sync:** Added `--sort` flag to `sync_to_obsidian.py`. After a successful targeted sync, the folder is moved into the `Applications/YYYY/MM/DD/` tree. `organize_applications.py` remains as a standalone tool for manual use. Post-Pipeline Step 3 in `03_cover_letter.md` is now automatic via the `--sort` flag.

**Phase 5 — Char-Count Check Consolidation:**
- **5.1 `--check-tex` mode:** Added `--check-tex` mode to `resume_parseability.py`. Runs the LaTeX project summary length check (same regex, same limits: <= 300 chars English, <= 280 chars German). The limit applies only to the project summary/description text — project name, separator (`---`), and link markup are excluded from the count. Step B in `02_resume_and_visual_audit.md` now calls `resume_parseability.py --check-tex` instead of an inline `python -c` one-liner.

---

## v27 — Resume Parseability Audit + ReportFallback Layout Fixes
**Files:** `resume_parseability.py` (new), `renderers/parseability_report.py` (new), `yaml_to_pdf.py`, `renderers/resume_reportfallback.py`, `SKILL.md`, `02_resume_and_visual_audit.md`, `README.md`, `CHANGELOG.md`

**Motivation:** Adds a standalone ATS parse-integrity audit that verifies the compiled resume PDF's text layer is machine-readable by ATS parsers. Also fixes several layout issues in the ReportFallback resume renderer.

**Resume Parseability Audit:**
- New `resume_parseability.py` script — takes a resume PDF + resume YAML as inputs, extracts the PDF text layer via pypdf, and runs 5 checks:
  1. **Unicode Integrity** — scans for replacement glyphs (U+FFFD) indicating font encoding corruption
  2. **Keyword Recovery** — extracts every tool, skill, and significant summary word from the YAML and verifies each is recoverable from the PDF text (handles line-break splitting via whitespace normalization)
  3. **Section Header Detection** — verifies all 6 standard section headers are present
  4. **Contact Info Extraction** — verifies name, phone, email, GitHub, LinkedIn are extractable
  5. **Text Structure** — reports line count, average/max line length
- Outputs `Parseability_Report.yaml` (structured) and `Parseability_Report.pdf` (human-readable, LM Roman 10, same style as ATS Report)
- Exit code 0 = pass, 1 = fail, 2 = error
- New `renderers/parseability_report.py` — renders the audit results as a PDF report with status tables, keyword recovery table, section detection table, contact extraction table, and a text preview section
- Registered `parseability_report` as a new document type in `yaml_to_pdf.py` (with filename inference for `parseability`/`parse` keywords)
- Integrated into Step 2 as Section 6 (Mandatory Post-Compilation) in `02_resume_and_visual_audit.md` with command, outputs, and pass criteria
- Added to SKILL.md script structure, Step 2 description/output, and completion checklist

**ReportFallback Resume Layout Fixes:**
- **Zero-padding frame:** Replaced `SimpleDocTemplate` with `BaseDocTemplate` + custom `Frame(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)` so that Tables (section headers) and Paragraphs (body text) both start at the exact same x position. Previously, the default 6pt frame padding caused body text to appear 6pt indented relative to section headers.
- **Education dates right-aligned:** Restored the two-column Table layout for education (same as Professional Experience) — degree + university on the left, date right-aligned. University name is italic and 1 font size smaller (8.5pt), not bold.
- **Project tools line:** Compressed (no spaces after commas), spaces within tool names replaced with non-breaking spaces to prevent mid-tool wrapping, adaptive font size (7.5pt / 7.0pt / 6.5pt) based on header length to keep tools on one line.
- **Full justification:** Summary and project prose paragraphs use `alignment=4` (justify) for Ctrl+J-style text alignment.
- **No indentation:** All styles explicitly set `leftIndent=0, firstLineIndent=0` — name, contact, summary, skills, projects, section headers all start flush from the left margin.

---

## v26 — Render Mode Selection (LaTeX vs ReportFallback) + Renderer File Split + Calibri ReportFallback
**Files:** `renderers/resume.py`, `renderers/resume_latex.py` (new), `renderers/resume_reportfallback.py` (new), `renderers/resume_common.py` (new), `renderers/cover_letter.py`, `renderers/cover_letter_latex.py` (new), `renderers/cover_letter_reportfallback.py` (new), `SKILL.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`

**Motivation:** Lets the user choose between the LaTeX pipeline (pdflatex, `.tex` source preserved, agent-driven project polish) and a plain ReportLab fallback (Calibri font, no `.tex` file, single-paragraph projects rendered automatically) before the pipeline runs. Splits the monolithic renderer files into focused latex/reportfallback modules so each path can evolve independently.

**Renderer File Split:**
- `renderers/resume.py` is now a thin dispatcher that reads `render_mode` from the YAML data and routes to `resume_latex.py` or `resume_reportfallback.py`. Re-exports `HEADERS`, `get_resume_language`, and `create_resume_pdf_reportlab` for backward compatibility.
- `renderers/resume_common.py` (new) — shared `HEADERS` dict and `get_resume_language()` helper, imported by both latex and reportfallback resume renderers.
- `renderers/resume_latex.py` (new) — LaTeX renderer + parse-integrity audit (`_audit_pdf_parse_integrity`, `_write_parse_integrity_report`, `create_resume_pdf_latex`). The audit-failure fallback path lazy-imports the reportfallback renderer.
- `renderers/resume_reportfallback.py` (new) — ReportLab renderer using the Calibri font family (via `register_calibri()` from utils). Projects rendered in single-paragraph format (bullets joined into prose) to match the LaTeX polished layout.
- `renderers/cover_letter.py` is now a thin dispatcher reading `render_mode`.
- `renderers/cover_letter_latex.py` (new) — LaTeX cover letter renderer. Failure path lazy-imports the reportfallback renderer.
- `renderers/cover_letter_reportfallback.py` (new) — ReportLab cover letter renderer using Calibri. Reproduces the Geschäftsbrief layout (sender, recipient, right-aligned date, bold subject, salutation, body, closing + signature).

**Render Mode Selection (Pipeline Prompt):**
- New "First Action: Select Render Mode" step in `SKILL.md` (before "Name the Session"). The agent uses `ask_user_question` to ask the user whether to use `LaTeX` or `ReportFallback` for the resume and cover letter.
- The choice is written as a top-level `render_mode` key (`latex` or `reportfallback`) in both `Resume.yaml` and `Cover_Letter.yaml`.
- Default is `latex` when the key is missing (backward compatible with existing YAMLs).
- `02_resume_and_visual_audit.md`: `render_mode` added to the `Resume.yaml` schema. When `reportfallback` is selected, the agent skips Section 4 (LaTeX Project Format Polish) and compilation Steps B/C (no `.tex` to edit or recompile) — the ReportFallback renderer already produces single-paragraph projects.
- `03_cover_letter.md`: `render_mode` added to the `Cover_Letter.yaml` schema. Compilation commands section documents both modes.

**LM Roman 10 Font for ReportFallback:**
- The ReportFallback resume and cover letter renderers use `register_lm_roman_10()` (already present in `renderers/utils.py`) which registers the LM Roman 10 TTF family with ReportLab, falling back to Times-Roman if the LM Roman 10 font files are not found on the system.
- The previous Open Sans / Calibri registration in the resume ReportLab path has been removed in favor of LM Roman 10.
- Line spacing (leading) tightened across both renderers to reduce vertical whitespace.
- Resume header: name is now rendered large (24pt, dark blue, bold) on its own line. Photo integration removed — the header is name + contact lines only.

---

## v25 — Countering Algorithmic Monoculture (ATS Vendor Tracking, Project Verification Links, Resume Variations, Parse-Integrity Audit)
**Files:** All 15 `okf/portfolio/*.md` files, `okf_lint.py`, `okf_portfolio_search.py`, `zvec_hybrid_search.py`, `okf_diversity_audit.py` (new), `sync_to_obsidian.py`, `renderers/resume.py`, `config.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `IMPLEMENTATION_PLAN.md`

**Motivation:** Integrates findings from the Stanford study on algorithmic monoculture. The pipeline now acts as a buffer against repetitive algorithmic filtration by tracking applicant-firm clustering by ATS vendors, prompting for application source diversification, highlighting project verification links, and offering resume variations.

**Phase 1 — Portfolio Metadata Enrichment:**
- Added optional `repo_url` field to the YAML frontmatter of all 15 portfolio files under `okf/portfolio/`. Three projects have canonical repo URLs (Airbnb dbt, NYC Taxi, RAG PDF Query); the remaining 12 use the GitHub profile fallback `https://github.com/SagarMarthandan`.
- Updated `okf_lint.py` to validate `repo_url` if present (must start with `https://github.com/` or `https://`). Optional field — no violation if absent.
- Updated `parse_okf_file` in `okf_portfolio_search.py` to `setdefault` `repo_url` to `""` so downstream code always has the key.

**Phase 2 — Pipeline Schema Updates (Agent Guidelines):**
- `01_ats_and_jd_archival.md`: New section 0c — ATS vendor inference from JD text/URL footprints (Workday, Personio, SAP SuccessFactors, Greenhouse, Lever, Taleo; default Unknown). Application source prompt (Cold Apply, Referral, LinkedIn Connection, Direct) with weak-tie warning on Cold Apply + known vendor. Three new root keys in `ATS_Report.yaml` schema: `ats_vendor`, `application_source`, `weak_tie_contact`. Diversity audit command added to the compilation section.
- `02_resume_and_visual_audit.md`: Project verification links instruction (read `Repo:` from `project_info.md`, copy to `Resume.yaml` as `repo_url:`). Resume variation strategy (`Balanced` | `Project-Heavy` | `Skills-Heavy`) with tailoring rules. LaTeX polish updated to weave `\href{repo_url}{GitHub}` next to project title. `Resume.yaml` schema updated with `resume_variation` top-level key and `repo_url` per-project field.
- `03_cover_letter.md`: Project `repo_url` links woven into paragraph deep dives. Referral contact (`weak_tie_contact`) mentioned in paragraph 1 when `application_source` is `Referral` or `LinkedIn Connection`.

**Phase 3 — Script & Compiler Updates:**
- `okf_portfolio_search.py` & `zvec_hybrid_search.py`: `distill_project` and `distill_project_hybrid` now emit a `Repo: <url>` line in `project_info.md` when the portfolio file has a `repo_url`.
- `okf_diversity_audit.py` (new): Clustering audit utility that walks the `Applications/` tree, parses `ATS_Report.yaml` files for `ats_vendor` and `application_source`, and reports vendor clustering (warns at ≥3 applications to the same vendor in 14 days) and referral rate (warns at <20%). Advisory only — always exits 0. Handles missing fields gracefully for legacy applications.
- `config.py`: Added `APPLICATIONS_DIR`, `DIVERSITY_VENDOR_CLUSTER_THRESHOLD` (3), `DIVERSITY_REFERRAL_RATE_MIN` (0.20), `DIVERSITY_LOOKBACK_DAYS` (14) with env var override support.
- `sync_to_obsidian.py`: `parse_ats_yaml` and `parse_ats_md` now extract `ats_vendor`, `application_source`, `weak_tie_contact`. `parse_application` threads the 3 new fields into the returned app dict. `generate_application_note` emits `**ATS Vendor:**`, `**Source:**`, and `**Referral Contact:**` lines. `sync()` generates vendor backlink notes under `Job Search/Vendors/` and source backlink notes under `Job Search/Sources/`, plus `Vendors Index.md` and `Sources Index.md`. Updated dry-run output and final summary to include vendor/source counts.
- `renderers/resume.py`:
  - **LaTeX preamble safeguards:** Added `\input{glyphtounicode}`, `\pdfgentounicode=1`, and `\usepackage[none]{hyphenat}` to prevent font ligature corruption and auto-hyphenation in ATS PDF-to-text parsers (especially Workday).
  - **Project verification links (LaTeX):** `\href{repo_url}{\color{darkblue}\small[GitHub]}` injected next to project title when `repo_url` is present. URL is not LaTeX-escaped (would break `\href`); only the project name is escaped.
  - **Project verification links (ReportLab):** Clickable `<a href='...'>[GitHub]</a>` appended to project header paragraph when `repo_url` is present.
  - **Parse-integrity audit:** New `_audit_pdf_parse_integrity()` function uses `pypdf` to extract the PDF text layer, checks for Unicode replacement glyphs (U+FFFD), and cross-references critical keywords/tools from `Resume.yaml` against the extracted text. Returns status (Pass/Fail), corruption list, missing keywords, and recovery percentage.
  - **Automated fallback:** After LaTeX compilation, the audit runs automatically. If it fails (recovery < 100% or corruptions found), the ReportLab compiler is triggered as a fallback to overwrite the PDF with a highly parsable version. The fallback PDF is re-audited; if it also fails, the pipeline halts. Results written to `Layout_Audit_Report.yaml` under `parse_integrity_verification` (status, unicode_corruptions, missing_keywords, keyword_recovery_pct, fallback_triggered).

**Phase 4 — Testing & Verification:**
- Linter: PASSED (15 portfolio files clean with new `repo_url` field).
- OKF search test: PASSED (2/2 tests — DE with archetype boost, AI/RAG with dual archetype).
- Hybrid search test: PASSED (2/2 tests — DE hybrid ranking, AI/RAG hybrid ranking).
- Utils test suite: PASSED (30/30 tests).
- Diversity audit: Runs on 249 existing applications, correctly reports 47 in lookback window, emits referral-rate warning (0% < 20%).
- Obsidian sync dry-run: Vendor/source counts appear in summary; `**Referral Contact:** None` in sample application note (expected for legacy apps without the new fields).
- Distill output: `Repo:` line correctly emitted with canonical URLs for matched projects.

---

## v24 — Parallel Agent Safety, Session Naming, Documentation Restructure
**Files:** `zvec_hybrid_search.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `SKILL.md`, `README.md`, `CHANGELOG.md` (new), `config.py`, `yaml_to_pdf.py`, `sync_to_obsidian.py`, `organize_applications.py`, `OKF_IMPROVEMENT_PLAN.md`, `.gitignore`

**Cross-Process Lock Improvements:**
- Increased lock retry interval from 0.5s to 2.0s for relaxed polling — waiting agents no longer spin aggressively.
- Added one-time log message: `Zvec DB busy (another agent is using it). Waiting for lock...` — prints once when an agent starts waiting, then waits silently in 2s intervals.
- Used separate `logged` flag to prevent repeated log spam on every retry.

**Session Naming Convention:**
- Added "Name the Session" as the first action before any pipeline work in `SKILL.md`, `01_ats_and_jd_archival.md`, and `README.md`.
- Agents must extract Company Name and Job Role from the JD and rename their session/conversation to `[Company Name] — [Job Role]` in the UI sidebar.
- Makes it easy to identify which agent is handling which application when running 10 agents in parallel.
- Application folder naming convention also reinforced: must use `[Company Name] — [Job Role]` extracted from JD, no arbitrary names or timestamps.

**Post-Pipeline Ordering Enforcement:**
- Added explicit prerequisite in `03_cover_letter.md`, `SKILL.md`, and `README.md`: Obsidian sync (Step 2) MUST complete before application sorting (Step 3).
- Explained why: the folder must remain at `Applications/[Company Name] — [Job Role]/` during sync so the sync script can find it; sorting moves it to `Applications/YYYY/MM/DD/...` which makes it invisible to sync.
- Updated checklist in `SKILL.md`: "MUST run after Obsidian sync completes, not before".

**Documentation Restructure:**
- Extracted full changelog (v1–v23) from `README.md` into separate `CHANGELOG.md` file. README now links to it with a single line.
- Added developer-only skip comment to `CHANGELOG.md` (same as README — agents skip reading it during pipeline execution).
- Reordered README sections: Hybrid Search Architecture now comes before Step-by-Step Execution Guide.

**Branding & Path Cleanup:**
- Renamed all `yaml-cv-pipeline` / `YAML CV Pipeline` references to `okf-cv` / `OKF-CV Pipeline` across `SKILL.md`, `config.py`, `yaml_to_pdf.py`, `sync_to_obsidian.py`, `organize_applications.py`, `OKF_IMPROVEMENT_PLAN.md`.
- Replaced all `[skill directory]` placeholders and relative script paths with full absolute path `C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\` in all agent-facing instruction files (`01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`) and `README.md`.
- Fixed hardcoded paths in `02_resume_and_visual_audit.md` that pointed to the old `yaml-cv-pipeline` folder.

**Git Repository Setup:**
- Added `.gitignore` entries for personal info files (`okf/base_files/english/resume.md`, `okf/base_files/german/resume_de.md`), generated files (`okf/zvec_db/`, `okf/hash_index.json`, `okf/learning_log.json`, `*.lock`), and workspace files (`okf-cv.code-workspace`, `Applications/`).
- Ready for new GitHub repo `SagarMarthandan/okf-cv`.

---

## v23 — Hybrid Search Mode (OKF + Zvec Score Fusion)
**Files:** `zvec_hybrid_search.py` (new), `config.py`, `okf_learn.py`, `01_ats_and_jd_archival.md`, `SKILL.md`, `README.md`

- **Created `zvec_hybrid_search.py`:** Hybrid search engine that runs both OKF phrase matching and Zvec semantic embeddings, then fuses scores: `final = (okf_score * 0.6) + (zvec_sim * 0.4)`.
- **Zvec semantic layer:** All 14 portfolio files embedded using `all-MiniLM-L6-v2` (384-dim vectors) stored in local Zvec database under `okf/zvec_db/`.
- **Incremental re-embedding:** Content hash detection (`hash_index.json`) ensures only modified files are re-embedded. Full re-embedding only on first run or `force_recreate`.
- **Re-embed trigger in `okf_learn.py`:** When the self-learning loop adds new keywords to a portfolio file, the modified file is automatically re-embedded into the Zvec database via `reembed_file()`. Non-blocking — fails gracefully if Zvec unavailable.
- **Score fusion:** Zvec cosine similarity (0-1) scaled to OKF score range, then weighted. Weights configurable in `config.py` (`HYBRID_OKF_WEIGHT=0.6`, `HYBRID_ZVEC_WEIGHT=0.4`).
- **Hybrid diagnostics:** `project_info.md` now shows both OKF and Zvec scores in the match diagnostics comment: `OKF=X.XX, Zvec=0.XXX, fused=X.XX`.
- **Updated `01_ats_and_jd_archival.md`:** Step 1 now uses `zvec_hybrid_search.py` instead of `okf_portfolio_search.py` for project search.
- **Updated `SKILL.md`:** Pipeline diagram, script listing, and dependencies updated to include hybrid search and Zvec dependencies.
- **Updated `config.py`:** Added `ZVEC_DB_PATH`, `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIMENSION`, `HYBRID_OKF_WEIGHT`, `HYBRID_ZVEC_WEIGHT` with env var override support.
- **Cross-process locking:** All Zvec DB operations wrapped in `zvec_db_lock()` context manager using OS-level file locking (`msvcrt` on Windows, `fcntl` on Unix). Infinite wait (no timeout) — agents wait indefinitely until the lock is released. 0.5s retry interval. CPU-bound work (embeddings, hashing) runs outside the lock to minimize contention. Enables safe parallel pipeline execution across multiple agents.
- **OKF fallback:** `okf_portfolio_search.py` remains as a fallback if Zvec/sentence-transformers are not installed.

---

## v22 — OKF Improvement Plan: Frontmatter Curation, Scoring Rewrite, Linter & Self-Learning
**Files:** All 14 `okf/portfolio/*.md` files, `okf_portfolio_search.py`, `okf_lint.py` (new), `okf_learn.py` (new), `sync_to_obsidian.py`, `01_ats_and_jd_archival.md`, `03_cover_letter.md`, `tests/test_okf_search.py`, `SKILL.md`, `README.md`

**Phase 1 — Frontmatter Curation:**
- Audited and rewrote frontmatter for all 14 portfolio files using `repo info.md` as source of truth.
- Replaced broken image alt-text in descriptions with concise 1-sentence summaries.
- Removed noise tokens from technologies (`2025`, `ER Diagram`, `Project Status:`, `Screenshot 1`, etc.).
- Replaced title-derived keyword tokens with domain-relevant phrases.
- Trimmed archetypes from 7+ tags per file to 1-2 accurate canonical archetypes.
- Added Analytics Engineering archetype to NYC Taxi, Weather Data, and YouTube E2E projects.
- Added Data Analyst archetype to COMAD PCA project (anomaly detection, exploratory analysis).

**Phase 2 — Scoring Algorithm Rewrite:**
- Replaced token-intersection with phrase-level matching (multi-word phrases as substrings, single words with word boundaries).
- Added bidirectional synonym/alias map (50+ entries covering DE/AI domain: kafka↔message queue, dbt↔transformation framework, terraform↔iac, rag↔retrieval augmented generation, etc.).
- Added light stemming for morphological variants (orchestration↔orchestrator, pipeline↔pipelines).
- Added fuzzy token matching via `difflib.SequenceMatcher` (threshold 0.85) for typo tolerance.
- Added archetype boost: +10 for primary, +5 for secondary (from `ATS_Report.yaml`), +3 fallback from raw JD text.
- Added Jaccard-style normalization to prevent JD-length bias.
- Improved tiebreaker: archetype match count, then tech match count, then alphabetical.
- Added configurable `top_k` CLI argument (default 4).
- Search command now accepts `ATS_Report.yaml` as 3rd argument for archetype-boosted scoring.

**Phase 3 — Distill Output Enrichment:**
- `distill_project()` now emits archetypes line, body summary (first 1-2 sentences), and match diagnostics HTML comment.

**Phase 4 — Validation & Guardrails:**
- Created `okf_lint.py` frontmatter linter: validates non-empty fields, canonical archetypes, denylisted tech tokens, description length, keyword count, title-token overlap.
- Added linter step to Step 1 pipeline in `01_ats_and_jd_archival.md`.
- Updated `tests/test_okf_search.py` with 3 test cases: DE with archetype boost, AI/RAG with dual archetype, smoke test with generic JD.

**Phase 5 — Dependency & Config Cleanup:**
- Verified `requirements.txt` is minimal (`pyyaml`, `reportlab`, `pypdf`). No changes needed.

**Phase 6 — Self-Learning Keyword Enrichment:**
- Created `okf_learn.py`: post-application keyword enrichment loop.
- Extracts domain-relevant terms (bigrams/trigrams + single tokens) from processed JD using 100+ regex patterns.
- For each matched project, finds JD terms in project body/description/technologies but missing from keywords.
- Filters out 300+ generic noise words to ensure only domain-relevant terms are added.
- Appends up to 3 new keywords per project per run, respects 15-keyword cap.
- Runs linter after enrichment with baseline comparison; rolls back only on new violations.
- Logs all changes to `okf/learning_log.json` with timestamp, JD source, and role archetype.
- Wired into pipeline as Post-Pipeline Step 1 (after cover letter, before folder sort).
- Updated `03_cover_letter.md`, `SKILL.md`, and `README.md` with learning loop integration.

**Obsidian Vault Sync Integration:**
- Wired `sync_to_obsidian.py` into pipeline as Post-Pipeline Step 2 (after learning loop, before folder sort).
- Syncs all applications to Obsidian vault as linked notes (applications, companies, roles, skills, projects) for graph-view navigation.
- Handles both YAML and MD application formats.
- Updated `03_cover_letter.md`, `SKILL.md`, and `README.md` with Obsidian sync step.

---

## v21 — Google OKF Portfolio Search Migration
**Files:** `okf_portfolio_search.py` (new), `config.py`, `requirements.txt`, `renderers/job_description.py`, `renderers/ats_report.py`, `renderers/utils.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `SKILL.md`, `README.md`, `tests/test_okf_search.py` (new)

**Architectural Migration:**
- Replaced vector-based search engine with **Google OKF (Open Knowledge Format)** search matching — 100% local, offline, deterministic.
- Restructured candidate portfolio from a flat `repo info.md` file to a modular, self-contained `okf/` folder inside the skill directory. Contains individual project markdown files with metadata frontmatters (specifying keywords, technologies, and archetypes) and template base resumes/photos.
- Created `okf_portfolio_search.py` to calculate deterministic keyword/archetype overlap scores between the job description and project files.

**Resource and Dependency Gains:**
- Removed heavy Python ML dependencies (`torch`, `sentence-transformers`, `tqdm`) saving **~2.5GB of disk space** and reducing memory footprint from **~1GB to <15MB**.
- Search execution speed increased **100x** (from ~3s model load time to <5ms query execution).

**ReportLab Fallback Typeface Integration:**
- Swapped ReportLab fallback PDF fonts (in `ats_report.py` and `job_description.py`) from Calibri to **Latin Modern Roman 10** (`LMRoman10`) using the centralized font helper.

---

## v20 — Application Folder Date-Tree Sorting
**Files:** `organize_applications.py` (new), `03_cover_letter.md`, `SKILL.md`, `README.md`

- **Added `organize_applications.py`** — sorts application folders into a `Applications/YYYY/MM/DD/[Company Name] — [Job Role]/` tree, bucketed by each folder's creation time (`os.path.getctime`).
- **Two run modes:** scan mode (sorts every unsorted folder in `Applications/`) and targeted mode (sorts a single freshly-created folder, used by the pipeline).
- **Pipeline integration:** Step 3 now runs the sorter automatically after the cover letter compiles, placing the new application folder into the correct date bucket.
- **Idempotent and safe:** already-sorted folders are skipped; `--dry-run` previews moves; `--root` overrides the Applications path for isolated testing; UTF-8 stdout reconfigure handles em-dash (`—`) folder names on the Windows console.

---

## v19 — ATS Scoring Remodel & Font Update
**Files:** `renderers/utils.py`, `renderers/ats_report.py`, `renderers/job_description.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `README.md`

- **Removed `formatting_and_parse` from the ATS score matrix.** Formatting no longer dilutes the 100-point score.
- **Rebalanced the matrix to 4 equally-weighted categories of 25 points each:** `keywords_and_terminology`, `experience_relevance`, `technical_skills`, `soft_skills_and_language` (total = 100).
- **Added a non-scored `formatting_quality` verdict** (`Excellent` / `Good` / `Average` / `Bad`) with `suggestions` populated only when the verdict is `Average` or `Bad`. Rendered as a dedicated section in the ATS Report PDF (pre- and post-rewrite).
- **Fixed unformatted dict rendering** in the ATS Report PDF: `bullet_point_density_audit` and `quantified_outcomes` entries are now rendered as readable labeled lines instead of raw Python dict reprs.
- **Switched the ATS Report and Job Description PDF typeface** to Latin Modern Roman 10 (`LMRoman10`) with Helvetica fallback.

---

## v18 — Replace closest_location.py with LLM Web Search
**Files:** `closest_location.py` (deleted), `tests/test_closest_location.py` (deleted), `config.py`, `01_ats_and_jd_archival.md`, `SKILL.md`, `README.md`

- Removed `closest_location.py` and its unit tests — the hardcoded city coordinate database and haversine distance calculation failed for remote locations and any city not in the static database.
- Removed `CANDIDATES` and `CITY_COORDS` dictionaries from `config.py`.
- Step 1 now instructs the LLM to **web search** which of the 4 candidate cities (Kiel, Frankfurt, Berlin, Köln) is geographically nearest to the job location.
- Remote, country-wide, or unspecified locations still default to Kiel, Germany.

---

## v17 — Scope Leak Fixes & Portability Improvements
**Files:** `config.py`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `renderers/utils.py`, `SKILL.md`, `README.md`

**Scope Leak Fixes:**
- Made all Base Files paths relative and configurable via environment variables (`YAML_CV_MD_PATH`, `YAML_CV_DB_PATH`)
- Replaced hardcoded Python interpreter paths with `python` to support local/venv installations
- Restricted font search to local directories only (`project/fonts/`, `../Base Files/fonts/`) with `YAML_CV_FONT_DIRS` override
- Updated all working directory references from absolute paths to relative `Applications/`
- Fixed photo path references to use relative paths

**Portability:**
- Skill now operates entirely within its scope without accessing files outside the project
- Supports locally installed dependencies without requiring specific Python installation paths
- Environment variable overrides for all critical paths for maximum flexibility

---

## v16 — Performance & Code Quality Optimizations
**Files:** `renderers/utils.py`, `renderers/cover_letter.py`, `yaml_to_pdf.py`, `config.py`, `requirements.txt`, `test_utils.py`

**Code Quality & Maintainability:**
- Created centralized `config.py` for all hardcoded paths, constants, and city coordinates with environment variable override support
- Consolidated duplicate font registration code into `_find_and_register_font_family()` helper function (~60 lines reduced)
- Extracted common address formatting utility `format_address()` for LaTeX/HTML rendering
- Added comprehensive type hints to all functions in `renderers/utils.py` and `yaml_to_pdf.py`

**Testing:**
- Created `test_utils.py` with 30 unit tests for LaTeX escaping and address formatting utilities

---

## v14 — LM Roman 10 Font Integration
**Files:** `renderers/utils.py`, `renderers/ats_report.py`, `renderers/job_description.py`, `README.md`

- Replaced previous font with Latin Modern Roman 10 (`LMRoman10`) for the ReportLab-based Job Description archival and ATS Report PDFs.
- Added TTF registration code for `lmroman10` (regular, bold, italic, bold-italic) searching standard system and local AppData paths.

---

## v13 — Job Location Tailoring
**Files:** `SKILL.md`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `README.md`

- Introduced a location-tailoring mechanism that extracts the job location from the job description.
- Uses web search to determine the closest candidate city among Kiel (home), Frankfurt (friend), Berlin (friend), and Köln (friend).
- Updated pipeline steps to propagate the closest candidate city to `Resume.yaml` and `Cover_Letter.yaml` addresses and dates.

---

## v12 — Pipeline Token Optimizations
**Files:** `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `SKILL.md`, `README.md`, `renderers/utils.py`, `renderers/ats_report.py`, `renderers/job_description.py`

- Collapsed writing style guidelines and step descriptions to reference-only summaries, saving context tokens and preventing documentation drift.
- Replaced copy-paste attachment placeholders with direct file load instructions, saving **1,000–3,000+ context tokens** per run.
- Added developer-only skip comment to the top of `README.md`.

---

## v11 — YAML Frontmatter Syntax Fix
**Files:** `SKILL.md`

- Converted the description in `SKILL.md` frontmatter to use a YAML block scalar (`>-`).
- Resolves parsing errors where unescaped colons and quotes within the description caused invalid YAML syntax.

---

## v10 — ReportLab Only for Job Description Archival
**Files:** `renderers/job_description.py`, `SKILL.md`

- Changed the Job Description compiler to output directly in ReportLab fallback mode (no LaTeX conversion or pdflatex compiling).
- Streamlined `create_job_description_pdf` to call the fallback generator directly.

---

## v9 — ReportLab Only for ATS Analysis
**Files:** `renderers/ats_report.py`, `SKILL.md`

- Changed the ATS Analysis report compiler to output directly in ReportLab fallback mode (no LaTeX conversion or pdflatex compiling).
- Streamlined `create_ats_report_pdf` to call the fallback generator directly.

---

## v8 — LaTeX Paragraph Separation Fix
**Files:** `renderers/resume.py`, `02_resume_and_visual_audit.md`

- Fixed projects (and experience entries) flowing together as one continuous block of text with no visual gap between them.
- **Root cause:** `\vspace{6pt}` between `\noindent` paragraphs was firing in LaTeX's horizontal mode (mid-paragraph) where it is a no-op. LaTeX must be in vertical mode for `\vspace` to produce actual vertical space.
- **Fix:** Added `\par` at the end of each `\end{itemize}` block in the generator (`resume.py`). `\par` explicitly ends the paragraph and switches LaTeX to vertical mode before the `\vspace{6pt}` separator fires.
- Updated `02_resume_and_visual_audit.md` Step 4 format rule to require `.\par` at the end of every project paragraph in the LaTeX polish step.

---

## v6 — README Changelog & Mermaid Diagram Fix
**Files:** `README.md`

- Added full `## Changelog` section to `README.md` documenting all changes from v1–v5 with files affected, rationale, and bullet-point summaries.
- Fixed Mermaid architectural diagram for GitHub compatibility:
  - Replaced `&` with `and` in all node labels and subgraph titles.
  - Split multi-source arrow syntax into individual arrows.
  - Replaced `<br>` multi-line node labels with single-line labels using em-dashes.
  - Quoted all subgraph titles to prevent parse errors on special characters.

---

## v5 — RAG Output Distillation
**Files:** `okf_portfolio_search.py`

- Added `distill_project()` helper that strips each matched project's raw markdown to just the signal Step 2 needs: project title + first prose paragraph + tech-stack line.
- Previously, each project's full raw markdown (code blocks, badges, troubleshooting sections, install instructions) was dumped into `project_info.md` — resulting in ~400 lines for 4 projects.
- Now `project_info.md` is ~12 lines for 4 projects. Full content is still used for semantic ranking; only the distilled output is written.

---

## v4 — Consistent LaTeX Spacing Across Sections
**Files:** `renderers/resume.py`, `02_resume_and_visual_audit.md`

- Fixed inconsistent vertical spacing between project and experience entries in the generated LaTeX.
- Changed inter-entry join separator from `\vspace{8pt}` → `\vspace{6pt}` uniformly for both Projects and Professional Experience sections.
- Replaced the implicit `\\[2pt]` line-break after each `\jobEntry` with an explicit `\vspace{2pt}` for deterministic, consistent spacing.
- Removed the trailing `\vspace{6pt}` from inside each project paragraph (was causing double-spacing when combined with the join separator).

---

## v3 — German Language Support & Post-Rewrite ATS PDF Fix
**Files:** `02_resume_and_visual_audit.md`, `03_cover_letter.md`, `SKILL.md`, `README.md`, `renderers/cover_letter.py`

**German Language Adaptations:**
- Resume output renamed to `SAGAR_MARTHANDAN_Lebenslauf.pdf` / `.tex` when JD is in German.
- Cover letter output renamed to `SAGAR_MARTHANDAN_Anschreiben.pdf` / `.tex` when JD is in German.
- German resume summary (Zusammenfassung) capped at **340–380 characters** (vs 420 for English) to prevent 5th-line overflow from longer German compound words.
- German project paragraphs (Projekte) capped at **230–250 characters** (vs 300 for English) to guarantee ≤ 3 lines.
- German cover letter (Anschreiben) limited to **180–240 words** total (vs 250–320 for English), reducing each paragraph by 10–20 words to prevent A4 page overflow.
- Step 2 compilation and character-count audit scripts updated with conditional English/German paths and limits.

**Post-Rewrite ATS Rescoring Fix:**
- After the resume rewrite, `ATS_Report.yaml` is updated with `post_rewrite_ats_score`. Step 2 now explicitly re-runs `yaml_to_pdf.py` to recompile `ATS_Report.pdf` so the PDF reflects the updated scores.

---

## v2 — Master README & Pipeline Documentation
**Files:** `README.md`

- Created the master `README.md` documenting the full pipeline architecture, step-by-step execution guide, and directory structure.
- Added the Mermaid architectural workflow diagram.

---

## v1 — Initial Pipeline Implementation
**Files:** All core files (initial commit)

- Full 3-step YAML CV pipeline: ATS analysis & JD archival (Step 1), resume rewrite & LaTeX visual audit (Step 2), cover letter generation (Step 3).
- LaTeX primary renderer with ReportLab fallback for all 4 document types (resume, cover letter, job description, ATS report).
- Auto-seeding: portfolio database is built on first run from `repo info.md` if it doesn't exist.
- `.tex` source files preserved for resume and cover letter (cleaned up for JD and ATS report).
- ATS Score Gate: pipeline halts with remedy suggestions if pre-rewrite score is `< 85`.
- Stop-Slop writing rules enforced across all generated text (active voice, adverb ban, zero em-dashes).
- Automated pip dependency installation at Step 1 start.
- `SKILL.md`, `01_ats_and_jd_archival.md`, `02_resume_and_visual_audit.md`, `03_cover_letter.md` codified as agent-native skill instructions.
