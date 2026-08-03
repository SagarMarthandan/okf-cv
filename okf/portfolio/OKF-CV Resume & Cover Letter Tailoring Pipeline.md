---
title: OKF-CV Resume & Cover Letter Tailoring Pipeline
description: ATS-optimized resume and cover letter pipeline with URL scraping, hybrid search (OKF + Zvec semantic embeddings), YAML configs, LaTeX compilation, parse-integrity audits, and self-learning.
technologies: Python, LaTeX, PyYAML, ReportLab, Zvec, Sentence-Transformers, pypdf, Jina Reader
keywords:
- hybrid search
- score fusion
- ats optimization
- zvec semantic embeddings
- okf phrase matching
- parse-integrity audit
- self-learning keyword enrichment
- obsidian vault sync
- url scraping
- jina reader
- din 5008
- windows file-lock recovery
- algorithmic monoculture
- embedding daemon
- anti-spinning protocol
archetypes:
- Agentic/Automation
- Backend/Platform Engineering
repo_url: https://github.com/SagarMarthandan/okf-cv
---

# OKF-CV Resume & Cover Letter Tailoring Pipeline

An end-to-end, ATS-optimized application materials generation pipeline. It uses structured YAML files for configuration, compiles them to PDF via LaTeX (with a ReportLab fallback), and leverages a **hybrid search engine** combining Google OKF (Open Knowledge Format) phrase matching with Zvec semantic embeddings to dynamically rank and inject relevant engineering projects from a master portfolio directory based on a target Job Description (JD). An optional Step 0 scrapes the JD directly from a job posting URL — no manual copy-paste required.

The pipeline also counters **algorithmic monoculture** — the Stanford-studied phenomenon where repetitive ATS algorithmic filtration narrows opportunity. It tracks applicant-firm clustering by ATS vendor, prompts for application source diversification (referrals vs cold applies), highlights project verification links (clickable GitHub URLs on the resume), offers resume layout variations, lets the user choose between LaTeX and ReportLab (LM Roman 10) rendering modes, and runs an automated PDF parse-integrity audit that verifies the compiled PDF's text layer is ATS-parseable.

---

## Hybrid Search Architecture (OKF + Zvec)

The portfolio search runs **100% locally and offline** using score fusion:

- **OKF Phrase Matching (weight 0.6):** 4-layer matching strategy:
  1. **Exact phrase matching** — multi-word phrases as substrings, single words with word boundaries (no false positives from token splitting)
  2. **Synonym/alias expansion** — bidirectional map of 50+ domain terms (`kafka` ↔ `message queue`, `dbt` ↔ `transformation framework`, `terraform` ↔ `infrastructure as code`, `rag` ↔ `retrieval augmented generation`)
  3. **Light stemming** — strips common English suffixes (`-tion`, `-ing`, `-er`, `-ed`, `-es`, `-s`) for morphological variant matching (`orchestration` ↔ `orchestrator`)
  4. **Fuzzy token matching** — `difflib.SequenceMatcher` with 0.85 ratio threshold for typo tolerance (`Databrick` → `Databricks`)
  - Jaccard-style normalization prevents JD-length bias. Archetype boosts (+10 primary, +5 secondary) applied when `ATS_Report.yaml` is provided. Tiebreaker: archetype match count, then tech match count, then alphabetical. Configurable `top_k` via CLI (default 4).
- **Zvec Semantic Embeddings (weight 0.4):** All portfolio files embedded using `all-MiniLM-L6-v2` (384-dim vectors), stored in a local Zvec database under `okf/zvec_db/`. Incremental re-embedding via content hash detection — only changed files are re-embedded. Catches conceptual matches OKF cannot see (e.g., "event streaming platform" → Kafka project).
- **Score Fusion:** `final = (okf_score * 0.6) + (zvec_scaled * 0.4)`. Zvec cosine similarity (0-1) is scaled to the OKF score range, then weighted. Weights are configurable in `config.py` (`HYBRID_OKF_WEIGHT`, `HYBRID_ZVEC_WEIGHT`).
- **Cross-Process Safety:** All Zvec DB operations (ingestion, query, re-embed) are protected by `zvec_db_lock()` — OS-level file locking (`msvcrt` on Windows, `fcntl` on Unix) with infinite wait (no timeout) and 0.5s retry interval. Agents wait indefinitely until the lock is released. CPU-bound work (embedding computation, hash detection) runs outside the lock to minimize hold time. Enables safe parallel execution across 10+ agents.
- **Embedding Daemon:** A local TCP daemon (127.0.0.1, ports 54321-54325) holds the `all-MiniLM-L6-v2` model in memory. The pipeline invokes the hybrid search 3 times per run (pre-rewrite similarity, portfolio search, post-rewrite similarity) — without the daemon, each invocation loads the model fresh (~21s on CPU, ~63s total wasted). The daemon is pre-warmed in Step 1 before the hybrid search runs (eliminating the ~70s cold start on Windows CPU), auto-started via `_ensure_daemon()` with Windows-safe creationflags (`CREATE_BREAKAWAY_FROM_JOB | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`), and auto-shuts down after 30 min of inactivity. Falls back to direct model loading if unavailable (pipeline still works, just slower).

---

## Pipeline Architecture

The pipeline operates in an optional Step 0 (URL scraping), three sequential phases, and two post-pipeline steps:

### Step 0 (optional): JD Fetch — URL → Job Description Text

Runs only when the user pastes a job posting URL instead of raw JD text. If the user pastes raw JD text directly, Step 0 is skipped.

- **Hybrid scraping strategy:** Known JS-SPA vendors (LinkedIn, Workday, Greenhouse, Lever, SuccessFactors, Personio) go straight to **Jina Reader** (`https://r.jina.ai/<url>`) — a free service that returns clean markdown of the fully rendered page (handles JS rendering, cookie/consent walls). Static / Unknown vendors try the agent's local `webfetch` first, then Jina as a fallback. Optional `JINA_API_KEY` env var for higher rate limits.
- **JD-shape validation:** Scraped text must pass a heuristic gate — role title + company signal + ≥2 JD section markers (`requirements`, `responsibilities`, `qualifications`, `experience`, `we are looking for`, `about the role`, plus German equivalents `anforderungen`, `profil`, `aufgaben`, `wir suchen`) + >200 chars + not a login/error page.
- **Manual-paste fallback:** If both scrape strategies fail (rate limit, login wall, failed validation), the user is prompted to paste the JD manually. For JS-SPA vendors where Jina fails, the doomed `webfetch` attempt is skipped — the user is prompted to paste immediately. Manual paste is always available and never locked out.
- **URL-hash cache:** Scraped JDs cached at `okf/.jd_cache/<sha1(url)>.txt` (7-day TTL) so re-runs skip re-scraping. `source_url` recorded in `Job_Description.yaml` for traceability.

### Step 1: ATS Analysis, JD Archival & Hybrid Project Search
- **Session naming:** Extract Company Name and Job Role from the JD and rename the agent session to `[Company Name] — [Job Role]` (critical for parallel agent identification).
- **Dependency check:** Cached import probe (`okf/.dep_check.json`, 24hr cache) — only runs `pip install` if an import actually fails.
- **Embedding daemon pre-warm:** Calls `_ensure_daemon()` from `zvec_hybrid_search.py` to pre-warm the daemon before hybrid search runs — the SentenceTransformer model is loaded into memory in a background process before the search needs it, eliminating the ~70s cold start on Windows CPU. If unavailable, falls back to direct model loading (~21s per invocation).
- **Language detection & archetype selection:** English/German, role archetype (Data Engineer, Data Analyst, Analytics Engineer, AI Data Engineer), loads matching archetype-specific base resume.
- **ATS pre-scoring:** 4-category German-market matrix (max 100 points). Score gate: `< 85` triggers `HOLD` with remedy suggestions, `>= 85` sets `PROCEED`.
- **Frontmatter lint:** `okf_lint.py` validates all portfolio files (non-empty fields, canonical archetypes, no denylisted tech tokens, keyword quality, `repo_url` format). Content-hash cache skips unchanged files; `--force` ignores the cache.
- **ATS vendor inference & application source:** Scans JD text/URL for ATS footprints (Workday, Personio, SAP SuccessFactors, Greenhouse, Lever, Taleo). Prompts for application source (Cold Apply, Referral, LinkedIn Connection, Direct). Cold Apply + known vendor triggers a weak-tie warning. Saves `ats_vendor`, `application_source`, `weak_tie_contact` to `ATS_Report.yaml`.
- **Hybrid project selector:** Runs OKF 4-layer + Zvec semantic search with archetype-boosted scoring and Jaccard normalization. Writes top matching projects to `project_info.md` with full hybrid diagnostics (OKF score, Zvec cosine, fused score) and `Repo:` lines for verification links.
- **Location tailoring:** Static geocode table maps common German job locations to the nearest candidate city (Kiel, Frankfurt, Berlin, Köln). Falls back to web search for unknown locations, cached permanently in `okf/.location_cache.json`. Remote/unspecified defaults to Kiel.
- **Skill gap analysis (P2):** Cross-references JD-required skills against base resume and matched projects; stored as `skill_gaps` in `ATS_Report.yaml`.
- **Contextual placement weighting (P4):** Checks which resume sections contain each critical JD keyword; applies placement multipliers (1.0x skills, 1.2x projects, 1.3x experience, 1.5x multiple). Stored as `placement_breakdown`.
- **Pre-rewrite semantic similarity (P1):** Cosine similarity between base resume and JD via `resume_jd_similarity.py` (all-MiniLM-L6-v2). Stored as `pre_rewrite_similarity` for before/after tracking.
- **Outputs:** `ATS_Report.yaml`/`.pdf`, `Job_Description.yaml`/`.pdf`, tailored `project_info.md`.

### Step 2: Resume Rewrite & Visual Layout Audit
- **Render mode & resume style selection:** User chooses between `LaTeX` (pdflatex, `.tex` source preserved, optional prose refinement) and `ReportFallback` (ReportLab with LM Roman 10, no `.tex` file). Also chooses `US Style` or `German Style` (Lebenslauf section order). Both stored in `Resume.yaml`.
- **Tuned resume generation:** Writes `Resume.yaml` tailored to role archetype and retrieved projects; sets contact location to the computed closest candidate city. Three `resume_variation` modes: `Balanced` (default — 3 projects, 4 experience bullets), `Project-Heavy` (4 verbose projects, simplified skills), `Skills-Heavy` (3 projects, expanded skills block).
- **Dynamic section ordering:** Data-driven from `resume_style`. US style: Summary → Technical Skills → Projects → Professional Experience → Education → Spoken Languages. German style: Summary → Professional Experience → Education → Technical Skills → Spoken Languages (no separate Projects section — 3 JD-aligned projects fold into Professional Experience as `project_bullets` under an "Independent Data Engineering & Professional Development" entry in `name --- [GitHub] --- summary` format with quantified metrics). A resume YAML may override the order per-application via a top-level `section_order` key.
- **Project verification links:** Reads `Repo:` lines from `project_info.md` and copies them into each project block as `repo_url:`. Compiled as clickable `[GitHub]` links in both LaTeX (`\href{repo_url}{\color{darkblue}\small[GitHub]}`) and ReportLab (`<a href='...'>[GitHub]</a>`).
- **LaTeX compilation & project format:** Projects rendered in `name --- [GitHub] --- summary` single-paragraph format (YAML `bullets` joined into prose). Project name, em-dash separators, and link markup are excluded from the char count — only summary text counts toward `<= 300` chars (English) / `<= 280` chars (German). Tools stay in YAML for the parseability audit but are not displayed in the project header. Preamble includes `glyphtounicode` and `hyphenat` safeguards to prevent font ligature corruption and auto-hyphenation in ATS PDF-to-text parsers.
- **Uniform spacing:** All project and experience entries separated by consistent `\vspace{6pt}` — no double-spacing, no variable gaps.
- **Constraints & eye-test audit:**
  - Experience bullets: strictly single-line, `<= 105` characters.
  - Project summaries: `<= 300` chars (`<= 280` German), `<= 3` lines.
  - Summary: exactly 2 lines, max 250 chars (max 230 German Zusammenfassung).
  - Stop-Slop writing rules: strict active voice, no `-ly` adverbs, zero em-dashes, no filler text.
- **Parse-integrity audit (LaTeX mode):** After LaTeX compilation, the PDF is automatically audited via `pypdf` — extracts the text layer, checks for Unicode replacement glyphs (U+FFFD), cross-references critical keywords/tools from `Resume.yaml` against the extracted text. On failure (recovery < 100% or corruptions found), the ReportLab compiler is triggered as a fallback to overwrite the PDF; the fallback PDF is re-audited and the pipeline halts if it also fails. Results written to `Layout_Audit_Report.yaml` under `parse_integrity_verification`.
- **Resume parseability audit (both modes):** `resume_parseability.py` runs a standalone parse-integrity audit on the final PDF — the actual document submitted to companies. Checks: (1) Unicode integrity, (2) keyword recovery (every tool/skill/summary word recoverable from the PDF text, with line-break splitting handled via whitespace normalization), (3) section header detection (style-aware: US style checks 6 headers, German style checks 5), (4) contact info extraction (name, phone, email, GitHub, LinkedIn), (5) text structure stats. Outputs `Parseability_Report.yaml` + `Parseability_Report.pdf` (LM Roman 10). Pass criteria: 100% keyword recovery, all sections, 5/5 contact fields, zero unicode corruptions. Exit 0 = pass, 1 = fail, 2 = error.
- **Post-rewrite ATS rescoring:** Updates `post_rewrite_ats_score` in `ATS_Report.yaml` and recompiles `ATS_Report.pdf`. Also computes post-rewrite cosine similarity via `resume_jd_similarity.py`, stored as `post_rewrite_similarity`.
- **Outputs:** `Resume.yaml`, `SAGAR_MARTHANDAN_Resume.pdf` / `SAGAR_MARTHANDAN_Lebenslauf.pdf` (with preserved `.tex` sources), `Layout_Audit_Report.yaml`, `Parseability_Report.yaml`/`.pdf`, post-rewrite ATS rescoring in `ATS_Report.yaml`.

### Step 3: Cover Letter Generation
- **DIN 5008 Form B layout:** Metric-grounded cover letter adapted to formal German business formatting, set to the computed closest candidate location (sender address and date/city header). Both renderers produce a DIN 5008 Form B-style layout: Anschriftfeld (small single-line sender line above the recipient block, suitable for window envelopes), right-aligned date, bold subject (Betreff), salutation, body, closing + signature, an `Anlagen:` (enclosures) section after the signature, and a footer line with phone/email at the bottom of the page.
- **Gender-tag stripping:** German job postings commonly append gender-equality tags to role titles (e.g., `Application for Analyst (w/m/f)`, `Bewerbung als Entwickler (m/w/d)`). The `strip_gender_tags()` helper in `renderers/utils.py` strips these from the subject line at render time via a regex matching parentheticals containing only single letters from `{w, m, f, d, x}` separated by slashes. Meaningful parentheticals are preserved. The YAML keeps the original subject — only the PDF output is cleaned.
- **Application source integration:** If `application_source` is `Referral` or `LinkedIn Connection`, mentions the `weak_tie_contact` name/role in paragraph 1. GitHub is referenced in plain language (e.g., "see my GitHub for the full implementation") — raw `repo_url` links are NOT inserted into cover letter prose. A single generic reference to the GitHub portfolio is sufficient; individual repositories are not linked.
- **Enclosures (Anlagen):** Optional `enclosures` field in the cover letter YAML schema (list of strings). When present, an `Anlagen:` section is rendered after the signature listing the enclosed documents (e.g., `Lebenslauf`, `Zeugnisse`). Omitted when absent — backward compatible.
- **Strict limits:** Exactly one page, 4 paragraphs, **250–320 words** total (**180–240 words** for German cover letters to prevent A4 overflow).
- **Outputs:** `Cover_Letter.yaml`, `SAGAR_MARTHANDAN_Cover_Letter.pdf` / `SAGAR_MARTHANDAN_Anschreiben.pdf` (with preserved `.tex` sources).

### Post-Pipeline Step 1: Self-Learning Keyword Enrichment
- `okf_learn.py` extracts domain-relevant terms from the processed JD, finds terms that appear in matched projects' bodies but are missing from their keyword list, and appends them.
- **ATS score delta tracking (P3):** Each learning log entry includes `pre_rewrite_ats_score` and `post_rewrite_ats_score`, creating a longitudinal dataset of which keyword enrichments and project selections correlate with the biggest ATS score improvements.
- **Safeguards:** Max 3 new keywords per project per run, 15 keywords per file max (linter enforced with rollback), every change logged to `okf/learning_log.json` with timestamp, JD source, and ATS scores.
- **Automatic Zvec re-embedding:** Modified files are automatically re-embedded into the Zvec database via `reembed_file()`. Non-blocking — fails gracefully if Zvec unavailable.
- **Idempotent:** Re-running on the same application folder is a no-op.

### Post-Pipeline Step 2: Obsidian Vault Sync + Folder Sort
- `sync_to_obsidian.py` syncs the application to the Obsidian vault as linked notes under `<vault>/Job Search/`.
- **Targeted sync:** The pipeline passes the application folder as a positional argument for incremental sync — only this application's notes are written, and the relevant entity/index notes are patched (append with dedup). Use `--full` to force a complete rebuild.
- **Note types:** One note per application, company, role archetype, skill, project, ATS vendor, and application source. Wikilinks connect applications to companies, roles, skills, projects, vendors, and sources for graph-view navigation. Vendor and source backlink notes visualize clustering immediately in Obsidian's Graph View.
- **Format support:** Handles both YAML and MD application formats automatically. Parses `ats_vendor`, `application_source`, and `weak_tie_contact` from both formats.
- **Folder sort (`--sort` flag):** After syncing, moves the application folder into `Applications/YYYY/MM/DD/[Company Name] — [Job Role]/`, bucketed by the folder's creation time. Replaces the separate Post-Pipeline Step 3.
- **Windows file-lock recovery:** Folder moves are wrapped in `_resilient_move()` in `obsidian_folder_sort.py` — a 3-retry loop with `gc.collect()` + 0.5s delay between attempts to release lingering file handles (`[WinError 32]`). If all rename attempts fail, falls back to `shutil.copytree` + `shutil.rmtree` — which works even when a directory handle is held open (copytree reads file contents; rmtree removes entries individually rather than renaming).

---

## Agent Execution & Anti-Spinning Protocol

In agentic IDEs (Devin, Claude Code, Oh My Pi), the step docs enforce a **Tool-Call Execution Protocol** to prevent loop-guard interrupts:

- **Tool-call priority:** Never emit multi-paragraph planning prose, un-called YAML drafts, or consecutive Markdown headers in pure text without issuing a tool call. Every turn must perform concrete tool actions (`write`, `edit`, `exec`).
- **Terse commentary:** Limit reasoning prose before a tool call to 1 concise sentence describing the immediate action.
- **Batch tool calls:** When multiple independent file writes or edits are needed, issue them in a single turn (parallel tool calls) rather than one-per-turn with prose between each.

This prevents the UI buffer clears (large blank vertical gaps) and forced tool-call retries that occur when the agent outputs 20+ planning headers without a tool call.

---

## Key Scripts

- **`zvec_hybrid_search.py`** — Hybrid search engine (OKF + Zvec score fusion). CLI: `<jd_path> <out_path> [ats_report_path] [top_k]` or `--similarity <resume_path> <jd_path>`. Auto-starts and pre-warms the embedding daemon via `_ensure_daemon()`.
- **`okf_portfolio_search.py`** — OKF-only search engine (4-layer matching, archetype boost, Jaccard normalization). Fallback if Zvec/sentence-transformers are not installed.
- **`embedding_server.py`** — Local TCP daemon holding the SentenceTransformer model in memory (auto-started, 30-min idle shutdown). Manual control: `--status` / `--stop`.
- **`okf_lint.py`** — Frontmatter linter. Content-hash cache skips unchanged files; `--force` lints all.
- **`okf_learn.py`** — Self-learning keyword enrichment (post-application).
- **`okf_diversity_audit.py`** — Standalone weekly clustering audit (vendor clustering + referral rate warnings). Advisory only — not run per application.
- **`resume_parseability.py`** — ATS parse-integrity audit on the compiled PDF. `--check-tex` mode runs the LaTeX project summary length check (same `<= 300`/`<= 280` char limits).
- **`resume_jd_similarity.py`** — Cosine similarity between resume and JD (pre/post-rewrite alignment metric).
- **`sync_to_obsidian.py`** — Syncs applications to Obsidian vault as linked notes. `--sort` moves the folder into the date tree.
- **`obsidian_folder_sort.py`** — Folder-sort logic with Windows file-lock recovery (`_resilient_move`). Extracted from `sync_to_obsidian.py` for standalone use.
- **`organize_applications.py`** — Standalone folder sorter into `Applications/YYYY/MM/DD/` tree (thin shim over `obsidian_folder_sort.py`).
- **`obsidian_sync_core.py`** — Core Obsidian sync logic (note generation, entity/index notes, targeted sync).
- **`okf_utils.py`** — Shared OKF utilities (synonyms, stemming, fuzzy matching).
- **`yaml_to_pdf.py`** — Main YAML compilation router (resume, cover_letter, job_description, ats_report, parseability_report). `--tex-only` writes `.tex` without running pdflatex.
- **`config.py`** — Centralized paths and constants with env var override support.

---

## Countering Algorithmic Monoculture

Integrated findings from the Stanford study on algorithmic monoculture. The pipeline acts as a buffer against repetitive algorithmic filtration:

- **ATS vendor tracking:** Infers ATS vendor from JD text/URL footprints (Workday, Personio, Greenhouse, etc.) and stores it per application.
- **Application source diversification:** Prompts for source (Cold Apply, Referral, LinkedIn Connection, Direct) and warns on Cold Apply + known vendor to check the network for weak ties.
- **Project verification links:** Clickable `[GitHub]` links next to each project on the resume provide verifiable evidence.
- **Resume layout variations:** `Balanced` / `Project-Heavy` / `Skills-Heavy` modes avoid submitting identical resumes to the same ATS vendor.
- **Render mode choice:** LaTeX vs ReportLab (LM Roman 10) lets the user pick the most ATS-parseable output for a given vendor.
- **Parse-integrity audit:** Automated PDF text-layer audit verifies the compiled resume is machine-readable by ATS parsers (unicode integrity, keyword recovery, section headers, contact info).
- **Weekly diversity audit:** `okf_diversity_audit.py` reports vendor clustering (warns at ≥3 applications to the same vendor in 14 days) and referral rate (warns at <20%). Advisory only.
