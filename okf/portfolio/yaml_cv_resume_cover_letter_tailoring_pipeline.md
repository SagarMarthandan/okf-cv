---
title: YAML-CV Resume & Cover Letter Tailoring Pipeline
description: ATS-optimized resume and cover letter pipeline using hybrid search (OKF phrase matching + Zvec semantic embeddings), YAML configs, LaTeX compilation, and self-learning keyword enrichment.
technologies: Python, LaTeX, PyYAML, ReportLab, Zvec, Sentence-Transformers, pypdf
keywords:
- hybrid search
- okf phrase matching
- zvec semantic embeddings
- score fusion
- ats optimization
- latex compilation
- self-learning keyword enrichment
- obsidian vault sync
- frontmatter linter
- archetype scoring
- jaccard normalization
- synonym expansion
- fuzzy matching
- offline search
- cross-process locking
archetypes:
- Agentic/Automation
- Backend/Platform Engineering
---

# YAML-CV Resume & Cover Letter Tailoring Pipeline

A premium, production-grade **end-to-end resume tailoring and application optimization pipeline** integrated directly inside an agentic workspace. It uses structured YAML configurations, local LaTeX compilation, and a **hybrid search engine** combining OKF 4-layer phrase matching with Zvec semantic embeddings (all-MiniLM-L6-v2) via score fusion to dynamically select and rank relevant engineering projects from a master portfolio.

---

### Tech Stack & Integrations

- **Python 3.12** (Core execution environment)
- **Zvec** (Local embedded vector database engine for semantic search)
- **Sentence-Transformers** (`all-MiniLM-L6-v2` for 100% offline local embeddings, 384-dim vectors)
- **OKF** (Open Knowledge Format — 4-layer phrase matching: exact, synonym expansion, light stemming, fuzzy token matching)
- **LaTeX / pdflatex** (Primary resume and cover letter compilation engine)
- **ReportLab** (Synchronous fallback PDF rendering engine)
- **PyYAML & JSON** (Structured data serialization and audit reports)
- **Obsidian** (Vault sync for graph-view navigation of applications, companies, roles, skills, and projects)

---

## Hybrid Search Architecture (OKF + Zvec)

The portfolio search runs 100% locally and offline using score fusion:

- **OKF Phrase Matching (weight 0.6):** 4-layer matching strategy — exact phrase matching, bidirectional synonym map (50+ domain terms), light stemming (suffix stripping for morphological variants), fuzzy token matching (difflib SequenceMatcher, 0.85 threshold for typo tolerance). Jaccard-style normalization prevents JD-length bias. Archetype boosts (+10 primary, +5 secondary) applied when ATS_Report.yaml is provided.
- **Zvec Semantic Embeddings (weight 0.4):** All portfolio files embedded using all-MiniLM-L6-v2, stored in local Zvec database. Incremental re-embedding via content hash detection — only changed files re-embedded. Catches conceptual matches OKF cannot see (e.g., "event streaming platform" matching a Kafka project).
- **Score Fusion:** `final = (okf_score * 0.6) + (zvec_scaled * 0.4)`. Zvec cosine similarity scaled to OKF score range for comparability. Weights configurable in config.py.
- **Self-Learning Flywheel:** After each application, okf_learn.py extracts JD terms found in matched project bodies but missing from keyword lists, appends them (max 3 per project, 15 per file, linter-validated with rollback), and automatically re-embeds modified files into the Zvec database. Both search layers improve over time.
- **Cross-Process Safety:** All Zvec DB operations protected by zvec_db_lock() — OS-level file locking (msvcrt on Windows, fcntl on Unix) with infinite wait (no timeout, agents wait indefinitely until lock is released) and 0.5s retry. CPU-bound work (embeddings, hashing) runs outside the lock. Enables safe parallel execution across 10+ agents — they queue for DB access instead of crashing with lock errors.

---

## Pipeline Architecture

The pipeline operates in three sequential phases plus three post-pipeline steps:

### Step 1: ATS Analysis, JD Archival & Hybrid Project Search
- Dependency ingest, language detection (English/German), ATS pre-scoring (4-category matrix, 100 points, score gate >= 85 to PROCEED).
- Frontmatter linter (okf_lint.py) validates all portfolio files before scoring.
- Hybrid search engine runs OKF phrase matching + Zvec semantic embeddings, fuses scores, writes top matching projects to project_info.md with full diagnostics (OKF score, Zvec cosine, fused score).
- Location tailoring via web search to find closest candidate city.
- Outputs: ATS_Report.yaml/.pdf, Job_Description.yaml/.pdf, project_info.md.

### Step 2: Resume Rewrite & Visual Layout Audit
- Generates Resume.yaml tailored to role archetype and retrieved projects.
- LaTeX compilation with single-paragraph project format (<= 300 chars, <= 3 lines).
- Visual layout audit: experience bullets <= 105 chars single-line, summary exactly 4 lines <= 420 chars.
- Stop-Slop writing rules: strict active voice, no -ly adverbs, zero em-dashes, no filler text.
- Post-rewrite ATS rescoring.
- Outputs: Resume.yaml, SAGAR_MARTHANDAN_Resume.pdf, Layout_Audit_Report.yaml.

### Step 3: Cover Letter Generation
- German Geschaftsbrief layout (DIN 5008), metric-grounded prose.
- Strict limits: one page, 4 paragraphs, 250-320 words (180-240 for German).
- Outputs: Cover_Letter.yaml, SAGAR_MARTHANDAN_Cover_Letter.pdf.

### Post-Pipeline Step 1: Self-Learning Keyword Enrichment
- okf_learn.py extracts domain-relevant JD terms, finds them in matched project bodies, appends as keywords.
- Linter-validated with rollback, max 3 per project per run, 15 per file cap.
- Modified files automatically re-embedded into Zvec database.
- Full audit trail in okf/learning_log.json.

### Post-Pipeline Step 2: Obsidian Vault Sync
- sync_to_obsidian.py walks Applications/ tree, generates linked Obsidian notes.
- One note per application, company, role archetype, skill, and project.
- Wikilinks for graph-view navigation. Handles YAML and MD formats.

### Post-Pipeline Step 3: Application Folder Sorting
- organize_applications.py moves application folder into Applications/YYYY/MM/DD/[Company] - [Role]/.
- Idempotent, date-bucketed by folder creation time.