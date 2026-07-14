"""
config.py — Centralized configuration for OKF-CV Pipeline.

Provides default paths and constants with environment variable override support.
"""
import os


# Base paths (override with environment variables if needed)
# Calculate paths relative to skill directory for portability
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SKILL_DIR))  # Go up to YAML-CV directory

DEFAULT_PORTFOLIO_DIR = os.getenv(
    "YAML_CV_PORTFOLIO_DIR",
    os.path.join(SKILL_DIR, "okf", "portfolio")
)
DEFAULT_BASE_FILES_DIR = os.getenv(
    "YAML_CV_BASE_FILES_DIR",
    os.path.join(SKILL_DIR, "okf", "base_files")
)
DEFAULT_PHOTO_DIR = os.getenv(
    "YAML_CV_PHOTO_DIR",
    os.path.join(SKILL_DIR, "okf", "photo")
)

# Zvec hybrid search configuration
ZVEC_DB_PATH = os.getenv(
    "YAML_CV_ZVEC_DB_PATH",
    os.path.join(SKILL_DIR, "okf", "zvec_db")
)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
HYBRID_OKF_WEIGHT = 0.6
HYBRID_ZVEC_WEIGHT = 0.4

# Applications directory (where the pipeline saves application folders)
APPLICATIONS_DIR = os.getenv(
    "YAML_CV_APPLICATIONS_DIR",
    os.path.join(PROJECT_ROOT, "Applications")
)

# Diversity audit thresholds
DIVERSITY_VENDOR_CLUSTER_THRESHOLD = int(os.getenv("YAML_CV_DIVERSITY_VENDOR_THRESHOLD", "3"))
DIVERSITY_REFERRAL_RATE_MIN = float(os.getenv("YAML_CV_DIVERSITY_REFERRAL_MIN", "0.20"))
DIVERSITY_LOOKBACK_DAYS = int(os.getenv("YAML_CV_DIVERSITY_LOOKBACK_DAYS", "14"))


# ─── Candidate city geocode table ─────────────────────────────────────────────
# The candidate's 4 home cities with approximate coordinates (lat, lon).
# Used by nearest_candidate_city() to avoid a web search per application.
CANDIDATE_CITIES = {
    "Kiel":      (54.32, 10.13),
    "Frankfurt": (50.11,  8.68),
    "Berlin":    (52.52, 13.40),
    "Köln":      (50.94,  6.96),
}

# Static mapping of common German job locations to their nearest candidate city.
# Falls back to web search for locations not in this table (see
# 01_ats_and_jd_archival.md section 5). To add new locations, append to this dict.
JOB_LOCATION_TO_CANDIDATE_CITY = {
    # Munich area -> Frankfurt (nearest of the 4)
    "Munich": "Frankfurt, Germany",
    "München": "Frankfurt, Germany",
    "Stuttgart": "Frankfurt, Germany",
    # Frankfurt area
    "Frankfurt": "Frankfurt, Germany",
    "Frankfurt am Main": "Frankfurt, Germany",
    "Wiesbaden": "Frankfurt, Germany",
    "Mainz": "Frankfurt, Germany",
    "Darmstadt": "Frankfurt, Germany",
    # Cologne area -> Köln
    "Köln": "Köln, Germany",
    "Cologne": "Köln, Germany",
    "Koln": "Köln, Germany",
    "Düsseldorf": "Köln, Germany",
    "Duesseldorf": "Köln, Germany",
    "Bonn": "Köln, Germany",
    "Aachen": "Köln, Germany",
    "Dortmund": "Köln, Germany",
    "Essen": "Köln, Germany",
    "Duisburg": "Köln, Germany",
    # Berlin area
    "Berlin": "Berlin, Germany",
    "Potsdam": "Berlin, Germany",
    # Hamburg area -> Kiel
    "Hamburg": "Kiel, Germany",
    # Kiel area
    "Kiel": "Kiel, Germany",
    "Lübeck": "Kiel, Germany",
    "Luebeck": "Kiel, Germany",
    "Flensburg": "Kiel, Germany",
    # Remote / unspecified -> default to Kiel
    "Remote": "Kiel, Germany",
    "Home Office": "Kiel, Germany",
    "Home-Office": "Kiel, Germany",
    "Deutschland": "Kiel, Germany",
    "Germany": "Kiel, Germany",
    "Nationwide": "Kiel, Germany",
}


def nearest_candidate_city(job_location: str) -> str:
    """Look up the nearest candidate city for a job location string.

    Uses the static JOB_LOCATION_TO_CANDIDATE_CITY table. Returns None if the
    location is not found in the table (caller should fall back to web search).
    Normalizes input by stripping whitespace and trying case-insensitive match.
    """
    if not job_location:
        return None
    loc = job_location.strip()
    # Try exact match first
    if loc in JOB_LOCATION_TO_CANDIDATE_CITY:
        return JOB_LOCATION_TO_CANDIDATE_CITY[loc]
    # Try case-insensitive match
    loc_lower = loc.lower()
    for key, value in JOB_LOCATION_TO_CANDIDATE_CITY.items():
        if key.lower() == loc_lower:
            return value
    # Try substring match (e.g., "Munich, Germany" contains "Munich")
    for key, value in JOB_LOCATION_TO_CANDIDATE_CITY.items():
        if key.lower() in loc_lower:
            return value
    return None


