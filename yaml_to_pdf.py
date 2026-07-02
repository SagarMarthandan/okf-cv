"""
yaml_to_pdf.py — YAML CV Pipeline entry point.

Routes an input YAML file to the correct PDF renderer based on the document
type declared in the YAML (or inferred from the filename).

Supported types:
  resume           → renderers/resume.py
  cover_letter     → renderers/cover_letter.py
  job_description  → renderers/job_description.py
  ats_report       → renderers/ats_report.py

Usage:
  python yaml_to_pdf.py <input.yaml> <output.pdf>
"""
import os
import sys
import yaml
from typing import Dict, Any

from renderers.resume          import create_resume_pdf
from renderers.cover_letter    import create_cover_letter_pdf
from renderers.job_description import create_job_description_pdf
from renderers.ats_report      import create_ats_report_pdf

VALID_TYPES = {'resume', 'cover_letter', 'job_description', 'ats_report'}


def _infer_type(filename: str) -> str:
    """Infer document type from filename when the YAML has no 'type' field."""
    name = filename.lower()
    if 'resume' in name:
        return 'resume'
    if 'cover_letter' in name or 'cover' in name:
        return 'cover_letter'
    if 'ats_report' in name or 'ats' in name:
        return 'ats_report'
    if 'job_description' in name or 'job' in name:
        return 'job_description'
    return ''


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python yaml_to_pdf.py <input.yaml> <output.pdf>", file=sys.stderr)
        sys.exit(1)

    yaml_path = sys.argv[1]
    pdf_path  = sys.argv[2]

    if not os.path.exists(yaml_path):
        print(f"Error: Input file '{yaml_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error parsing YAML file '{yaml_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print(f"Error: YAML content must be a dictionary, got {type(data)}.", file=sys.stderr)
        sys.exit(1)

    doc_type = str(data.get('type', '')).lower()

    # Fall back to filename heuristic if type is missing or unrecognised
    if doc_type not in VALID_TYPES:
        doc_type = _infer_type(os.path.basename(yaml_path))

    # Ensure output directory exists
    pdf_dir = os.path.dirname(pdf_path)
    if pdf_dir and not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir, exist_ok=True)

    renderers = {
        'resume':          create_resume_pdf,
        'cover_letter':    create_cover_letter_pdf,
        'job_description': create_job_description_pdf,
        'ats_report':      create_ats_report_pdf,
    }

    if doc_type not in renderers:
        print(
            f"Error: Unknown document type '{doc_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TYPES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    renderers[doc_type](data, pdf_path)


if __name__ == '__main__':
    main()
