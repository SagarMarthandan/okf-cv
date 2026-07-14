# Implementation Plan: Countering Algorithmic Monoculture in okf-cv

This plan outlines the changes required to integrate the findings from the Stanford study on algorithmic monoculture into the `okf-cv` pipeline. 

By tracking applicant-firm clustering by ATS vendors, prompting for application source diversification, highlighting project verification links, and offering resume variations, the pipeline will act as a buffer against repetitive algorithmic filtration.

---

## 🛠️ Phase 1: Portfolio Metadata Enrichment (Data Layer)

### 1.1 Add `repo_url` to Portfolio Frontmatters
Add an optional `repo_url` field to the frontmatter of all 14 project files under `okf/portfolio/`. This provides the link that the resume will compile as clickable evidence.

* **Target files:** `okf/portfolio/*.md`
* **Schema addition:**
  ```yaml
  ---
  title: ...
  description: ...
  technologies: ...
  keywords: ...
  archetypes: ...
  repo_url: https://github.com/SagarMarthandan/[repo-name] # New field
  ---
  ```

#### Known Canonical Repo URLs:
* `airbnb_data_engineering_project_dbt_snowflake_dagster.md` -> `https://github.com/SagarMarthandan/DBT-Airbnb-Practice-Project`
* `nyc_taxi_analytics_pipeline_2025.md` -> `https://github.com/SagarMarthandan/ny-taxi-pipeline-2025`
* `retrieval_augmented_generation_rag_pdf_query_system.md` -> `https://github.com/SagarMarthandan/RAG-LLM-pdf-query`
* `youtube_e2e_advanced_data_engineering_pipeline.md` -> `https://github.com/SagarMagar/Youtube_E2E_DE` (or candidate's profile fallback if missing)
* **Default/Fallback for others:** `https://github.com/SagarMarthandan`

### 1.2 Update Frontmatter Linter (`okf_lint.py`)
Modify `okf_lint.py` to allow and validate the new optional `repo_url` field. Ensure it starts with `https://github.com/` or `https://` if present.

---

## 🔍 Phase 2: Pipeline Schema Updates (Agent Guidelines)

### 2.1 Update Step 1 Instructions (`01_ats_and_jd_archival.md`)
* Add new inputs under the JD: `ats_vendor`, `application_source`, and `weak_tie_contact`.
* **ATS Vendor Inference:** Instruct the agent to look for common ATS system footprints in the JD text or target application URL:
  * `myworkdayjobs.com` -> `Workday`
  * `personio.de` / `personio.com` -> `Personio`
  * `successfactors.eu` / `successfactors.com` -> `SAP SuccessFactors`
  * `greenhouse.io` -> `Greenhouse`
  * `lever.co` -> `Lever`
  * `taleo.net` -> `Taleo`
  * If none found, default to `Unknown`.
* **Application Source Selection:** Instruct the agent to prompt the user for the application source (`Cold Apply`, `Referral`, `LinkedIn Connection`, etc.). If the source is `Cold Apply` and the vendor is known, output a warning advising the user to check their network for weak ties.
* **Update ATS_Report.yaml Schema:** Add the following keys at the root of `ATS_Report.yaml`:
  ```yaml
  ats_vendor: "Personio"                 # Inferred or user-provided
  application_source: "Cold Apply"       # Referral, Cold Apply, LinkedIn, Direct
  weak_tie_contact: null                 # Optional name/role of contact
  ```

### 2.2 Update Step 2 Instructions (`02_resume_and_visual_audit.md`)
* **Project Verification Links:** Instruct the agent to extract the `repo_url` from `project_info.md` and copy it into the project block in `Resume.yaml`.
* **Resume Variation Strategy:** Add instructions for the `resume_variation` parameter:
  * Key in `Resume.yaml`: `resume_variation: Balanced | Project-Heavy | Skills-Heavy`
  * Tailoring instructions based on selected variation:
    * `Project-Heavy`: Focus on execution; write verbose descriptions for 4 projects (up to 300 chars each), simplify the skills block.
    * `Skills-Heavy`: Focus on tools; list only 3 projects, but expand the technical skills categories and bullet details.
    * `Balanced`: The standard Jake Ryan structure (3 projects, 4 experience bullets).
* **Update LaTeX Polish instructions:** Update the single-paragraph formatting instructions in Step 4. If a project has a `repo_url`, weave a clickable hypertarget next to the project title:
  ```latex
  \noindent\textbf{Project Name} (\href{repo_url}{GitHub}) --- [Action verb] [what was built] [quantified metric] [tools woven in]. [Second/third sentences].\par
  ```

### 2.3 Update Step 3 Instructions (`03_cover_letter.md`)
* Weave project verification links into paragraph deep dives if relevant.
* Incorporate application source (e.g. mention the referral contact in paragraph 1 if `application_source` is `Referral`).

---

## ⚙️ Phase 3: Script & Compiler Updates (Logic Layer)

### 3.1 Update Search Scripts (`okf_portfolio_search.py` & `zvec_hybrid_search.py`)
Modify `distill_project` (in `okf_portfolio_search.py`) and `distill_project_hybrid` (in `zvec_hybrid_search.py`) to include the repository URL if found in the portfolio frontmatter.
* Output format in `project_info.md`:
  ```markdown
  # Project Name
  Description text
  Tech: dbt, Snowflake
  Archetypes: Data Engineering
  Repo: https://github.com/...
  ```

### 3.2 Create Clustering Audit Utility (`okf_diversity_audit.py`)
Create a new script `okf_diversity_audit.py` that scans the `Applications/` directory to evaluate historical application distributions.
* **Functions:**
  * Walk the `Applications/` tree.
  * Parse all `ATS_Report.yaml` files.
  * Count applications grouped by `ats_vendor` in the last 14 days.
  * Calculate the percentage of `Referral` vs `Cold Apply`.
  * **Alert Thresholds:**
    * Trigger a warning if `ats_vendor` count $\ge 3$ in the last 14 days for the same vendor.
    * Trigger a warning if the referral rate is $< 20\%$.
* **Orchestration:** Hook this script into Step 1. When the agent installs dependencies and runs the linter, it should also execute:
  ```powershell
  python okf_diversity_audit.py
  ```
  and output the diversity status report directly to the terminal.

### 3.3 Update Obsidian Sync (`sync_to_obsidian.py`)
Update the Obsidian note generator to handle the new vendor and source fields, reinforcing networking actions.
* **YAML Parsers:** Update `parse_ats_yaml` to read `ats_vendor`, `application_source`, and `weak_tie_contact`.
* **Note Generation:**
  * In `generate_application_note`, append:
    ```markdown
    **ATS Vendor:** [[{ats_vendor}]]
    **Source:** [[{application_source}]]
    **Referral Contact:** {weak_tie_contact or 'None'}
    ```
  * Generate backlinks:
    * Create a separate note in Obsidian under `Job Search/Vendors/` for each unique vendor (e.g., `Workday.md`, `Personio.md`) listing all applications using that vendor.
    * Create a separate note under `Job_Search/Sources/` for each application source (e.g., `Referral.md`, `Cold Apply.md`) listing matching applications.
    * This visualizes the clustering immediately in Obsidian's Graph View.

### 3.4 Update Resume LaTeX Compiler (`renderers/resume.py`)
Modify `renderers/resume.py` to parse `repo_url` (or `url`) inside the `projects` section of `Resume.yaml`.
* If a project has a URL, modify the generated LaTeX definition to include the hyperlink next to the project title:
  ```python
  repo_url = proj.get('repo_url', proj.get('url', ''))
  if repo_url:
      proj_name = f"{proj_name} \\href{{{repo_url}}}{{\\color{{darkblue}}\\small[GitHub]}}"
  ```
* This ensures that even before the LaTeX Polish step runs, the base `.tex` document compiles with clickable links.

### 3.5 Parse-Integrity Validation (PDF Auditing)
Workday and other ATS systems use primitive PDF-to-text parsers that struggle with LaTeX features like **font ligatures** (e.g. "fi", "fl", "ff" mapped to single glyphs, rendering as corrupted/missing letters in raw text) and **auto-hyphenation** (splitting keywords across line margins).

* **LaTeX Preamble Safeguards (`renderers/resume.py`):**
  Add the following commands to the top of the LaTeX template preamble in `create_resume_pdf` to map Unicode characters cleanly and prevent word hyphenation:
  ```latex
  \input{glyphtounicode}
  \pdfgentounicode=1
  \usepackage[none]{hyphenat} % Disables auto-hyphenation globally
  ```
* **Automated PDF Parsing Audit (`renderers/resume.py` or separate check):**
  Right after compiling `SAGAR_MARTHANDAN_Resume.pdf` in Step 2:
  1. Load the generated PDF using `pypdf` and extract the text layer:
     ```python
     import pypdf
     reader = pypdf.PdfReader("SAGAR_MARTHANDAN_Resume.pdf")
     pdf_text = "".join(page.extract_text() for page in reader.pages)
     ```
  2. Check for **unicode corruptions** (e.g., replacement glyphs `\uFFFD`).
  3. Run a **Keyword Recovery Check**: Cross-reference the extracted text against a list of critical keywords/tools from `Resume.yaml` (e.g. `dbt`, `Snowflake`, `Airflow`, `Python`). If a keyword is missing (or fractured due to font/unicode mapping issues), fail the audit and output the missing keywords.
  4. Write the results to `Layout_Audit_Report.yaml` under:
     ```yaml
     parse_integrity_verification:
       status: "Pass/Fail"
  5. **Resilient Recovery (ReportLab Fallback):**
     If the LaTeX PDF fails the parse-integrity check (recovery < 100% or unicode corruptions found):
     * Print a loud warning detailing the failed keywords.
     * Automatically trigger the ReportLab compiler (`create_resume_pdf_reportlab`) as a fallback to overwrite the PDF with a standard, highly parsable PDF.
     * Run the parse-integrity check on the fallback ReportLab PDF. If that also fails, halt the pipeline. If it passes, log the fallback recovery and proceed to Step 3.
     This guarantees that the pipeline never produces a PDF that is unreadable by Workday.


---

## 🧪 Phase 4: Testing & Verification

1. **Verify Linter:** Run `python okf_lint.py` to check that the newly updated portfolio markdown files with `repo_url` pass successfully.
2. **Verify Hybrid Search:** Run `zvec_hybrid_search.py` on a dummy JD and ensure `project_info.md` correctly distills the `Repo: <url>` line.
3. **Verify Diversity Audit:** Execute `python okf_diversity_audit.py` and inspect the terminal output warnings.
4. **Verify LaTeX Resume Generation & Preamble:** Compile a tailored resume with `repo_url` present and check the LaTeX source file for `glyphtounicode` and `hyphenat`.
5. **Verify Parse-Integrity Check:** Ensure the PDF compiler runs the `pypdf` extraction, writes a passing status in `Layout_Audit_Report.yaml`, and logs no keyword gaps or character corruptions. Open the resulting PDF, copy its text, and verify that ligatures (e.g. "efficient", "workflow") copy-paste correctly as single letters.
6. **Verify Obsidian Sync:** Run `python sync_to_obsidian.py` and verify that the vendor and source backlink notes are generated correctly in the vault.

---
---

# Refined Implementation Plan (Codebase-Verified)

> Derived from the plan above, but concretely mapped against the actual codebase state. Each task lists the exact file, function, and insertion point.

## Verified Codebase Facts
- **14 portfolio files** exist in `okf/portfolio/*.md` — none currently have `repo_url`.
- `parse_okf_file` (`okf_portfolio_search.py:225`) uses `yaml.safe_load` and passes through **all** frontmatter keys, so `repo_url` will be available to `distill_project` with no parser change needed.
- `renderers/resume.py` LaTeX preamble **already loads** `xcolor` (line 267) and `hyperref` (line 262) — so the `\href{...}{\color{darkblue}...}` injection in §3.4 will compile without new packages. Only `glyphtounicode` + `hyphenat` are new.
- Applications tree lives at `C:\Users\sagar\Documents\YAML-CV\Applications\YYYY\MM\DD\[Company] — [Role]\` (confirmed via `organize_applications.py` + `find_application_folders` in `sync_to_obsidian.py`).
- `sync_to_obsidian.py` already has `parse_ats_yaml`, `parse_ats_md`, `parse_application`, `generate_application_note`, `generate_entity_note`, and a `sync()` orchestrator with a `dirs` dict + index-note pattern — the vendor/source backlinks fit cleanly into this existing structure.
- YouTube project: **use profile fallback** `https://github.com/SagarMarthandan` (suspicious `SagarMagar` URL in original plan rejected).

---

## Phase 1 — Portfolio Metadata Enrichment (Data Layer)

### Task 1.1: Add `repo_url` to all 14 portfolio frontmatters
Insert `repo_url:` as the last frontmatter key (after `archetypes:`) in each `okf/portfolio/*.md`:
- `airbnb_data_engineering_project_dbt_snowflake_dagster.md` → `https://github.com/SagarMarthandan/DBT-Airbnb-Practice-Project`
- `nyc_taxi_analytics_pipeline_2025.md` → `https://github.com/SagarMarthandan/ny-taxi-pipeline-2025`
- `retrieval_augmented_generation_rag_pdf_query_system.md` → `https://github.com/SagarMarthandan/RAG-LLM-pdf-query`
- `youtube_e2e_advanced_data_engineering_pipeline.md` → `https://github.com/SagarMarthandan` (profile fallback)
- Remaining 10 files → `https://github.com/SagarMarthandan` (profile fallback)

### Task 1.2: Update `okf_lint.py` to validate `repo_url`
Add an optional-field validation block in `lint_file()` (after the keywords check, before `return violations`):
- If `repo_url` key is present, validate it's a string starting with `https://github.com/` or `https://`.
- If absent, no violation (optional field).
- Add `repo_url` to the `setdefault` calls in `parse_okf_file` so downstream code always has a key (default `""`).

---

## Phase 2 — Pipeline Schema Updates (Agent Guidelines)

### Task 2.1: Update `01_ats_and_jd_archival.md`
- **New subsection "0c. ATS Vendor Inference & Application Source"** (after 0b, before section 1): instruct the agent to scan JD text/URL for ATS footprints (`myworkdayjobs.com`→Workday, `personio.de`/`personio.com`→Personio, `successfactors.eu`/`.com`→SAP SuccessFactors, `greenhouse.io`→Greenhouse, `lever.co`→Lever, `taleo.net`→Taleo; default `Unknown`).
- **Application Source prompt**: ask user for `Cold Apply` / `Referral` / `LinkedIn Connection` / `Direct`. If `Cold Apply` + known vendor → emit weak-tie warning.
- **ATS_Report.yaml schema additions** (add 3 root keys after `closest_candidate_location`):
  ```yaml
  ats_vendor: "Personio"
  application_source: "Cold Apply"
  weak_tie_contact: null
  ```
- **Diversity audit hook**: add a command in the "Compilation & Portfolio Search Commands" section to run `okf_diversity_audit.py` after the linter, printing the diversity status report.

### Task 2.2: Update `02_resume_and_visual_audit.md`
- **Project Verification Links**: in section 1 (Document Rewrite), instruct the agent to read `Repo:` lines from `project_info.md` and copy them into each project block in `Resume.yaml` as `repo_url:`.
- **Resume Variation Strategy**: add a new subsection describing `resume_variation: Balanced | Project-Heavy | Skills-Heavy` with the tailoring rules from the plan. Add `resume_variation` to the `Resume.yaml` schema (top-level key).
- **LaTeX Polish update**: in section 4, update the single-paragraph format template to weave `\href{repo_url}{GitHub}` next to the project title when `repo_url` is present:
  ```latex
  \noindent\textbf{Project Name} (\href{repo_url}{GitHub}) --- [prose].\par
  ```
- **Resume.yaml schema**: add optional `repo_url:` field to each project entry.

### Task 2.3: Update `03_cover_letter.md`
- In "Narrative Rules", add: weave project `repo_url` links into paragraph deep dives where relevant; if `application_source` is `Referral`, mention the `weak_tie_contact` name/role in paragraph 1.

---

## Phase 3 — Script & Compiler Updates (Logic Layer)

### Task 3.1: Update `distill_project` + `distill_project_hybrid`
- **`okf_portfolio_search.py` `distill_project`** (line 434): after the `Archetypes:` line, add:
  ```python
  repo_url = proj.get("repo_url", "").strip()
  if repo_url:
      parts.append(f"Repo: {repo_url}")
  ```
- **`zvec_hybrid_search.py` `distill_project_hybrid`** (line 520): identical addition after the `Archetypes:` line.
- No change needed to `parse_okf_file` — `yaml.safe_load` already surfaces `repo_url`.

### Task 3.2: Create `okf_diversity_audit.py` (new file)
- **Config**: add `APPLICATIONS_DIR` and audit thresholds to `config.py`:
  ```python
  APPLICATIONS_DIR = os.getenv("YAML_CV_APPLICATIONS_DIR", os.path.join(PROJECT_ROOT, "Applications"))
  DIVERSITY_VENDOR_CLUSTER_THRESHOLD = 3
  DIVERSITY_REFERRAL_RATE_MIN = 0.20
  DIVERSITY_LOOKBACK_DAYS = 14
  ```
- **Script logic**:
  1. Walk `APPLICATIONS_DIR` using the same `YYYY/MM/DD/[Company] — [Role]` traversal as `find_application_folders` (reuse or mirror that logic).
  2. Parse each `ATS_Report.yaml` for `ats_vendor`, `application_source`, and the date from the path.
  3. Filter to last 14 days (based on path date).
  4. Count applications per vendor; flag any vendor with count ≥ 3.
  5. Compute referral rate = (`Referral` count) / (total); flag if < 20%.
  6. Print a formatted status report to stdout (warnings prefixed `WARNING:`).
  7. Exit 0 always (advisory only — don't block the pipeline).
- **Handle missing fields gracefully**: older applications won't have `ats_vendor`/`application_source` — skip them in the counts but note the count of legacy apps.

### Task 3.3: Update `sync_to_obsidian.py`
- **`parse_ats_yaml`** (line 393): add `ats_vendor`, `application_source`, `weak_tie_contact` to the result dict (read from `data.get(...)`).
- **`parse_ats_md`** (line 472): add regex extraction for `**ATS Vendor:** X` and `**Source:** Y` lines (MD format applications).
- **`parse_application`** (line 653): thread the 3 new fields into the returned app dict.
- **`generate_application_note`** (line 749): after the `**Role:**` line, append:
  ```
  **ATS Vendor:** [[{ats_vendor}]]
  **Source:** [[{application_source}]]
  **Referral Contact:** {weak_tie_contact or 'None'}
  ```
  (only emit vendor/source lines if non-empty; always emit referral contact line).
- **`sync()`** (line 824):
  - Add `vendor_apps` and `source_apps` `defaultdict(list)` aggregation maps.
  - Add `"vendors": OUTPUT_ROOT / "Job Search" / "Vendors"` and `"sources": OUTPUT_ROOT / "Job_Search" / "Sources"` to the `dirs` dict.
  - Write vendor backlink notes (one per vendor) and source backlink notes (one per source) using the existing `generate_entity_note` helper.
  - Add `Vendors Index.md` and `Sources Index.md` to the indexes dict.
  - Update the final print summary + dry-run block.

### Task 3.4: Update `renderers/resume.py` — repo_url href injection
- **LaTeX path** (`create_resume_pdf`, projects section ~line 192): after computing `proj_name`, inject:
  ```python
  repo_url = proj.get('repo_url', proj.get('url', ''))
  if repo_url:
      proj_name = f"{proj_name} (\\href{{{repo_url}}}{{\\color{{darkblue}}\\small[GitHub]}})"
  ```
  Place this **before** `escape_latex` is applied to `proj_name` — actually, the URL must NOT be escaped (it would break `\href`), so inject it **after** escaping the name. Adjust accordingly: escape the name first, then append the raw `\href` wrapper.
- **ReportLab path** (`create_resume_pdf_reportlab`, projects section ~line 520): append a clickable `<a href='...'>[GitHub]</a>` to the project header paragraph if `repo_url` present.

### Task 3.5: Parse-Integrity Validation (PDF Auditing)
- **LaTeX preamble safeguards** (`create_resume_pdf`, ~line 257): add to the preamble **before** `\begin{document}`:
  ```latex
  \input{glyphtounicode}
  \pdfgentounicode=1
  \usepackage[none]{hyphenat}
  ```
  Place after the existing `\usepackage{xcolor}` line. Note: `glyphtounicode` is a TeX file shipped with TeX Live/MiKTeX, not a package — `\input` is correct.
- **PDF parse-integrity audit function** (new function in `renderers/resume.py`):
  ```python
  def _audit_pdf_parse_integrity(pdf_path, resume_data):
  ```
  1. `import pypdf`; read the PDF; extract text from all pages.
  2. Check for `\uFFFD` replacement glyphs → corruption flag.
  3. Build a keyword list from `resume_data` (project tools + technical_skills categories' skills + key terms like `dbt`, `Snowflake`, `Airflow`, `Python`).
  4. For each keyword, check presence in extracted text (case-insensitive substring). Collect missing.
  5. Return a dict: `{"status": "Pass"/"Fail", "corruptions": [...], "missing_keywords": [...], "recovery_pct": int}`.
- **Wire into `create_resume_pdf`**: after the successful `run_pdflatex` call (in the `try` block, before the photo cleanup `finally`), run the audit on the output PDF. Write results into `Layout_Audit_Report.yaml` under a new `parse_integrity_verification` key (complete the truncated schema from the plan):
  ```yaml
  parse_integrity_verification:
    status: "Pass"  # Pass | Fail
    unicode_corruptions: []
    missing_keywords: []
    keyword_recovery_pct: 100
    fallback_triggered: false
  ```
  Use `yaml.safe_dump` to merge into the existing file if present, else create it.
- **ReportLab fallback trigger**: if audit status is `Fail` (recovery < 100% or corruptions found):
  1. Print a loud warning with the failed keywords.
  2. Call `create_resume_pdf_reportlab(data, output_path)` to overwrite the PDF.
  3. Re-run the audit on the ReportLab PDF.
  4. If that also fails → print error and raise (halt pipeline). If passes → log `fallback_triggered: true` and proceed.
- **Add `pypdf` to `requirements.txt`** (verify it's not already there first).

---

## Phase 4 — Testing & Verification

### Task 4.1: Linter verification
Run `python okf_lint.py` — confirm all 14 files pass with the new `repo_url` field.

### Task 4.2: Hybrid search distillation verification
Run `zvec_hybrid_search.py` on a dummy JD; confirm `project_info.md` contains `Repo: https://github.com/...` lines for matched projects.

### Task 4.3: Diversity audit verification
Run `python okf_diversity_audit.py` — confirm it walks the Applications tree, prints vendor counts, and emits warnings (or "no applications in lookback window" if tree is sparse).

### Task 4.4: LaTeX resume generation + preamble verification
Compile a tailored resume with `repo_url` present; confirm the `.tex` source contains `glyphtounicode`, `hyphenat`, and the `\href{...}{\color{darkblue}\small[GitHub]}` injection.

### Task 4.5: Parse-integrity check verification
Confirm the PDF compiler runs the `pypdf` extraction, writes `parse_integrity_verification` to `Layout_Audit_Report.yaml`, and logs no keyword gaps or corruptions. Manually copy-paste ligature words ("efficient", "workflow") from the PDF to confirm clean text.

### Task 4.6: Obsidian sync verification
Run `python sync_to_obsidian.py --dry-run` — confirm vendor/source counts appear in the summary; then full run and verify `Job Search/Vendors/` and `Job_Search/Sources/` notes are generated.

### Task 4.7: Existing test suite
Run the existing tests in `tests/` (`test_okf_search.py`, `test_hybrid_search.py`, `test_utils.py`) to confirm no regressions from the `distill_project` changes.

---

## Execution Order (dependency-safe)
1. **Phase 1** (Tasks 1.1, 1.2) — data first so the linter and search scripts have `repo_url` to work with.
2. **Phase 3.1** (distill functions) — small, isolated edit; unblocks Phase 4.2.
3. **Phase 3.2** (`okf_diversity_audit.py` + `config.py`) — standalone new file.
4. **Phase 3.3** (`sync_to_obsidian.py`) — independent of renderer changes.
5. **Phase 3.4 + 3.5** (`renderers/resume.py`) — the largest single-file change; do href injection, preamble, and parse-integrity audit together.
6. **Phase 2** (markdown doc updates) — update the agent instruction files to reflect the new schema/behavior.
7. **Phase 4** — run all verification tasks.

## Risks / Notes
- **`glyphtounicode` availability**: shipped with TeX Live and MiKTeX standard installs. If your TeX distribution lacks it, compilation will fail with a clear "File not found" error — easy to diagnose. Verify it exists on your system during Task 4.4.
- **`hyphenat` with `[none]`**: disables all hyphenation globally. This is the intended behavior for ATS parsability but may cause slightly more line wraps in long words — the existing 105-char bullet limit and 300-char project limit already account for single-line constraints.
- **`pypdf` dependency**: lightweight, pure-Python, no native deps. Safe to add.
- **Older applications** in `Applications/` won't have `ats_vendor`/`application_source` — the diversity audit and Obsidian sync handle this gracefully (skip/empty).
