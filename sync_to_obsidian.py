#!/usr/bin/env python3
"""
sync_to_obsidian.py — Bridge script that walks the YAML-CV Applications tree
and emits linked Obsidian notes into the vault for graph-view navigation.

Handles two application formats:
  - YAML format (older): ATS_Report.yaml, Job_Description.yaml, Resume.yaml, ...
  - MD format  (newer): ATS_Report.md, Job_Description.md, Resume.md, ...

Generates notes under <vault>/Job Search/:
  Applications/  — one note per application
  Companies/     — one note per company
  Roles/         — one note per role archetype
  Skills/        — one note per skill extracted from JDs
  Projects/      — one note per project used in applications
  * Index.md     — index notes listing all entries in each category

Usage:
  python sync_to_obsidian.py [--dry-run] [--verbose]

Config:
  APPLICATIONS_DIR and VAULT_DIR at the top of this file.
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run: pip install pyyaml")

# ─── Config ───────────────────────────────────────────────────────────────────

APPLICATIONS_DIR = Path(r"C:\Users\sagar\Documents\YAML-CV\Applications")
VAULT_DIR = Path(r"C:\Users\sagar\Documents\Obsidian Vault")
OUTPUT_ROOT = VAULT_DIR / "Job Search"

# ─── Helpers ──────────────────────────────────────────────────────────────────

EM_DASH = "\u2014"  # —
EN_DASH = "\u2013"  # –


def slugify(name: str) -> str:
    """Sanitize a string for use as an Obsidian note filename."""
    # Replace characters that are problematic in filenames / wikilinks
    name = name.replace(EM_DASH, "-").replace(EN_DASH, "-")
    # Strip characters Obsidian wikilinks don't handle well
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_skill(raw: str) -> str:
    """Normalize a skill string from a JD into a canonical short name."""
    s = raw.strip()
    # Remove parenthetical qualifiers: "SQL (advanced)" → "SQL"
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s).strip()
    # Remove leading bullets / numbering
    s = re.sub(r"^[-*]\s*", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # Common normalizations
    lower = s.lower()
    if lower in ("dbt", "dbt core", "dbt cloud", "dbt (core or cloud)", "dbt (core & cloud)"):
        return "dbt"
    if lower.startswith("sql"):
        return "SQL"
    if lower in ("gcp", "google cloud", "google cloud platform"):
        return "GCP"
    if lower in ("aws", "amazon web services"):
        return "AWS"
    if lower in ("azure", "microsoft azure"):
        return "Azure"
    if lower.startswith("python"):
        return "Python"
    if lower.startswith("apache airflow") or lower == "airflow":
        return "Apache Airflow"
    if lower.startswith("apache kafka") or lower == "kafka":
        return "Apache Kafka"
    if lower == "docker" or "containerization" in lower:
        return "Docker"
    if lower == "kubernetes" or lower.startswith("kubernetes"):
        return "Kubernetes"
    if lower == "terraform" or lower.startswith("terraform"):
        return "Terraform"
    if lower.startswith("snowflake"):
        return "Snowflake"
    if lower.startswith("bigquery") or lower.startswith("google bigquery"):
        return "BigQuery"
    if lower.startswith("databricks"):
        return "Databricks"
    if lower.startswith("power bi"):
        return "Power BI"
    if lower.startswith("looker") and "studio" not in lower:
        return "Looker"
    if lower.startswith("looker studio"):
        return "Looker Studio"
    if lower.startswith("tableau"):
        return "Tableau"
    if lower in ("ci/cd", "ci / cd", "continuous integration"):
        return "CI/CD"
    if lower.startswith("rest api") or lower == "apis" or lower == "api":
        return "REST APIs"
    if lower.startswith("fastapi"):
        return "FastAPI"
    if lower.startswith("flask"):
        return "Flask"
    if lower.startswith("redis"):
        return "Redis"
    if lower.startswith("dagster"):
        return "Dagster"
    if lower.startswith("airbyte"):
        return "Airbyte"
    if lower.startswith("postgresql") or lower.startswith("postgres"):
        return "PostgreSQL"
    if lower.startswith("pyspark"):
        return "PySpark"
    if lower.startswith("jinja"):
        return "Jinja"
    if lower.startswith("pytest"):
        return "Pytest"
    if lower.startswith("soda core") or lower == "soda":
        return "Soda Core"
    if lower.startswith("github actions"):
        return "GitHub Actions"
    if lower == "git" or lower.startswith("git "):
        return "Git"
    if lower.startswith("apache spark") or lower == "spark":
        return "Apache Spark"
    if lower.startswith("microsoft excel") or lower == "excel":
        return "Microsoft Excel"
    if lower == "linux" or lower.startswith("linux"):
        return "Linux"
    if lower.startswith("fastapi"):
        return "FastAPI"
    if lower.startswith("langchain"):
        return "LangChain"
    if lower.startswith("langgraph"):
        return "LangGraph"
    if lower.startswith("rag") and lower in ("rag", "rag frameworks"):
        return "RAG"
    if lower.startswith("ollama"):
        return "Ollama"
    if lower.startswith("faiss"):
        return "FAISS"
    if lower.startswith("llm") or lower == "llms":
        return "LLMs"
    if lower.startswith("openai"):
        return "OpenAI API"
    if lower.startswith("huggingface") or lower.startswith("hugging face"):
        return "HuggingFace"
    if lower.startswith("prompt engineering"):
        return "Prompt Engineering"
    if lower.startswith("generative ai") or lower == "genai":
        return "Generative AI"
    if lower.startswith("agentic ai") or lower.startswith("ai agents"):
        return "Agentic AI"
    if lower.startswith("machine learning") or lower == "ml":
        return "Machine Learning"
    if lower.startswith("deep learning"):
        return "Deep Learning"
    if lower.startswith("nlp") or lower.startswith("natural language"):
        return "NLP"
    if lower.startswith("computer vision"):
        return "Computer Vision"
    if lower.startswith("tensorflow"):
        return "TensorFlow"
    if lower.startswith("pytorch"):
        return "PyTorch"
    if lower.startswith("scikit-learn") or lower.startswith("sklearn"):
        return "scikit-learn"
    if lower.startswith("pandas"):
        return "Pandas"
    if lower.startswith("numpy"):
        return "NumPy"
    if lower.startswith("streamlit"):
        return "Streamlit"
    if lower.startswith("flask"):
        return "Flask"
    if lower.startswith("elasticsearch"):
        return "Elasticsearch"
    if lower.startswith("mongodb"):
        return "MongoDB"
    if lower.startswith("mysql"):
        return "MySQL"
    if lower.startswith("oracle"):
        return "Oracle"
    if lower.startswith("sap"):
        return "SAP"
    if lower.startswith("tableau"):
        return "Tableau"
    if lower.startswith("power bi"):
        return "Power BI"
    if lower.startswith("looker") and "studio" not in lower:
        return "Looker"
    if lower.startswith("looker studio"):
        return "Looker Studio"
    if lower.startswith("amplitude"):
        return "Amplitude"
    if lower.startswith("hubspot"):
        return "HubSpot"
    if lower.startswith("salesforce"):
        return "Salesforce"
    if lower.startswith("dbt"):
        return "dbt"
    if lower.startswith("dimensional mod"):
        return "Dimensional Modeling"
    if lower.startswith("data vault"):
        return "Data Vault"
    if lower.startswith("scd type 2") or lower == "scd type 2":
        return "SCD Type 2"
    if lower.startswith("incremental mod"):
        return "Incremental Modeling"
    if lower.startswith("medallion arch"):
        return "Medallion Architecture"
    if lower.startswith("data governance"):
        return "Data Governance"
    if lower.startswith("data lineage"):
        return "Data Lineage"
    if lower.startswith("observability"):
        return "Observability"
    if lower.startswith("microservices"):
        return "Microservices"
    if lower.startswith("event-driven"):
        return "Event-Driven Architecture"
    if lower.startswith("data modeling"):
        return "Data Modeling"
    if lower.startswith("schema design"):
        return "Schema Design"
    if lower.startswith("performance optimization") or lower.startswith("performance optimisation"):
        return "Performance Optimization"
    if lower.startswith("delta lake"):
        return "Delta Lake"
    if lower.startswith("apache superset") or lower == "superset":
        return "Apache Superset"
    if lower.startswith("semantic layer"):
        return "Semantic Layer"
    if lower.startswith("semantic model"):
        return "Semantic Models"
    if lower.startswith("kpi"):
        return "KPI Definitions"
    if lower.startswith("data products"):
        return "Data Products"
    if lower.startswith("data catalogue") or lower.startswith("data catalog") or lower.startswith("model catalog"):
        return "Data Catalogue"
    if lower.startswith("rbac"):
        return "RBAC"
    if lower.startswith("amplitude"):
        return "Amplitude"
    if lower.startswith("hubspot"):
        return "HubSpot"
    if lower.startswith("elt") or lower.startswith("etl"):
        return "ELT/ETL"
    if lower.startswith("dax"):
        return "DAX"
    if lower.startswith("monitoring"):
        return "Monitoring"
    if lower.startswith("unit testing"):
        return "Unit Testing"
    if lower.startswith("integration testing"):
        return "Integration Testing"
    if lower.startswith("data quality"):
        return "Data Quality"
    if lower.startswith("real-time") or lower.startswith("real time"):
        return "Real-Time Processing"
    if lower.startswith("marketing attribution"):
        return "Marketing Attribution"
    if lower.startswith("product usage") or lower.startswith("product analytics"):
        return "Product Analytics"
    if lower.startswith("customer care"):
        return "Customer Care Data"
    if lower.startswith("subscription data"):
        return "Subscription Data"
    if lower.startswith("iac") or lower.startswith("infrastructure as code"):
        return "Infrastructure as Code"
    # Title-case fallback for anything else
    return s.title() if s.islower() else s


def normalize_project(raw: str) -> str:
    """Normalize a project name from portfolio/resume into a canonical form.

    Maps the many LLM-generated name variants to canonical project names using
    keyword matching. Returns empty string for junk entries that aren't projects.
    """
    p = raw.strip()
    # Remove surrounding quotes
    p = p.strip('"').strip("'")
    # Remove trailing tools annotation if present
    p = re.sub(r"\s*[—–-]\s*Tools?:.*$", "", p)
    p = re.sub(r"\s*\*Tools?:.*$", "", p)
    # Remove trailing periods
    p = p.rstrip(".")
    # Collapse whitespace
    p = re.sub(r"\s+", " ", p).strip()
    # Remove emoji prefixes (any non-ASCII char at start)
    p = re.sub(r"^[\U0001f000-\U0001ffff\u2600-\u27bf]+\s*", "", p)

    # Junk entries — return empty string so caller can skip
    lower = p.lower()
    junk_patterns = [
        "install packages", "install requirements", "create environment",
        "transform and compile models", "run data quality tests",
        "generated by:", "query:", "install", "create ",
    ]
    for jp in junk_patterns:
        if lower.startswith(jp):
            return ""

    # Canonical project mapping via keyword matching
    # Order matters — more specific patterns first
    canonical = [
        # (keywords that must ALL be present, canonical name)
        (["f1", "ingestion"], "F1 Ingestion Formula 1 ELT Platform"),
        (["f1", "azure"], "F1 Ingestion Formula 1 ELT Platform"),
        (["formula", "ingestion"], "F1 Ingestion Formula 1 ELT Platform"),
        (["ergast", "medallion"], "Ergast Formula 1 Databricks Medallion Architecture"),
        (["ergast", "databricks"], "Ergast Formula 1 Databricks Medallion Architecture"),
        (["formula", "databricks"], "Ergast Formula 1 Databricks Medallion Architecture"),
        (["formula", "medallion"], "Ergast Formula 1 Databricks Medallion Architecture"),
        (["formula one", "processing"], "Ergast Formula 1 Databricks Medallion Architecture"),
        (["nyc", "taxi"], "NYC Taxi Analytics Pipeline"),
        (["nyc taxi"], "NYC Taxi Analytics Pipeline"),
        (["cloud", "data", "analytics", "pipeline", "nyc"], "NYC Taxi Analytics Pipeline"),
        (["cloud", "data", "pipeline", "nyc"], "NYC Taxi Analytics Pipeline"),
        (["cloud", "analytics", "pipeline", "nyc"], "NYC Taxi Analytics Pipeline"),
        (["cloud", "data", "analytics", "nyc"], "NYC Taxi Analytics Pipeline"),
        (["yaml-cv", "resume"], "YAML-CV Resume Cover Letter Tailoring Pipeline"),
        (["yaml", "cv", "tailoring"], "YAML-CV Resume Cover Letter Tailoring Pipeline"),
        (["yaml-cv", "tailoring"], "YAML-CV Resume Cover Letter Tailoring Pipeline"),
        (["resume", "cover", "letter", "tailoring"], "YAML-CV Resume Cover Letter Tailoring Pipeline"),
        (["resume", "cover", "letter", "pipeline"], "YAML-CV Resume Cover Letter Tailoring Pipeline"),
        (["ats", "resume", "pipeline"], "ATS Resume Pipeline Streamlit App"),
        (["ats", "streamlit"], "ATS Resume Pipeline Streamlit App"),
        (["ai", "resume", "pipeline"], "ATS Resume Pipeline Streamlit App"),
        (["resume", "pipeline", "streamlit"], "ATS Resume Pipeline Streamlit App"),
        (["star schema", "sales"], "Star Schema for Enterprise Sales Analytics"),
        (["star schema", "enterprise"], "Star Schema for Enterprise Sales Analytics"),
        (["power bi", "enterprise", "sales"], "Star Schema for Enterprise Sales Analytics"),
        (["power bi", "sales", "analytics"], "Star Schema for Enterprise Sales Analytics"),
        (["rag", "pdf"], "RAG-Based PDF Query Assistant"),
        (["rag", "query"], "RAG-Based PDF Query Assistant"),
        (["retrieval", "augmented", "generation"], "RAG-Based PDF Query Assistant"),
        (["pdf", "query", "system"], "RAG-Based PDF Query Assistant"),
        (["pdf", "query", "assistant"], "RAG-Based PDF Query Assistant"),
        (["subspace", "poisoning"], "Master Thesis Subspace Poisoning"),
        (["master", "thesis"], "Master Thesis Subspace Poisoning"),
        (["masterarbeit"], "Master Thesis Subspace Poisoning"),
        (["bitcoin", "analytics"], "Bitcoin Analytics Engineering Pipeline"),
        (["bitcoin", "dbt"], "Bitcoin Analytics Engineering Pipeline"),
        (["bitcoin", "data", "transformation"], "Bitcoin Analytics Engineering Pipeline"),
        (["bitcoin", "transformation"], "Bitcoin Analytics Engineering Pipeline"),
        (["airbnb", "analytics"], "Airbnb Analytics Engineering Pipeline"),
        (["airbnb", "modern", "data"], "Airbnb Analytics Engineering Pipeline"),
        (["airbnb", "data", "engineering"], "Airbnb Analytics Engineering Pipeline"),
        (["airbnb", "modern", "data", "stack"], "Airbnb Analytics Engineering Pipeline"),
        (["adventure", "works"], "Adventure Works Global Sales Returns Dashboard"),
        (["weather", "data", "analytics"], "Weather Data Analytics Pipeline"),
        (["weather", "data", "pipeline"], "Weather Data Analytics Pipeline"),
        (["weather", "analytics"], "Weather Data Analytics Pipeline"),
        (["youtube", "analytics"], "YouTube End-To-End Analytics Data Pipeline"),
        (["youtube", "e2e"], "YouTube End-To-End Analytics Data Pipeline"),
        (["youtube", "data", "pipeline"], "YouTube End-To-End Analytics Data Pipeline"),
        (["youtube", "end-to-end"], "YouTube End-To-End Analytics Data Pipeline"),
        (["youtube", "end", "end"], "YouTube End-To-End Analytics Data Pipeline"),
        (["youtube", "pipeline"], "YouTube End-To-End Analytics Data Pipeline"),
        (["sql", "practice"], "SQL Practice and Revision"),
        (["sql", "revision"], "SQL Practice and Revision"),
        (["bike", "rentals"], "Bike Rentals Data Transformation Pipeline"),
        (["bike", "rental"], "Bike Rentals Data Transformation Pipeline"),
        (["kafka", "fx"], "Kafka FX Rates Stream Processing"),
        (["fx", "rates"], "Kafka FX Rates Stream Processing"),
    ]

    for keywords, canonical_name in canonical:
        if all(kw in lower for kw in keywords):
            return canonical_name

    # If no match, return the cleaned-up original
    return p


# ─── YAML-format parsers ──────────────────────────────────────────────────────

def parse_ats_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    result = {
        "company": data.get("company", ""),
        "position": data.get("position", ""),
        "pre_total": None,
        "post_total": None,
        "score_gate": None,
        "detractors": [],
        "skills_to_add": [],
        "skills_to_remove": [],
    }
    matrix = data.get("ats_score_matrix", {})
    if isinstance(matrix, dict):
        total = matrix.get("total_score")
        if total is not None:
            result["pre_total"] = int(total)
    post = data.get("post_rewrite_ats_score", {})
    if isinstance(post, dict):
        pmatrix = post.get("ats_score_matrix", {})
        if isinstance(pmatrix, dict):
            ptotal = pmatrix.get("total_score")
            if ptotal is not None:
                result["post_total"] = int(ptotal)
    detractors = data.get("core_score_detractors", [])
    if isinstance(detractors, list):
        result["detractors"] = [str(d) for d in detractors]
    blueprint = data.get("improvement_blueprint", {})
    if isinstance(blueprint, dict):
        gate = blueprint.get("ats_threshold_calibration", {})
        if isinstance(gate, dict):
            verdict = gate.get("score_gate_verdict")
            if verdict:
                result["score_gate"] = str(verdict)
        tuning = blueprint.get("technical_skills_tuning", {})
        if isinstance(tuning, dict):
            add = tuning.get("add", [])
            if isinstance(add, list):
                result["skills_to_add"] = [str(s) for s in add]
            rem = tuning.get("remove", [])
            if isinstance(rem, list):
                result["skills_to_remove"] = [str(s) for s in rem]
    return result


def parse_jd_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    result = {
        "company": data.get("company", ""),
        "position": data.get("position", ""),
        "skills": [],
        "location": data.get("location", ""),
    }
    sections = data.get("sections", [])
    if isinstance(sections, list):
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = (sec.get("title") or "").lower()
            # Only extract skills from tech stack / tooling sections
            # Requirement bullets are full sentences, not skill names
            if "tech stack" in title or "tooling" in title or "technology" in title:
                bullets = sec.get("bullets", [])
                if isinstance(bullets, list):
                    result["skills"].extend(str(b) for b in bullets)
    return result


def parse_resume_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    projects = []
    for p in data.get("projects", []):
        if isinstance(p, dict):
            projects.append(p.get("name", ""))
    return {"projects": [np for np in (normalize_project(p) for p in projects if p) if np]}


# ─── MD-format parsers ─────────────────────────────────────────────────────────

def parse_ats_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    result = {
        "company": "",
        "position": "",
        "pre_total": None,
        "post_total": None,
        "score_gate": None,
        "detractors": [],
        "skills_to_add": [],
        "skills_to_remove": [],
    }

    # Title: "# ATS Analysis Report: Company — Role"
    title_match = re.search(r"^#\s+.*?:\s*(.+)$", text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        parts = re.split(r"[—–-]", title, maxsplit=1)
        if len(parts) == 2:
            result["company"] = parts[0].strip()
            result["position"] = parts[1].strip()

    # Scoring table — find all table rows with scores
    # Pattern: | **Category** | **max** | criteria | **score** |
    # Bold markers may or may not be present around numbers
    score_rows = re.findall(
        r"\|\s*\*{0,2}([^|*]+)\*{0,2}\s*\|\s*\*{0,2}:?[0-9]+\*{0,2}\s*\|[^|]*\|\s*\*{0,2}([0-9]+)\*{0,2}\s*\|",
        text,
    )
    if score_rows:
        total_row = [r for r in score_rows if "total" in r[0].lower()]
        if total_row:
            result["pre_total"] = int(total_row[0][1])

    # Post-rewrite score — look for a second scoring table or "Post-Rewrite" section
    post_section = re.search(r"post.?rewrite.*?(?:TOTAL|total).*?(\d+)\s*/?\s*100", text, re.IGNORECASE | re.DOTALL)
    if post_section:
        result["post_total"] = int(post_section.group(1))
    else:
        # Try: "Post-Rewrite ATS Score: XX" or "Post-rewrite: XX"
        m = re.search(r"post.?rewrite.*?(\d{2,3})", text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val <= 100:
                result["post_total"] = val

    # Score gate verdict
    gate_match = re.search(r"(PROCEED|HOLD)", text, re.IGNORECASE)
    if gate_match:
        result["score_gate"] = gate_match.group(1).upper()
    elif re.search(r"meets_target:\s*true", text, re.IGNORECASE):
        result["score_gate"] = "PROCEED"
    elif re.search(r"meets_target:\s*false", text, re.IGNORECASE):
        result["score_gate"] = "HOLD"

    # Core detractors — bullet list under "## 3. Core Score Detractors" or similar
    detractor_section = re.search(
        r"##\s*\d*\.?\s*Core Score Detractors\s*\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL,
    )
    if detractor_section:
        bullets = re.findall(r"^[-*]\s+(.+)$", detractor_section.group(1), re.MULTILINE)
        # Clean bold markers
        result["detractors"] = [re.sub(r"\*\*([^*]+)\*\*:?\s*", r"\1: ", b).strip() for b in bullets]

    # Skills to add / remove from "Technical Skills Tuning" section
    tuning_section = re.search(
        r"Skills to Add:?\s*\n(.*?)(?:\*\*Skills to Remove|\n##|\Z)",
        text,
        re.DOTALL,
    )
    if tuning_section:
        bullets = re.findall(r"^[-*]\s+(.+)$", tuning_section.group(1), re.MULTILINE)
        result["skills_to_add"] = [b.strip().strip("*") for b in bullets]

    remove_section = re.search(
        r"Skills to Remove:?\s*\n(.*?)(?:\*\*Skills to Reframe|\n##|\Z)",
        text,
        re.DOTALL,
    )
    if remove_section:
        bullets = re.findall(r"^[-*]\s+(.+)$", remove_section.group(1), re.MULTILINE)
        result["skills_to_remove"] = [b.strip().strip("*") for b in bullets]

    return result


def parse_jd_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    result = {"company": "", "position": "", "skills": [], "location": ""}

    # Title: "# Company — Role"
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        parts = re.split(r"[—–-]", title, maxsplit=1)
        if len(parts) == 2:
            result["company"] = parts[0].strip()
            result["position"] = parts[1].strip()

    # Tech stack section — this is the primary source of skill names
    tech_section = re.search(
        r"##\s*.*?(?:Tech Stack|Tooling|Technology).*?\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if tech_section:
        block = tech_section.group(1)
        bullets = re.findall(r"^[-*]\s+(.+)$", block, re.MULTILINE)
        for b in bullets:
            # Strip bold markers: "**Languages:** Python, SQL" → "Languages: Python, SQL"
            b_clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", b).strip()
            # "Languages: Python, SQL" → split on colon, then commas
            if ":" in b_clean:
                parts = b_clean.split(":", 1)
                items = [i.strip() for i in parts[1].split(",")]
                result["skills"].extend(items)
            else:
                # Single-item bullet — may still be comma-separated
                items = [i.strip() for i in b_clean.split(",")]
                result["skills"].extend(items)

    return result


def parse_resume_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    projects = []
    # Projects are bold lines between **PROJECTS** and **PROFESSIONAL EXPERIENCE**
    proj_section = re.search(
        r"\*\*PROJECTS\*\*\s*\n(.*?)(?:\*\*PROFESSIONAL EXPERIENCE\*\*|\Z)",
        text,
        re.DOTALL,
    )
    if proj_section:
        # Project names are bold: **Project Name** *Tools: ...*
        names = re.findall(r"^\*\*(.+?)\*\*", proj_section.group(1), re.MULTILINE)
        projects = [np for np in (normalize_project(n) for n in names) if np]
    return {"projects": projects}


def parse_project_info_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # Project names are H1 headers: "# Project Name"
    names = re.findall(r"^#\s+(.+)$", text, re.MULTILINE)
    # Skip the first "# Tailored Project Portfolio" header
    projects = []
    for n in names:
        n = n.strip()
        if "tailored project portfolio" in n.lower():
            continue
        np = normalize_project(n)
        if np:
            projects.append(np)
    return {"projects": projects}


# ─── Application folder walker ────────────────────────────────────────────────

def find_application_folders(root: Path) -> list:
    """Find all application folders matching YYYY/MM/DD/[Company] — [Role]/."""
    apps = []
    if not root.exists():
        return apps
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue
                for app_dir in sorted(day_dir.iterdir()):
                    if not app_dir.is_dir():
                        continue
                    apps.append(app_dir)
    return apps


def parse_application(app_dir: Path) -> Optional[dict]:
    """Parse a single application folder, handling both YAML and MD formats."""
    # Determine format
    ats_yaml = app_dir / "ATS_Report.yaml"
    ats_md = app_dir / "ATS_Report.md"
    jd_yaml = app_dir / "Job_Description.yaml"
    jd_md = app_dir / "Job_Description.md"
    resume_yaml = app_dir / "Resume.yaml"
    resume_md = app_dir / "Resume.md"
    project_info = app_dir / "project_info.md"

    # Parse ATS report
    if ats_yaml.exists():
        ats = parse_ats_yaml(ats_yaml)
    elif ats_md.exists():
        ats = parse_ats_md(ats_md)
    else:
        return None  # Not a valid application folder

    # Parse JD
    if jd_yaml.exists():
        jd = parse_jd_yaml(jd_yaml)
    elif jd_md.exists():
        jd = parse_jd_md(jd_md)
    else:
        jd = {"company": "", "position": "", "skills": []}

    # Parse projects
    projects = []
    if project_info.exists():
        projects = parse_project_info_md(project_info)["projects"]
    elif resume_yaml.exists():
        projects = parse_resume_yaml(resume_yaml)["projects"]
    elif resume_md.exists():
        projects = parse_resume_md(resume_md)["projects"]

    # Extract date from path
    parts = app_dir.parts
    # .../Applications/YYYY/MM/DD/[Company]/
    date_str = ""
    try:
        # Find the Applications part and take next 3 segments
        idx = parts.index("Applications")
        year = parts[idx + 1]
        month = parts[idx + 2]
        day = parts[idx + 3]
        date_str = f"{year}-{month}-{day}"
    except (ValueError, IndexError):
        pass

    # Extract company and role from folder name as fallback
    folder_name = app_dir.name
    folder_parts = re.split(r"[—–]", folder_name, maxsplit=1)
    if len(folder_parts) == 2:
        folder_company = folder_parts[0].strip()
        folder_role = folder_parts[1].strip()
    else:
        folder_company = folder_name
        folder_role = ""

    company = ats.get("company") or jd.get("company") or folder_company
    position = ats.get("position") or jd.get("position") or folder_role

    # Normalize skills
    raw_skills = jd.get("skills", [])
    skills = []
    seen = set()
    for s in raw_skills:
        norm = normalize_skill(s)
        if norm and norm.lower() not in seen and len(norm) > 1:
            seen.add(norm.lower())
            skills.append(norm)

    return {
        "folder": app_dir,
        "company": company.strip(),
        "position": position.strip(),
        "date": date_str,
        "pre_total": ats.get("pre_total"),
        "post_total": ats.get("post_total"),
        "score_gate": ats.get("score_gate"),
        "detractors": ats.get("detractors", []),
        "skills_to_add": ats.get("skills_to_add", []),
        "skills_to_remove": ats.get("skills_to_remove", []),
        "skills": skills,
        "projects": projects,
    }


# ─── Obsidian note generators ─────────────────────────────────────────────────

def app_note_name(app: dict) -> str:
    """Filename for an application note."""
    return slugify(f"{app['company']} — {app['position']} ({app['date']})")


def generate_application_note(app: dict) -> str:
    lines = []
    lines.append(f"# {app['company']} — {app['position']} ({app['date']})")
    lines.append("")
    lines.append(f"**Date:** {app['date']}")
    lines.append(f"**Company:** [[{app['company']}]]")
    lines.append(f"**Role:** [[{app['position']}]]")
    if app["pre_total"] is not None:
        lines.append(f"**ATS Pre-rewrite:** {app['pre_total']}/100")
    if app["post_total"] is not None:
        lines.append(f"**ATS Post-rewrite:** {app['post_total']}/100")
    if app["score_gate"]:
        lines.append(f"**Score Gate:** {app['score_gate']}")
    lines.append("")

    if app["skills"]:
        lines.append("## Skills Required")
        for s in app["skills"]:
            lines.append(f"- [[{s}]]")
        lines.append("")

    if app["projects"]:
        lines.append("## Projects Used")
        for p in app["projects"]:
            lines.append(f"- [[{p}]]")
        lines.append("")

    if app["detractors"]:
        lines.append("## Core Detractors")
        for d in app["detractors"]:
            lines.append(f"- {d}")
        lines.append("")

    if app["skills_to_add"]:
        lines.append("## Skills to Add")
        for s in app["skills_to_add"]:
            lines.append(f"- {s}")
        lines.append("")

    if app["skills_to_remove"]:
        lines.append("## Skills to Remove")
        for s in app["skills_to_remove"]:
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)


def generate_entity_note(title: str, backlinks_key: str, backlinks: list, extra_sections: dict = None) -> str:
    lines = [f"# {title}", ""]
    if backlinks:
        lines.append(f"## {backlinks_key}")
        for b in sorted(backlinks):
            lines.append(f"- [[{b}]]")
        lines.append("")
    if extra_sections:
        for heading, items in extra_sections.items():
            if items:
                lines.append(f"## {heading}")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")
    return "\n".join(lines)


def generate_index_note(title: str, entries: list) -> str:
    lines = [f"# {title}", ""]
    for e in sorted(entries):
        lines.append(f"- [[{e}]]")
    lines.append("")
    return "\n".join(lines)


# ─── Main sync logic ──────────────────────────────────────────────────────────

def sync(dry_run: bool = False, verbose: bool = False) -> None:
    app_folders = find_application_folders(APPLICATIONS_DIR)
    if verbose:
        print(f"Found {len(app_folders)} application folders")

    applications = []
    for folder in app_folders:
        app = parse_application(folder)
        if app:
            applications.append(app)
            if verbose:
                print(f"  Parsed: {app['company']} — {app['position']} ({app['date']}) "
                      f"pre={app['pre_total']} post={app['post_total']} "
                      f"skills={len(app['skills'])} projects={len(app['projects'])}")
        elif verbose:
            print(f"  Skipped (no ATS report): {folder.name}")

    if not applications:
        print("No valid applications found.")
        return

    # Build aggregation maps
    company_apps = defaultdict(list)   # company → [app_note_name]
    role_apps = defaultdict(list)      # role → [app_note_name]
    skill_apps = defaultdict(list)     # skill → [app_note_name]
    project_apps = defaultdict(list)   # project → [app_note_name]

    for app in applications:
        note_name = app_note_name(app)
        company_apps[app["company"]].append(note_name)
        role_apps[app["position"]].append(note_name)
        for s in app["skills"]:
            skill_apps[s].append(note_name)
        for p in app["projects"]:
            project_apps[p].append(note_name)

    # Prepare output directories
    dirs = {
        "applications": OUTPUT_ROOT / "Applications",
        "companies": OUTPUT_ROOT / "Companies",
        "roles": OUTPUT_ROOT / "Roles",
        "skills": OUTPUT_ROOT / "Skills",
        "projects": OUTPUT_ROOT / "Projects",
    }

    if dry_run:
        print("\n=== DRY RUN ===")
        print(f"Would write {len(applications)} application notes")
        print(f"Would write {len(company_apps)} company notes")
        print(f"Would write {len(role_apps)} role notes")
        print(f"Would write {len(skill_apps)} skill notes")
        print(f"Would write {len(project_apps)} project notes")
        print(f"Output root: {OUTPUT_ROOT}")
        print("\nSample application note:")
        print("---")
        print(generate_application_note(applications[-1]))
        return

    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    written = 0

    # Write application notes
    for app in applications:
        note_path = dirs["applications"] / f"{app_note_name(app)}.md"
        note_path.write_text(generate_application_note(app), encoding="utf-8")
        written += 1

    # Write company notes
    for company, apps in sorted(company_apps.items()):
        note_path = dirs["companies"] / f"{slugify(company)}.md"
        note_path.write_text(
            generate_entity_note(company, "Applications", apps),
            encoding="utf-8",
        )
        written += 1

    # Write role notes
    for role, apps in sorted(role_apps.items()):
        note_path = dirs["roles"] / f"{slugify(role)}.md"
        note_path.write_text(
            generate_entity_note(role, "Applications", apps),
            encoding="utf-8",
        )
        written += 1

    # Write skill notes
    for skill, apps in sorted(skill_apps.items()):
        note_path = dirs["skills"] / f"{slugify(skill)}.md"
        note_path.write_text(
            generate_entity_note(skill, "Required By", apps),
            encoding="utf-8",
        )
        written += 1

    # Write project notes
    for project, apps in sorted(project_apps.items()):
        note_path = dirs["projects"] / f"{slugify(project)}.md"
        note_path.write_text(
            generate_entity_note(project, "Used In", apps),
            encoding="utf-8",
        )
        written += 1

    # Write index notes
    indexes = {
        "Applications Index.md": [app_note_name(a) for a in applications],
        "Companies Index.md": list(company_apps.keys()),
        "Roles Index.md": list(role_apps.keys()),
        "Skills Index.md": list(skill_apps.keys()),
        "Projects Index.md": list(project_apps.keys()),
    }
    for filename, entries in indexes.items():
        note_path = OUTPUT_ROOT / filename
        note_path.write_text(generate_index_note(filename.replace(".md", ""), entries), encoding="utf-8")
        written += 1

    print(f"Sync complete: {written} notes written to {OUTPUT_ROOT}")
    print(f"  {len(applications)} applications")
    print(f"  {len(company_apps)} companies")
    print(f"  {len(role_apps)} roles")
    print(f"  {len(skill_apps)} skills")
    print(f"  {len(project_apps)} projects")
    print(f"  5 index notes")
    print(f"\nOpen Obsidian -> Job Search -> graph view to see the mind map.")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync YAML-CV applications to Obsidian vault")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written without writing files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-application progress")
    args = parser.parse_args()
    sync(dry_run=args.dry_run, verbose=args.verbose)
