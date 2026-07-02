"""
config.py — Centralized configuration for YAML CV Pipeline.

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


