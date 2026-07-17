# Pipeline Step 1: ATS Check & Job Description Archival

> **READ-ONLY SKILL FILES — HARD GUARDRAIL:** The `renderers/` directory, all top-level pipeline scripts (`zvec_hybrid_search.py`, `okf_portfolio_search.py`, `okf_lint.py`, `embedding_server.py`, etc.), `okf/base_files/`, `okf/portfolio/`, and all pipeline step docs are **PERMANENTLY READ-ONLY** during this step. The model MUST NOT edit, patch, or modify any of these files. **The ONLY files the model writes in this step are** `ATS_Report.yaml`, `Job_Description.yaml`, `Job_Description.pdf`, and `project_info.md` (inside the current application folder). This rule has no exceptions.

## Objective
Analyze the target job description (JD) against the candidate's base resume and project portfolio to detect gaps, classify the role archetype, calculate an ATS score, and structure the clean JD for archival.

## Inputs
- **Job Description (JD):** Paste target JD text at the bottom.
- **Base Resume & Portfolio:** Loaded from the local `okf/` folder inside the skill directory. Archetype-specific base resumes are selected based on the JD's role archetype (e.g. `okf/base_files/english/resume_data_engineer.md`, `okf/base_files/english/resume_data_analyst.md`, `okf/base_files/english/resume_analytics_engineer.md`, `okf/base_files/english/resume_ai_data_engineer.md`). Falls back to `okf/base_files/english/resume.md` for unmatched archetypes. German equivalents use `_de` suffix (e.g. `resume_data_engineer_de.md`).

## Execution Rules

### 0a. Name the Session
Per SKILL.md §"Name the Session" — extract Company Name and Job Role from the JD and rename this session to `[Company Name] — [Job Role]`.

### 0b. Pre-Scoring: Verify Dependencies & Load Base Files
Before any scoring or analysis, perform the following verification and loading steps:
1. **Dependency Check (24hr cache):** The agent verifies that all required packages are importable, but only once per 24 hours. A cache file at `okf/.dep_check.json` records the last successful check timestamp. On each run:
   - Read `okf/.dep_check.json`. If it exists and the timestamp is less than 24 hours old, skip the import probe entirely — dependencies are already verified.
   - If the file is missing, older than 24 hours, or the import probe has never run, execute the import probe and (on success) write the current timestamp to the cache file:
   ```powershell
    C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe -c "import json,os,time; cache='C:/Users/sagar/Documents/YAML-CV/skills/okf-cv/okf/.dep_check.json'; skip=False; 
if os.path.exists(cache):
    try:
        data=json.load(open(cache)); skip=(time.time()-data.get('ts',0))<86400
    except: pass
if not skip:
    import subprocess,sys; r=subprocess.run([sys.executable,'-c','import yaml, reportlab, pypdf, zvec, sentence_transformers'],capture_output=True)
    if r.returncode!=0: subprocess.run([sys.executable,'-m','pip','install','-q','-r','C:/Users/sagar/Documents/YAML-CV/skills/okf-cv/requirements.txt'])
    json.dump({'ts':time.time()},open(cache,'w')); print('Dependency check completed and cached for 24hrs.')
else: print('Dependency check skipped (cached within 24hrs).')
   ```
   This avoids running the import probe on every application. The cache is automatically invalidated after 24 hours.
2. **Frontmatter Lint:** Run the OKF linter to verify portfolio metadata is clean before scoring:
   ```powershell
   C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\okf_lint.py"
   ```
   If the linter fails, fix the offending frontmatter before proceeding.
3. **Load base resume:** Load the candidate's base resume from the detected language folder. The pipeline uses **archetype-specific base resumes** to maximize pre-rewrite ATS scores:
   - First, detect the JD's primary role archetype from the job title and description. The supported archetypes are:
     - `Data Engineer` → `resume_data_engineer.md`
     - `Data Analyst` → `resume_data_analyst.md`
     - `Analytics Engineer` → `resume_analytics_engineer.md`
     - `AI Data Engineer` → `resume_ai_data_engineer.md`
   - Load the matching archetype base resume from `okf/base_files/english/` (or `okf/base_files/german/` for German JDs — append `_de` to the filename, e.g. `resume_data_engineer_de.md`).
   - If the archetype doesn't match any of the 4 specific bases, fall back to the generic `resume.md` (or `resume_de.md` for German).
   *(Note: You do not need to load the global project_info.md file in Step 1, because the OKF search command in Step 1 will dynamically generate a tailored project_info.md file inside the application folder).*

Do not proceed to scoring without first running the dependency installation, the linter, and loading the base resume file. All gap analysis and keyword comparisons must reference the loaded resume content.

### 0c. ATS Vendor Inference & Application Source
Before scoring, gather monoculture-counter metadata:

1. **ATS Vendor Inference:** Scan the JD text and any target application URL for common ATS system footprints:
   - `myworkdayjobs.com` → `Workday`
   - `personio.de` / `personio.com` → `Personio`
   - `successfactors.eu` / `successfactors.com` → `SAP SuccessFactors`
   - `greenhouse.io` → `Greenhouse`
   - `lever.co` → `Lever`
   - `taleo.net` → `Taleo`
   - If none found, default to `Unknown`.
2. **Application Source Selection:** Prompt the user for the application source. Valid values: `Cold Apply`, `Referral`, `LinkedIn Connection`, `Direct`.
   - If the source is `Cold Apply` and the vendor is known (not `Unknown`), output a warning advising the user to check their network for weak ties before submitting.
   - If the source is `Referral` or `LinkedIn Connection`, prompt for the optional `weak_tie_contact` (name or role of the contact).

> **Note:** The diversity audit (`okf_diversity_audit.py`) is no longer run automatically per application. It is a standalone tool for weekly review — see the README "Weekly Review" section.

### 1. Requirements & Archetype Detection
- Scan candidate-facing profile requirements.
- Classify the JD into exactly one primary role archetype (e.g., Data Engineering, Analytics Engineering, Data Analyst, AI Engineer, AI/LLMOps, Agentic/Automation, ML Engineering, Backend/Platform Engineering).
- Save selection and a one-sentence rationale under `role_archetype` in the YAML output.
- **Secondary archetype:** If the JD clearly spans two domains (e.g., requires both ML engineering and data platform work), assign a `secondary` archetype with its own one-sentence rationale. If the JD is focused on a single domain, omit the `secondary` field entirely.

### 2. German-Market ATS Scoring Matrix
- Grade the current resume against a German-market calibrated matrix (0-100 total) using **4 equally-weighted categories** (25 points each):
  - `keywords_and_terminology` (max 25)
  - `experience_relevance` (max 25)
  - `technical_skills` (max 25)
  - `soft_skills_and_language` (max 25)
- **Formatting is NOT scored.** Instead, emit a separate non-scored `formatting_quality` verdict (see below) that classifies the resume's formatting/parsability as one of `Excellent`, `Good`, `Average`, or `Bad`. If the verdict is `Average` or `Bad`, populate `suggestions` with concrete fixes. This keeps formatting feedback visible without diluting the 100-point score.
- Save category details and total score in `ats_score_matrix`, and the formatting verdict in `formatting_quality`, in the YAML output.
- **Score Gate:** If `total_score < 85`, set `score_gate_verdict: HOLD` and stop the pipeline. Populate `remedy_suggestions` as a structured list (see schema). Warn the user to review remedies before proceeding to Step 2. If `>= 85`, set `score_gate_verdict: PROCEED`.

### 3. Skill Gap Analysis (P2)
After scoring and project selection, extract a `skill_gaps` list:
- Extract a `required_skills` list from the JD — technologies, tools, and methodologies explicitly mentioned as required or strongly preferred.
- Collect `resume_skills` from the base resume's technical skills section and `project_skills` from the matched projects in `project_info.md` (technologies + keywords).
- Compute `skill_gaps = required_skills - (resume_skills ∪ project_skills)`.
- Store the result as a flat list of strings under `skill_gaps` in `ATS_Report.yaml`.
- The agent uses this list during Step 2 to make targeted additions where justified (add to skills section, weave into project descriptions, or note as genuine gaps).

### 4. Contextual Placement Weighting (P4)
After the 4-category ATS score is computed, perform a contextual placement check on critical JD keywords:
- Extract the top critical keywords from the JD (the same keywords used in the `keywords_and_terminology` scoring category).
- For each keyword, check which sections of the base resume contain it: `skills`, `projects`, or `experience`.
- Apply a placement multiplier per keyword:
  - Found in skills section only: **1.0x**
  - Found in project summary only: **1.2x**
  - Found in experience bullet only: **1.3x**
  - Found in multiple sections: **1.5x**
  - Not found: omit from the list (already captured in `skill_gaps` or `keyword_inventory`)
- Store results under `placement_breakdown` in `ATS_Report.yaml`:
  ```yaml
  placement_breakdown:
    keywords:
      - keyword: "Kafka"
        sections_found: ["skills", "projects", "experience"]
        multiplier: 1.5
  ```
- This sub-report is informational — it does not change the 4-category score. It highlights where evidence-based keyword usage is strong (multiple sections) and where it is weak (skills section only).

### 5. Pre-Rewrite Semantic Similarity (P1)
After writing `ATS_Report.yaml` and `Job_Description.yaml`, compute the pre-rewrite cosine similarity between the base resume and the JD:
```powershell
cd "Applications/[Company Name] — [Job Role]/"
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\zvec_hybrid_search.py" --similarity "[base_resume_path]" "Job_Description.yaml"
```
The base resume path is the archetype-specific file loaded in Step 0b (e.g., `okf/base_files/english/resume_data_engineer.md`). Write the returned float value to `resume_jd_semantic_similarity.pre_rewrite_similarity` in `ATS_Report.yaml`. (The `--similarity` flag uses the same model as the hybrid search, avoiding a second model load.)

### 6. Improvement Blueprint Generation
Populate each field of `improvement_blueprint` as follows:
- **`bullet_point_density_audit`:** For each bullet in the base resume's experience and projects sections, check if it contains a quantified metric (number, percentage, or time unit). List any bullets that are metric-free as items requiring quantification.
- **`project_swap_directive`:** Compare each project in the portfolio against the JD archetype. List projects that are misaligned under `remove_projects`. List archetype-aligned projects from `project_info.md` that are not currently in the base resume under `add_projects`, each with a one-sentence `justification`. Confirm exactly 3 (or 4 if score improves) are selected.
- **`keyword_inventory`:** Extract only JD keywords that are **absent from the base resume** (gap-only approach). Do not list keywords already present. Categorize absences into `hard_skills`, `methodologies`, and `domain_terms`.
- **`technical_skills_tuning`:** List tools/technologies to add (present in JD, absent from resume skills section) and to remove (present in resume skills section but irrelevant or distracting for this role).
- **`quantified_outcomes`:** For each metric-free bullet identified in the density audit, suggest a concrete revised version that adds a plausible quantified outcome.

### 7. Job Description Archival & Location Extraction
- Strip web tracking, cookies, duplicate fields, and metadata from the raw JD.
- Extract the job location from the raw JD (e.g., Munich, Berlin, Remote, etc.). Save it under a top-level `location` field in `Job_Description.yaml`.
- Structure into clean YAML sections (overview, requirements, responsibilities, stack) for permanent reference.

### 8. Candidate Location Selection
- The candidate has 4 candidate cities: **Kiel** (home), **Frankfurt**, **Berlin**, and **Köln**.
- **Static lookup + cache first:** Check the job location against the static geocode table and the persistent location cache in `config.py`. Run this Python one-liner to resolve:
  ```powershell
  C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe -c "from config import nearest_candidate_city; print(nearest_candidate_city('[job_location]') or 'NOT_FOUND')"
  ```
  This checks the static `JOB_LOCATION_TO_CANDIDATE_CITY` table first, then falls back to `okf/.location_cache.json` (which stores locations previously resolved via web search). If either hits, no web search is needed.
- **Web search fallback:** If the lookup returns `NOT_FOUND`, use **web search** to determine which of the 4 cities is geographically nearest to the job location. Then cache the result so future applications with the same location skip the web search:
  ```powershell
  C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe -c "from config import cache_location_result; cache_location_result('[job_location]', '[resolved_city, Germany]')"
  ```
- For remote, country-wide, or unspecified locations, default to **Kiel, Germany**.
- Save the result (e.g. `Frankfurt, Germany`) under `closest_candidate_location` in the root of `ATS_Report.yaml`.

## Output Target & Directory Structure
Create folder `Applications/[Company Name] — [Job Role]/` and save three files:
- `ATS_Report.yaml`
- `Job_Description.yaml`
- `project_info.md` (tailored project portfolio generated via OKF search)

**Naming Convention:** Per SKILL.md — folder MUST be `Applications/[Company Name] — [Job Role]/`. No arbitrary names or timestamps.

### A. `ATS_Report.yaml` Schema
```yaml
type: ats_report
company: "[Company Name]"      # Used by the PDF renderer for the report title
position: "[Job Position Title]"  # Used by the PDF renderer for the report subtitle
closest_candidate_location: "[Closest candidate location (Kiel, Frankfurt, Berlin, or Köln) determined via web search]"
ats_vendor: "[Inferred ATS vendor (Workday, Personio, SAP SuccessFactors, Greenhouse, Lever, Taleo, or Unknown)]"
application_source: "[Cold Apply, Referral, LinkedIn Connection, or Direct]"
weak_tie_contact: null  # Optional name/role of referral or LinkedIn contact
role_archetype:
  primary: "[Archetype Name]"
  secondary: "[Secondary Archetype — omit this field if JD is single-domain]"
  archetype_rationale: "[One sentence rationale for primary]"
  secondary_rationale: "[One sentence rationale for secondary — omit if secondary omitted]"
ats_score_matrix:
  keywords_and_terminology: { max_score: 25, current_score: 0, evaluation_criteria: "..." }
  experience_relevance: { max_score: 25, current_score: 0, evaluation_criteria: "..." }
  technical_skills: { max_score: 25, current_score: 0, evaluation_criteria: "..." }
  soft_skills_and_language: { max_score: 25, current_score: 0, evaluation_criteria: "..." }
  total_score: 0
formatting_quality:
  verdict: "Excellent"   # one of: Excellent | Good | Average | Bad
  notes: "[Optional one-line rationale]"
  suggestions: []        # Populate ONLY when verdict is Average or Bad
core_score_detractors: []
skill_gaps: []              # JD-required skills/technologies not present in base resume or matched projects
resume_jd_semantic_similarity:
  pre_rewrite_similarity: null  # Cosine similarity (base resume ↔ JD) — computed via resume_jd_similarity.py
  # post_rewrite_similarity: populated by Step 2 only
placement_breakdown:        # Contextual keyword placement weighting (P4)
  keywords: []
  # Each entry: { keyword: "...", sections_found: ["skills", "projects", "experience"], multiplier: 1.5 }
  # Multipliers: skills=1.0x, project summary=1.2x, experience bullet=1.3x, multiple sections=1.5x
improvement_blueprint:
  target_language_confirmation: "German/English"
  bullet_point_density_audit:
    - bullet: "[Exact bullet text from base resume]"
      issue: "No quantified metric"
  project_swap_directive:
    remove_projects: []
    add_projects: [{ name: "...", justification: "..." }]
    volume_constraint_check: "3 projects selected"
  keyword_inventory:
    hard_skills: []      # JD keywords absent from resume only
    methodologies: []    # JD methodologies absent from resume only
    domain_terms: []     # JD domain terms absent from resume only
  technical_skills_tuning:
    add: []
    remove: []
  quantified_outcomes:
    - original: "[Metric-free bullet]"
      suggested: "[Revised bullet with quantified outcome]"
  ats_threshold_calibration:
    meets_target: false
    score_gate_verdict: "HOLD/PROCEED"
    remedy_suggestions:
      - "[Specific action: e.g., swap Project X for Project Y from portfolio]"
      - "[Specific action: e.g., add missing keyword 'dbt' to Technical Skills]"
      - "[Specific action: e.g., rewrite IBM bullet 3 to include a throughput metric]"
# post_rewrite_ats_score: populated by Step 2 only — do not fill during Step 1.
#   Includes: ats_score_matrix, score_delta, post_rewrite_similarity, formatting_quality, score_gate_verdict, remaining_gaps
```

### B. `Job_Description.yaml` Schema
```yaml
type: job_description
company: "[Company Name]"
position: "[Job Position Title]"
location: "[Job Location — extracted from the job description]"
sections:
  - title: "Core Role Overview & Context"
    content: "[Overview paragraph]"
  - title: "Target Profile Requirements"
    bullets:
      - "[Requirement]"
  - title: "Primary Responsibilities"
    bullets:
      - "[Responsibility]"
  - title: "Tech Stack & Tooling"
    bullets:
      - "[Tool/Skill]"
```

## Compilation & Portfolio Search Commands
Run the hybrid search and the compiler immediately after writing the files to generate the assets:
```powershell
cd "Applications\[Company Name] — [Job Role]\"

# 1. Search and generate the tailored project list using hybrid search (OKF + Zvec)
#    Pass ATS_Report.yaml as 3rd arg for archetype-boosted scoring
#    Uses score fusion: final = (okf_score * 0.6) + (zvec_sim * 0.4)
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\zvec_hybrid_search.py" "Job_Description.yaml" "project_info.md" "ATS_Report.yaml"

# 2. Compile ATS Report
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\yaml_to_pdf.py" "ATS_Report.yaml" "ATS_Report.pdf"

# 3. Compile Job Description
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\yaml_to_pdf.py" "Job_Description.yaml" "Job_Description.pdf"
```

---
### ATTACHMENTS FOR PROCESSING
Paste the raw Job Description text below this line.
