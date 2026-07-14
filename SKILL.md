---
name: okf-cv
description: >-
  Use when the user wants to generate an ATS-optimized resume and cover letter from a job description using the hybrid portfolio search (OKF phrase matching + Zvec semantic embeddings). Runs a 3-step pipeline: ATS analysis & JD archival, resume rewrite & layout audit, and cover letter generation. Trigger on keywords like "job description", "resume", "cover letter", "ATS", "apply", "job application", "tailor resume", "optimize resume", "OKF", "Open Knowledge Format", "hybrid search", "Zvec".
dependencies: python>=3.10, pyyaml, reportlab, pypdf, stop-slop, zvec, sentence-transformers
---

# OKF-CV Pipeline

End-to-end pipeline that takes a **Job Description (JD)** and produces a tailored ATS-optimized resume + cover letter as compiled PDFs, plus an archived JD reference and a visual-optimized alternate version.

## Pipeline Overview

```
                        JD + Base Resume
                               │
                               ▼
   Step 1: Setup & ATS Archival ──► ATS_Report.yaml + Job_Description.pdf
         │
         ├───► [Runs Hybrid Search: OKF Phrase Matching + Zvec Semantic Embeddings]
         │     └───► Score fusion: (okf * 0.6) + (zvec * 0.4)
         │     └───► Generates: project_info.md (Tailored Projects List)
         │
         ▼
  Step 2: Resume & Visual Audit ──► Reads tailored project_info.md
         │                           └───► Generates: Resume.yaml/pdf/tex
         ▼
  Step 3: Cover Letter ───────────► Reads tailored project_info.md
                                     └───► Generates: Cover_Letter.yaml/pdf/tex
         │
         ▼
  Post-Pipeline Step 1: Self-Learning ──► Runs okf_learn.py to enrich portfolio
         │                           └───► Keywords from JD terms found in project bodies
         ▼
Post-Pipeline Step 2: Obsidian Sync ──► Runs sync_to_obsidian.py to emit linked
         │                           └───► Notes into vault for graph-view navigation
         ▼                           ⚠ MUST complete before Step 3
Post-Pipeline Step 3: Sort ───────────► Moves the application folder into
                                     Applications/YYYY/MM/DD/[Company] — [Role]/
```

- **Base Files Directory (Self-Contained OKF):**
  - **English:** `okf/base_files/english/` (Base resume `resume.md`)
  - **German:** `okf/base_files/german/` (Base German resume `resume_de.md`)
  - **Photo:** `okf/photo/` (Photo image files, e.g. `Sagar.jpg`)
  - **Repo Info:** `okf/portfolio/` (Directory of individual OKF markdown files representing your projects)
- **Python Installation:** Python 3.10+ with dependencies installed from [requirements.txt](file:///c:/Users/sagar/Documents/YAML-CV/skills/okf-cv/requirements.txt) (`pyyaml`, `reportlab`, `pypdf`, `zvec`, `sentence-transformers` installed)
- **Working Directory:** `Applications/` (relative to project root)
- **Pipeline Script Structure:**
  - `yaml_to_pdf.py` — entry point; routes YAML files to the correct renderer
  - `zvec_hybrid_search.py` — Hybrid search engine (OKF phrase matching + Zvec semantic embeddings, score fusion 0.6/0.4, cross-process file lock for parallel agent safety)
  - `okf_portfolio_search.py` — OKF search & distillation engine (phrase-level matching, synonym expansion, stemming, fuzzy matching, archetype-boosted scoring, Jaccard normalization) — used as fallback if Zvec unavailable
  - `okf_lint.py` — Frontmatter linter; validates all portfolio files before scoring (run in Step 1)
  - `okf_learn.py` — Self-learning keyword enrichment; extracts JD terms and enriches portfolio keywords post-application (run after Step 3)
  - `sync_to_obsidian.py` — Syncs application data to Obsidian vault as linked notes for graph-view navigation (run after learning loop)
  - `renderers/utils.py` — shared utilities (`escape_latex`, color constants, `run_pdflatex`, font registration including Calibri)
  - `renderers/resume_common.py` — shared resume helpers (`HEADERS`, `get_resume_language`)
  - `renderers/resume.py` — Resume renderer dispatcher (reads `render_mode`, routes to latex or reportfallback)
  - `renderers/resume_latex.py` — Resume LaTeX renderer + parse-integrity audit
  - `renderers/resume_reportfallback.py` — Resume ReportLab renderer (LM Roman 10 font, same layout as LaTeX)
  - `renderers/cover_letter.py` — Cover Letter renderer dispatcher (reads `render_mode`, routes to latex or reportfallback)
  - `renderers/cover_letter_latex.py` — Cover Letter LaTeX renderer
  - `renderers/cover_letter_reportfallback.py` — Cover Letter ReportLab renderer (LM Roman 10 font, same layout as LaTeX)
  - `renderers/job_description.py` — Job Description renderer (ReportLab only)
  - `renderers/ats_report.py` — ATS Report renderer (ReportLab only)
  - `renderers/parseability_report.py` — Parseability Report renderer (ReportLab only, LM Roman 10)
  - `resume_parseability.py` — ATS parse-integrity audit script; checks PDF text layer for unicode corruption, keyword recovery, section headers, and contact info extraction; outputs `Parseability_Report.yaml` + `Parseability_Report.pdf` (run after resume compilation in Step 2)
  - `organize_applications.py` — Sorts application folders into a Year/Month/Date tree (run after Obsidian sync)

## General Writing & Style Rules (Stop-Slop)

To ensure all generated text sounds authentic and human, the pipeline step outputs (particularly resume bullet points and cover letter prose) must adhere to the **Stop-Slop** writing guidelines:
- **Core Principle:** Strictly eliminate predictable AI tells, structures, and rhythms.
- **Strict Active Voice:** Ensure every sentence leads with active human action. Avoid passive constructions.
- **Absolute Adverb Ban:** Do not use any adverbs ending in `-ly` or softening emphasis crutches (like *successfully*, *effectively*, *genuinely*, *actually*, *really*).
- **Zero Em-Dashes:** Punctuation em-dashes (`—`) are prohibited; use commas or periods.
- **No Throat-Clearing:** Start sentences directly. Cut preview/recap statements (e.g., *"at its core"*, *"it is worth noting"*, *"the reality is"*).

## Input Required

The user must provide:
1. **Job Description** — paste the full JD text
2. (Optional) **Language override** — if the user wants the output in a specific language different from the JD language

## First Action: Select Render Mode

Before executing any pipeline step, ask the user which render mode to use for the resume and cover letter PDFs. Use the `ask_user_question` tool with a single-select question:

- **Question:** "Which render mode should the resume and cover letter use?"
- **Header:** "Render mode"
- **Options:**
  - `LaTeX` — Compile via pdflatex (primary). Produces a `.tex` source file alongside the PDF. The agent performs the LaTeX project single-paragraph polish post-compilation.
  - `ReportFallback` — Compile via ReportLab using the LM Roman 10 font (TTF version installed locally). No `.tex` file is produced. Projects are rendered in single-paragraph format automatically to match the LaTeX layout. Use this when pdflatex is unavailable or when a LM Roman 10-styled PDF is preferred.

The selected mode MUST be written as a top-level `render_mode` key in both `Resume.yaml` and `Cover_Letter.yaml`:
- LaTeX → `render_mode: latex`
- ReportFallback → `render_mode: reportfallback`

The renderers read this key and dispatch accordingly. If the key is missing, `latex` is assumed (backward compatible). The choice applies to both the resume and the cover letter for this application.

## Second Action: Name the Session

Before executing any pipeline step, extract the **Company Name** and **Job Role/Position** from the JD and rename this session/conversation to `[Company Name] — [Job Role]`. This makes it easy to identify which agent is handling which application in the sidebar/session list when running multiple agents in parallel. Examples:
- `SAP — Senior Data Engineer`
- `Google Cloud — AI/ML Engineer`
- `Deutsche Bank — Analytics Engineer`

## Execution — Run All 3 Steps Sequentially

### STEP 1: Setup, ATS Analysis & Job Description Archival

Read and execute the full instructions in [01_ats_and_jd_archival.md](file:///c:/Users/sagar/Documents/YAML-CV/skills/okf-cv/01_ats_and_jd_archival.md).

Runs dependency check, runs the frontmatter linter (`okf_lint.py`) to validate portfolio metadata, parses and archives the job description, scores the base resume, performs location tailoring via web search to find the closest candidate city, and generates a tailored project list using the hybrid search engine (OKF phrase matching + Zvec semantic embeddings with score fusion).

**ATS Scoring Model:** 4 equally-weighted categories of 25 points each (total = 100) — Keywords & Terminology, Experience Relevance, Technical Skills, Soft Skills & Language. Formatting is **not scored**; instead a non-scored `formatting_quality` verdict (`Excellent` / `Good` / `Average` / `Bad`) is emitted with suggested changes when `Average` or `Bad`. Score gate: `PROCEED` if total >= 85, else `HOLD`.

**Output:** `ATS_Report.yaml`, `ATS_Report.pdf`, `Job_Description.yaml`, `Job_Description.pdf`, and `project_info.md` in `[Company Name] — [Job Role]/` folder.

**Naming Convention (Critical):** The application folder and session name MUST be `[Company Name] — [Job Role]` extracted from the JD. No arbitrary names or timestamps. See `01_ats_and_jd_archival.md` for details.

---

### STEP 2: Resume Rewrite & Visual Layout Audit

Read and execute the full instructions in [02_resume_and_visual_audit.md](file:///c:/Users/sagar/Documents/YAML-CV/skills/okf-cv/02_resume_and_visual_audit.md).

Rewrites the resume based on the ATS Improvement Blueprint and the tailored project list. Compiles the resume via LaTeX, performs a visual layout audit and Stop-Slop check, updates the post-rewrite ATS score, and runs the parse-integrity audit (`resume_parseability.py`) to verify the PDF text layer is ATS-parseable.

**Output:** `Resume.yaml`, `Layout_Audit_Report.yaml`, `SAGAR_MARTHANDAN_Resume.pdf` / `SAGAR_MARTHANDAN_Lebenslauf.pdf` (and `Resume_v2.pdf` / `Lebenslauf_v2.pdf` if needed), `Parseability_Report.yaml`, and `Parseability_Report.pdf`.

---

### STEP 3: Cover Letter Generation & Compilation

Read and execute the full instructions in [03_cover_letter.md](file:///c:/Users/sagar/Documents/YAML-CV/skills/okf-cv/03_cover_letter.md).

Generates a formal, metric-grounded cover letter standard conforming to German Geschäftsbrief layout in the target JD language.

**Output:** `Cover_Letter.yaml` and `SAGAR_MARTHANDAN_Cover_Letter.pdf` / `SAGAR_MARTHANDAN_Anschreiben.pdf`.

---

## Error Handling

If the compilation fails:
1. Check stdout/stderr console logs for PyYAML parser errors or ReportLab layout exceptions.
2. Verify YAML formatting is correct (e.g. check for unquoted colons, incorrect indentations).
3. If an image is missing, ensure Sagar.jpg is placed in the designated Base Files path.
4. If there's a layout overflow, trim the text length in the resume YAML.

## Completion Checklist

After all 3 steps complete, verify:
- [ ] `ATS_Report.yaml` exists in the company folder with pre and post rewrite scores, including `closest_candidate_location`
- [ ] `ATS_Report.pdf` is generated and `post_rewrite_ats_score` block is populated
- [ ] `ATS_Report.yaml` contains a non-scored `formatting_quality` verdict (pre- and post-rewrite) with `suggestions` populated only if verdict is `Average` or `Bad`
- [ ] `Job_Description.yaml` (with `location` key) & `Job_Description.pdf` are generated
- [ ] `project_info.md` (tailored project list) is generated in the company folder
- [ ] `Resume.yaml` & `SAGAR_MARTHANDAN_Resume.pdf` / `SAGAR_MARTHANDAN_Lebenslauf.pdf` are generated with the tailored closest location
- [ ] `SAGAR_MARTHANDAN_Resume.tex` / `SAGAR_MARTHANDAN_Lebenslauf.tex` & `SAGAR_MARTHANDAN_Cover_Letter.tex` / `SAGAR_MARTHANDAN_Anschreiben.tex` are preserved in the folder
- [ ] `Layout_Audit_Report.yaml` is generated with all eye-test diagnostics at Pass status
- [ ] `Parseability_Report.yaml` & `Parseability_Report.pdf` are generated with overall status PASS (100% keyword recovery, 6/6 sections, 5/5 contact fields, no unicode corruptions)
- [ ] `Cover_Letter.yaml` & `SAGAR_MARTHANDAN_Cover_Letter.pdf` / `SAGAR_MARTHANDAN_Anschreiben.pdf` are generated with the tailored closest location in the sender address and date fields
- [ ] Professional Experience bullet points are strictly single-line and <= 105 characters
- [ ] Project entries are in single-paragraph format, with name + `---` + description (no bullets), each <= 300 characters (<= 250 characters for German) and fitting on <= 3 lines
- [ ] Summary section is exactly 4 lines and <= 420 characters (<= 380 characters for German Zusammenfassung)
- [ ] Cover letter fits on exactly one page and has 250–320 words (180–240 words for German Anschreiben)
- [ ] All files match the target JD language and comply with the Stop-Slop guidelines
- [ ] `okf_learn.py` has enriched portfolio keywords from this JD (check `okf/learning_log.json` for changes)
- [ ] `sync_to_obsidian.py` has synced the application to the Obsidian vault (check `<vault>/Job Search/` for notes)
- [ ] `organize_applications.py` has moved the application folder into `Applications/YYYY/MM/DD/[Company Name] — [Job Role]/` (MUST run after Obsidian sync completes, not before)

