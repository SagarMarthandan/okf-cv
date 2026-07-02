[//]: # (DEVELOPER DOCUMENTATION ONLY — not part of agent runtime context. Do not read this file during pipeline execution.)
# 📄 OKF-CV Resume & Cover Letter Tailoring Pipeline

An end-to-end, high-scannability, and ATS-optimized application materials generation pipeline. It uses structured YAML files for configuration, compiles them to PDF/LaTeX, and leverages Google OKF (Open Knowledge Format) matching to dynamically rank and inject relevant engineering projects from a master portfolio directory based on a target Job Description (JD).

---

## 🗺️ Architectural Workflow

The following diagram illustrates the data flow, offline semantic search, and the three-stage generation lifecycle:

```mermaid
graph TD
    %% Base Styling — vibrant palette
    classDef input fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fffbeb;
    classDef processing fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#eff6ff;
    classDef output fill:#10b981,stroke:#059669,stroke-width:2px,color:#ecfdf5;
    classDef system fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#f5f3ff;
    classDef learn fill:#ec4899,stroke:#be185d,stroke-width:2px,color:#fdf2f8;
    classDef sync fill:#06b6d4,stroke:#0891b2,stroke-width:2px,color:#ecfeff;
    classDef sort fill:#f97316,stroke:#c2410c,stroke-width:2px,color:#fff7ed;

    %% Subgraph styles
    style Step1 fill:#1e3a8a10,stroke:#3b82f6,stroke-width:2px,color:#1e3a8a
    style Step2 fill:#05966910,stroke:#10b981,stroke-width:2px,color:#059669
    style Step3 fill:#7c3aed10,stroke:#8b5cf6,stroke-width:2px,color:#7c3aed
    style Post1 fill:#be185d10,stroke:#ec4899,stroke-width:2px,color:#be185d
    style Post2 fill:#0891b210,stroke:#06b6d4,stroke-width:2px,color:#0891b2
    style Post3 fill:#c2410c10,stroke:#f97316,stroke-width:2px,color:#c2410c

    %% Elements
    JD["📋 Raw Job Description"]:::input
    BaseFiles["📄 Base Files: resume.md / resume_de.md"]:::input
    RepoInfo["🗂️ Master Portfolio: portfolio/"]:::input

    subgraph Step1 ["Step 1: ATS Analysis and JD Archival"]
        Deps["📦 pip install -r requirements.txt"]:::system
        ATS["🎯 ATS Score Gate — 4-Category scoring matrix"]:::processing
        Lint["✅ okf_lint.py — Frontmatter validation"]:::processing
        OKF["🔍 Hybrid Search — OKF 4-Layer + Zvec Semantic"]:::processing
    end

    subgraph Step2 ["Step 2: Resume Rewrite and Visual Audit"]
        Rewrite["✏️ Resume.yaml Generation — Role Archetype Tuning"]:::processing
        LaTeX["📐 LaTeX Polish — Single-paragraph project format"]:::processing
        Audit["🔬 Visual Layout Audit — Layout_Audit_Report.yaml"]:::processing
    end

    subgraph Step3 ["Step 3: Cover Letter Generation"]
        CL["✉️ Geschaeftsbr. Generation — Cover_Letter.yaml"]:::processing
    end

    subgraph Post1 ["Post-Pipeline Step 1: Self-Learning"]
        Learn["🧠 okf_learn.py — Keyword enrichment from JD"]:::learn
    end

    subgraph Post2 ["Post-Pipeline Step 2: Obsidian Sync"]
        Sync["🔗 sync_to_obsidian.py — Linked vault notes"]:::sync
    end

    subgraph Post3 ["Post-Pipeline Step 3: Folder Sort"]
        Sort["📁 organize_applications.py — YYYY/MM/DD tree"]:::sort
    end

    %% Pipeline Outputs
    OutJD["📄 Job_Description.yaml / .pdf"]:::output
    OutATS["📊 ATS_Report.yaml / .pdf"]:::output
    OutProj["📝 project_info.md — Tailored Project List"]:::output
    OutRes["📄 Resume.yaml / SAGAR_MARTHANDAN_Resume.pdf"]:::output
    OutCL["✉️ Cover_Letter.yaml / SAGAR_MARTHANDAN_Cover_Letter.pdf"]:::output
    OutLog["📋 okf/learning_log.json — Enrichment audit trail"]:::output
    OutVault["🔮 Obsidian Vault — Job Search notes"]:::output
    OutTree["📁 Applications/YYYY/MM/DD/[Company] — [Role]/"]:::output

    %% Flow Connections
    JD --> Deps
    Deps --> ATS
    BaseFiles --> ATS

    ATS --> Lint
    RepoInfo --> Lint
    Lint --> OKF
    JD --> OKF

    ATS --> OutATS
    ATS --> OutJD
    OKF --> OutProj

    OutProj --> Rewrite
    OutATS --> Rewrite
    Rewrite --> LaTeX
    LaTeX --> Audit
    Audit --> OutRes

    OutProj --> CL
    OutRes --> CL
    CL --> OutCL

    OutCL --> Learn
    OutProj --> Learn
    Learn --> OutLog

    OutLog --> Sync
    Sync --> OutVault

    OutVault --> Sort
    Sort --> OutTree
```

---

## � Hybrid Search Architecture (OKF + Zvec)

The portfolio search runs **100% locally and offline** using a hybrid approach that combines Google's **Open Knowledge Format (OKF)** phrase matching with **Zvec semantic embeddings** for score fusion:

- **Hybrid Search Engine:** [zvec_hybrid_search.py](zvec_hybrid_search.py) runs both OKF and Zvec search, then fuses scores: `final = (okf_score * 0.6) + (zvec_sim * 0.4)`. OKF provides precision for exact/synonym/stem/fuzzy matches. Zvec provides semantic recall for conceptual matches OKF can't see (e.g., "event streaming platform" → Kafka project).
- **OKF Bundle Structure:** The master portfolio is structured as a directory of modular Markdown files under `okf/portfolio/`, each carrying metadata in its YAML frontmatter block (e.g., `title`, `description`, `technologies`, `keywords`, and `archetypes`).
- **OKF Matching Algorithm (4-layer):** The OKF component ([okf_portfolio_search.py](okf_portfolio_search.py)) uses a 4-layer matching strategy:
  1. **Exact phrase matching** — multi-word phrases as substrings, single words with word boundaries (no false positives from token splitting)
  2. **Synonym/alias expansion** — bidirectional map of 50+ domain terms (e.g., `kafka` ↔ `message queue`, `dbt` ↔ `transformation framework`, `terraform` ↔ `infrastructure as code`, `rag` ↔ `retrieval augmented generation`)
  3. **Light stemming** — strips common English suffixes (`-tion`, `-ing`, `-er`, `-ed`, `-es`, `-s`) for morphological variant matching (`orchestration` ↔ `orchestrator`, `pipeline` ↔ `pipelines`)
  4. **Fuzzy token matching** — `difflib.SequenceMatcher` with 0.85 ratio threshold for typo tolerance (`Databrick` → `Databricks`, `kuberntes` → `kubernetes`)
- **OKF Scoring:** Jaccard-style normalization prevents JD-length bias. Archetype boosts (+10 primary, +5 secondary) are applied when `ATS_Report.yaml` is provided. Tiebreaker: archetype match count, then tech match count, then alphabetical. Configurable `top_k` via CLI argument (default 4).
- **Zvec Semantic Layer:** All 14 portfolio files are embedded using `all-MiniLM-L6-v2` (384-dim vectors) and stored in a local Zvec database under `okf/zvec_db/`. Incremental re-embedding via content hash detection — only changed files are re-embedded. When `okf_learn.py` adds new keywords, modified files are automatically re-embedded into the Zvec database.
- **Score Fusion:** Zvec cosine similarity (0-1) is scaled to the OKF score range, then weighted: `final = (okf_score * 0.6) + (zvec_scaled * 0.4)`. Weights are configurable in `config.py` (`HYBRID_OKF_WEIGHT`, `HYBRID_ZVEC_WEIGHT`).
- **Cross-Process Safety:** All Zvec DB operations (ingestion, query, re-embed) are protected by a cross-process file lock (`zvec_db_lock()`). Uses OS-level locking (`msvcrt` on Windows, `fcntl` on Unix) with infinite wait (no timeout) and 0.5s retry interval. Agents wait indefinitely until the lock is released — no chance of concurrent access errors. CPU-bound work (embedding computation, hash detection) runs outside the lock to minimize hold time.
- **Frontmatter Linter:** [okf_lint.py](okf_lint.py) validates all portfolio files before scoring: checks for non-empty fields, canonical archetypes, denylisted tech tokens, description length, keyword count, and title-token overlap. Fails loud with the offending file + field.
- **Self-Learning Loop:** [okf_learn.py](okf_learn.py) runs post-application to enrich portfolio keywords from real JDs. Extracts domain-relevant terms, finds them in matched projects' bodies, and appends as new keywords. Max 3 per project per run, 15 per file cap, linter-validated with rollback, full audit trail in `okf/learning_log.json`.
- **Obsidian Vault Sync:** [sync_to_obsidian.py](sync_to_obsidian.py) syncs all applications to the Obsidian vault as linked notes (applications, companies, roles, skills, projects) for graph-view navigation and knowledge management.
- **Distilled Output:** The top matched projects are written to `project_info.md` as compact summaries (title + description + tech + archetypes + body summary + match diagnostics comment) for use in Step 2.

---

## ��️ Step-by-Step Execution Guide

The entire process is organized into 3 primary sequential steps, executed automatically by the agent when you supply a Job Description, followed by three post-pipeline steps (self-learning enrichment, Obsidian vault sync, and folder sorting):

### STEP 1: Setup, ATS Analysis & Job Description Archival
- **Name the Session (First Action):** Before any pipeline work, extract the Company Name and Job Role from the JD and rename the agent session/conversation to `[Company Name] — [Job Role]` in the UI sidebar. This makes it easy to identify which agent is handling which application when running multiple agents in parallel.
- **Dependency Ingest:** Automatically installs/updates pip dependencies (`pyyaml`, `reportlab`, `pypdf`) using Python 3.12.
- **Language Detection:** Identifies whether the JD is in English or German and loads corresponding base resume files.
- **ATS Pre-Scoring:** Grades the base resume against a calibrated 4-category German-market matrix (max 100 points).
  - **Score Gate:** If the ATS score is `< 85`, the pipeline triggers a `HOLD` verdict, presenting specific remedy suggestions (e.g., missing keywords, project mismatches). If `>= 85`, it sets `PROCEED`.
- **Frontmatter Lint:** Runs `okf_lint.py` to validate all portfolio files have clean YAML frontmatter (non-empty fields, canonical archetypes, no denylisted tech tokens, keyword quality checks). Fails before scoring if any violation is found.
- **Hybrid Project Selector:** Programmatically searches the local portfolio using a hybrid search engine ([zvec_hybrid_search.py](zvec_hybrid_search.py)) that combines OKF 4-layer phrase matching (exact, synonym, stemming, fuzzy) with Zvec semantic embeddings (all-MiniLM-L6-v2), archetype-boosted scoring (+10 primary, +5 secondary from `ATS_Report.yaml`), and Jaccard-style normalization. Score fusion: `final = (okf * 0.6) + (zvec * 0.4)`. Writes the top matching projects to a tailored `project_info.md` file with full hybrid diagnostics (OKF score, Zvec cosine, fused score).
- **Location Tailoring:** Extracts the job location from the job description and uses web search to determine the closest candidate location among Kiel (home), Frankfurt (friend), Berlin (friend), and Köln (friend).
- **Outputs:** `ATS_Report.yaml` & `Job_Description.yaml` (plus their compiled `.pdf` documents) and the tailored `project_info.md`.
- **Naming Convention (Critical):** The application folder and session name MUST be `[Company Name] — [Job Role]` extracted directly from the JD content. No arbitrary names, timestamps, or placeholders. This makes it easy to identify which session is running which application when multiple agents run in parallel.

### STEP 2: Resume Rewrite & Visual Layout Audit
- **Tuned Resume Generation:** Writes `Resume.yaml` by tailoring descriptions, skills, and summary to align with the target role archetype and the retrieved local projects, and sets the contact location to the computed closest candidate city.
- **LaTeX Compilation & Project Format Polish:** Generates a professional LaTeX resume (`SAGAR_MARTHANDAN_Resume.tex` or `SAGAR_MARTHANDAN_Lebenslauf.tex` for German) and converts project listings from standard bullet points into a compact, single-paragraph prose block with tools woven in naturally.
- **Uniform Spacing:** All project and experience entries are separated by a consistent `\vspace{6pt}` — no double-spacing, no variable gaps.
- **Constraints & Eye-Test Audit:** Runs character-length audits:
  - Experience bullets: Must be strictly single-line and `<= 105` characters.
  - Project paragraphs: Must be `<= 300` characters total (`<= 250` characters for German projects) and fit within `<= 3` lines.
  - Summary: Exactly 4 lines of text, maximum 420 characters (maximum 380 characters for German Zusammenfassung).
  - Stop-Slop writing rules: Strict active voice, no `-ly` adverbs, zero em-dashes, no filler text.
- **Self-Correction:** Resolves any line-wraps or overflows dynamically.
- **Post-Rewrite ATS Rescoring:** Updates `post_rewrite_ats_score` in `ATS_Report.yaml` and recompiles `ATS_Report.pdf`.
- **Outputs:** `Resume.yaml`, `SAGAR_MARTHANDAN_Resume.pdf` / `SAGAR_MARTHANDAN_Lebenslauf.pdf` (along with preserved LaTeX `.tex` sources), `Layout_Audit_Report.yaml`, and the post-rewrite ATS rescoring results updated inside `ATS_Report.yaml`.

### STEP 3: Cover Letter Generation
- **Geschäftsbrief Layout:** Generates a metric-grounded cover letter adapted to formal German business formatting, set to the computed closest candidate location (both in the sender address and date/city header).
- **Strict Limits:** Restricts cover letter content to exactly one page, 4 paragraphs, and **250–320 words** total (restricted to **180–240 words** for German cover letters to prevent A4 overflow).
- **Outputs:** `Cover_Letter.yaml` and compiled `SAGAR_MARTHANDAN_Cover_Letter.pdf` / `SAGAR_MARTHANDAN_Anschreiben.pdf` (along with preserved LaTeX `.tex` sources).

### Post-Pipeline Step 1: Self-Learning Keyword Enrichment
- **Keyword Learning:** After the cover letter compiles, [okf_learn.py](okf_learn.py) extracts domain-relevant terms from the processed Job Description, finds terms that appear in matched projects' bodies but are missing from their keyword lists, and appends them.
- **Safeguards:** Max 3 new keywords per project per run, 15 keywords per file max (linter enforced with rollback), every change logged to `okf/learning_log.json` with timestamp and JD source.
- **Idempotent:** Re-running on the same application folder is a no-op (no duplicate keywords added).

### Post-Pipeline Step 2: Obsidian Vault Sync
- **Graph-View Navigation:** After the learning loop, [sync_to_obsidian.py](sync_to_obsidian.py) walks the entire `Applications/` tree and generates linked Obsidian notes under `<vault>/Job Search/`.
- **Note Types:** One note per application, company, role archetype, skill, and project. Wikilinks connect applications to companies, roles, skills, and projects for graph-view navigation.
- **Format Support:** Handles both YAML and MD application formats automatically.
- **Standalone Use:** Run `python sync_to_obsidian.py` to sync all applications, or use `--dry-run` to preview without writing.

### Post-Pipeline Step 3: Application Folder Sorting
- **Prerequisite:** Obsidian sync (Step 2) MUST complete successfully before this step. Do NOT run `organize_applications.py` until `sync_to_obsidian.py` has finished — the folder must remain at `Applications/[Company Name] — [Job Role]/` during sync so the sync script can find it.
- **Date-Organized Tree:** After Obsidian sync succeeds, [organize_applications.py](organize_applications.py) moves the just-created application folder into `Applications/YYYY/MM/DD/[Company Name] — [Job Role]/`, bucketed by the folder's creation time.
- **Idempotent:** Re-running the script is a no-op on already-sorted folders.
- **Standalone Use:** Run `python organize_applications.py` to sort all existing unsorted folders in `Applications/`, or `python organize_applications.py "Applications/[Company] — [Role]"` to sort a single folder. Use `--dry-run` to preview moves without applying them.

---

## 📂 Project Directory Structure

```
YAML-CV/
├── skills\
│   └── okf-cv\
│       ├── SKILL.md                      # Agent-facing skill metadata
│       ├── README.md                     # This file (developer documentation)
│       ├── OKF_IMPROVEMENT_PLAN.md       # OKF improvement plan & Phase 6 design
│       ├── 01_ats_and_jd_archival.md     # Step 1 detailed agent rules
│       ├── 02_resume_and_visual_audit.md # Step 2 detailed agent rules
│       ├── 03_cover_letter.md            # Step 3 detailed agent rules
│       ├── requirements.txt              # Pipeline dependencies (pyyaml, reportlab, pypdf)
│       ├── config.py                     # Centralized paths and constants
│       ├── yaml_to_pdf.py                # Main YAML compilation router
│       ├── zvec_hybrid_search.py       # Hybrid search (OKF phrase matching + Zvec semantic embeddings, score fusion)
│       ├── okf_portfolio_search.py       # OKF search engine (4-layer matching, archetype boost, Jaccard normalization) — fallback if Zvec unavailable
│       ├── okf_lint.py                   # Frontmatter linter for portfolio files
│       ├── okf_learn.py                  # Self-learning keyword enrichment (post-application)
│       ├── sync_to_obsidian.py           # Syncs applications to Obsidian vault as linked notes
│       ├── organize_applications.py      # Sorts application folders into YYYY/MM/DD tree (post-pipeline)
│       ├── okf/                          # Self-contained OKF Knowledge Base
│       │   ├── portfolio/                # 14 individual OKF project markdown files
│       │   ├── zvec_db/                  # Zvec vector database (auto-generated, hash-indexed for incremental re-embedding)
│       │   ├── base_files/
│       │   │   ├── english/              # English base resume.md
│       │   │   └── german/               # German base resume_de.md
│       │   ├── photo/                    # Sagar.jpg for LaTeX templates
│       │   └── learning_log.json         # Self-learning enrichment audit trail
│       ├── renderers\                    # LaTeX/ReportLab rendering handlers
│       │   ├── utils.py                  # Shared utilities (escape_latex, fonts, run_pdflatex)
│       │   ├── resume.py                 # Resume renderer (LaTeX primary, ReportLab fallback)
│       │   ├── cover_letter.py           # Cover Letter renderer (LaTeX primary, ReportLab fallback)
│       │   ├── job_description.py        # Job Description renderer (ReportLab only)
│       │   └── ats_report.py             # ATS Report renderer (ReportLab only)
│       └── tests/
│           ├── test_utils.py             # Unit tests for LaTeX escaping and formatting
│           └── test_okf_search.py        # Automated test suite for OKF search
└── Applications\
    └── YYYY\
        └── MM\
            └── DD\
                └── [Company Name] — [Job Role]\      # Application folder (sorted by creation date)
                    ├── Job_Description.yaml / .pdf
                    ├── ATS_Report.yaml / .pdf
                    ├── project_info.md               # Tailored & distilled project list
                    ├── Resume.yaml / Layout_Audit_Report.yaml / Cover_Letter.yaml
                    ├── SAGAR_MARTHANDAN_Resume.pdf / .tex  (or Lebenslauf.pdf / .tex for German)
                    └── SAGAR_MARTHANDAN_Cover_Letter.pdf / .tex  (or Anschreiben.pdf / .tex for German)
```

---

## 🚀 How to Run the Pipeline

Since all the pipeline steps are natively codified into the agent's custom skills directory, you do not need to copy-paste any external prompts.

To execute the pipeline:
1. Paste the target **Job Description** (JD) into the chat.
2. Type: **`execute okf-cv`** (or keywords like *"tailor resume"* / *"optimize resume"*).
3. The agent will automatically run the end-to-end flow: installing dependencies, linting portfolio frontmatter, searching matching projects using hybrid search (OKF phrase matching + Zvec semantic embeddings with score fusion), compiling the ATS reports, writing the final tailored files to the `Applications/` directory, enriching portfolio keywords via the self-learning loop (with automatic Zvec re-embedding), syncing to the Obsidian vault, and sorting the application folder into the `Applications/YYYY/MM/DD/` date tree.

---

## 🧪 Testing

Run the automated test suite to verify search relevance:
```powershell
cd "[skill directory]"
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\tests\test_okf_search.py"
```

The suite includes 3 test cases:
1. **Data Engineering search** with archetype boost — verifies DE projects rank in top-3
2. **AI/RAG Developer search** with dual archetype — verifies RAG project ranks #1
3. **Smoke test** with generic DE JD — verifies at least 2 expected DE projects appear in top-3

Run the hybrid search standalone (OKF + Zvec score fusion):
```powershell
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\zvec_hybrid_search.py" "Job_Description.yaml" "project_info.md" "ATS_Report.yaml"
```

Run the frontmatter linter standalone:
```powershell
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\okf_lint.py"
```

Run the self-learning loop standalone:
```powershell
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\okf_learn.py" "Applications/[Company Name] — [Job Role]"
```

Sync applications to Obsidian vault:
```powershell
C:\Users\sagar\AppData\Local\Programs\Python\Python312\python.exe "C:\Users\sagar\Documents\YAML-CV\skills\okf-cv\sync_to_obsidian.py"
```

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history (v1–v23).
