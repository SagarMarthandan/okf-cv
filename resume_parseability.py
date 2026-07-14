"""
resume_parseability.py — ATS parse-integrity audit for compiled resume PDFs.

Reads a resume PDF and its source YAML, extracts the PDF text layer via pypdf,
and checks:
  1. Unicode corruption (replacement glyphs U+FFFD)
  2. Keyword recovery (all tools/skills from the YAML must appear in the text)
  3. Section header detection (all 6 standard sections must be present)
  4. Contact info extraction (name, phone, email, GitHub, LinkedIn)
  5. Text structure stats (lines, avg/max line length)

Outputs:
  - Parseability_Report.yaml  (structured audit results)
  - Parseability_Report.pdf   (human-readable report via the renderer)

Usage:
  python resume_parseability.py <resume.pdf> <resume.yaml> [output_dir]
  python resume_parseability.py --check-tex <resume.tex>

The --check-tex mode runs the LaTeX project paragraph length check only
(<= 300 chars for English, <= 250 chars for German). No PDF audit is performed.

If output_dir is omitted, the directory of the PDF is used.

Exit codes:
  0 = audit passed (all keywords recovered, no corruptions)
  1 = audit failed (corruptions or missing keywords, or tex length check failed)
  2 = error (could not read PDF or YAML)
"""
import os
import sys
import re
import yaml
import datetime

from reportlab.lib.pagesizes import A4


def _extract_pdf_text(pdf_path):
    """Extract the full text layer from a PDF using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        pages = len(reader.pages)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        return text, pages
    except Exception as e:
        print(f"Error extracting PDF text from {pdf_path}: {e}", file=sys.stderr)
        return None, 0


def _check_unicode_corruption(pdf_text):
    """Check for Unicode replacement glyphs (U+FFFD)."""
    corruptions = [i for i, ch in enumerate(pdf_text) if ch == '\uFFFD']
    status = "Pass" if not corruptions else "Fail"
    return {
        "status": status,
        "corruption_count": len(corruptions),
        "positions": corruptions[:50],
    }


def _build_keyword_set(resume_data):
    """Build the set of keywords to check from the resume YAML.

    Only keywords that are actually present in the YAML are checked.
    The audit verifies that every keyword in the YAML source is
    recoverable from the PDF text layer — not that arbitrary external
    keywords are present.
    """
    keywords = set()

    # From project tools
    for proj in resume_data.get('projects', resume_data.get('projekte', [])):
        if isinstance(proj, dict):
            for t in proj.get('tools', []):
                if t and len(str(t)) > 1:
                    keywords.add(str(t).strip())

    # From technical skills
    for cat in resume_data.get('technical_skills',
                               resume_data.get('technische_fähigkeiten',
                                               resume_data.get('technische fähigkeiten', []))):
        if isinstance(cat, dict):
            for s in cat.get('skills', []):
                if s and len(str(s)) > 1:
                    keywords.add(str(s).strip())

    # From summary (extract significant words)
    summary = resume_data.get('summary', resume_data.get('zusammenfassung', ''))
    if isinstance(summary, list):
        summary = ' '.join(summary)
    if summary:
        # Add notable terms from the summary (length > 4 to skip filler words)
        for word in summary.split():
            cleaned = word.strip('.,;:()')
            if len(cleaned) > 4:
                keywords.add(cleaned)

    return keywords


def _check_keyword_recovery(pdf_text, keywords):
    """Check which keywords are recoverable from the PDF text layer.

    Handles line-break splitting: a keyword split across a line break
    (e.g. 'Data Integration\\n& Ingestion') is still considered found
    because ATS parsers normalize whitespace.
    """
    pdf_text_lower = pdf_text.lower()
    # Normalized text (all whitespace collapsed to single spaces)
    normalized = " ".join(pdf_text.split()).lower()

    results = []
    missing = []
    found_count = 0

    for kw in sorted(keywords):
        kw_lower = kw.lower()
        if kw_lower in pdf_text_lower:
            results.append({"keyword": kw, "status": "found", "note": ""})
            found_count += 1
        elif kw_lower in normalized:
            results.append({"keyword": kw, "status": "found", "note": "Recovered after whitespace normalization (split across line break)"})
            found_count += 1
        else:
            # Check if all individual words are present (split across lines)
            words = kw_lower.split()
            all_words_found = all(w in pdf_text_lower for w in words)
            if all_words_found and len(words) > 1:
                results.append({"keyword": kw, "status": "found", "note": "All words present individually (split across lines)"})
                found_count += 1
            else:
                results.append({"keyword": kw, "status": "missing", "note": "Not in resume content"})
                missing.append(kw)

    total = len(keywords)
    recovery_pct = int(found_count / total * 100) if total > 0 else 100

    return {
        "status": "Pass" if not missing else "Fail",
        "keywords_total": total,
        "keywords_recovered": found_count,
        "keywords_missing": missing,
        "recovery_pct": recovery_pct,
        "keyword_results": results,
    }


def _check_section_headers(pdf_text, lang='english'):
    """Check that all expected section headers are present in the text."""
    expected = {
        'english': ['SUMMARY', 'TECHNICAL SKILLS', 'PROJECTS',
                    'PROFESSIONAL EXPERIENCE', 'EDUCATION', 'SPOKEN LANGUAGES'],
        'german': ['ZUSAMMENFASSUNG', 'TECHNISCHE FÄHIGKEITEN', 'PROJEKTE',
                   'BERUFSERFAHRUNG', 'AUSBILDUNG', 'SPRACHEN'],
    }
    sections = expected.get(lang, expected['english'])
    pdf_upper = pdf_text.upper()

    results = []
    found_count = 0
    for sec in sections:
        if sec.upper() in pdf_upper:
            results.append({"section": sec, "status": "found"})
            found_count += 1
        else:
            results.append({"section": sec, "status": "missing"})

    return {
        "status": "Pass" if found_count == len(sections) else "Fail",
        "sections_total": len(sections),
        "sections_found": found_count,
        "section_results": results,
    }


def _check_contact_info(pdf_text, resume_data):
    """Check that contact info fields are extractable from the PDF text."""
    contact = resume_data.get('contact_info', {})
    checks = {
        'Name':     contact.get('name', ''),
        'Phone':    contact.get('phone', ''),
        'Email':    contact.get('email', ''),
        'GitHub':   contact.get('github', ''),
        'LinkedIn': contact.get('linkedin', ''),
    }

    pdf_lower = pdf_text.lower()
    results = []
    found_count = 0

    for field, val in checks.items():
        if not val:
            continue
        if val.lower() in pdf_lower:
            results.append({"field": field, "value": val, "status": "found"})
            found_count += 1
        else:
            # Try partial match (first segment)
            partial = val.split('.')[0] if '.' in val else val.split(' ')[0]
            if partial.lower() in pdf_lower:
                results.append({"field": field, "value": val, "status": "partial"})
                found_count += 1
            else:
                results.append({"field": field, "value": val, "status": "missing"})

    total = len([v for v in checks.values() if v])
    return {
        "status": "Pass" if found_count == total else "Fail",
        "contact_fields_total": total,
        "contact_fields_found": found_count,
        "contact_results": results,
    }


def _text_stats(pdf_text):
    """Compute basic text structure statistics."""
    lines = [l for l in pdf_text.split('\n') if l.strip()]
    avg_len = sum(len(l) for l in lines) / len(lines) if lines else 0
    max_len = max(len(l) for l in lines) if lines else 0
    return {
        "non_empty_lines": len(lines),
        "avg_line_length": round(avg_len, 1),
        "max_line_length": max_len,
    }


def run_audit(pdf_path, yaml_path):
    """Run the full parse-integrity audit.

    Returns a dict with all audit results.
    """
    # Load YAML
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            resume_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML {yaml_path}: {e}", file=sys.stderr)
        return None

    # Extract PDF text
    pdf_text, pages = _extract_pdf_text(pdf_path)
    if pdf_text is None:
        return None

    # Determine language
    lang = 'english'
    lang_val = str(resume_data.get('language', '')).lower()
    if 'german' in lang_val or 'deutsch' in lang_val or lang_val == 'de':
        lang = 'german'

    # Run all checks
    unicode_check = _check_unicode_corruption(pdf_text)
    keywords = _build_keyword_set(resume_data)
    keyword_check = _check_keyword_recovery(pdf_text, keywords)
    section_check = _check_section_headers(pdf_text, lang)
    contact_check = _check_contact_info(pdf_text, resume_data)
    stats = _text_stats(pdf_text)

    # Overall verdict
    issues = []
    if unicode_check["status"] == "Fail":
        issues.append("unicode_corruptions")
    if keyword_check["keywords_missing"]:
        # Distinguish genuine misses from keywords not in the resume
        genuine_missing = [kw for kw in keyword_check["keywords_missing"]
                          if kw.lower() not in " ".join(pdf_text.split()).lower()]
        if genuine_missing:
            issues.append(f"missing_keywords: {genuine_missing}")

    overall_status = "Pass" if not issues else "Fail"

    # Extract company/position from YAML if available
    company = resume_data.get('company', '')
    position = resume_data.get('position', '')

    report = {
        "type": "parseability_report",
        "company": company,
        "position": position,
        "pdf_file": os.path.abspath(pdf_path),
        "yaml_file": os.path.abspath(yaml_path),
        "audit_date": datetime.date.today().isoformat(),
        "pages": pages,
        "total_chars": len(pdf_text),
        "total_words": len(pdf_text.split()),
        "overall_status": overall_status,
        "unicode_status": unicode_check["status"],
        "unicode_corruptions": unicode_check["positions"],
        "keyword_recovery_pct": keyword_check["recovery_pct"],
        "keywords_total": keyword_check["keywords_total"],
        "keywords_recovered": keyword_check["keywords_recovered"],
        "keywords_missing": keyword_check["keywords_missing"],
        "keyword_results": keyword_check["keyword_results"],
        "sections_found": section_check["sections_found"],
        "sections_total": section_check["sections_total"],
        "section_results": section_check["section_results"],
        "contact_fields_found": contact_check["contact_fields_found"],
        "contact_fields_total": contact_check["contact_fields_total"],
        "contact_results": contact_check["contact_results"],
        "text_stats": stats,
        "text_preview": pdf_text[:1500],
    }

    return report


def check_tex(tex_path):
    """Check LaTeX project paragraph lengths against the character limit.

    English resumes: <= 300 chars per project paragraph.
    German resumes (Lebenslauf): <= 250 chars per project paragraph.

    Returns 0 if all pass, 1 if any fail.
    """
    if not os.path.exists(tex_path):
        print(f"Error: TeX file '{tex_path}' not found.", file=sys.stderr)
        return 2

    limit = 250 if 'Lebenslauf' in os.path.basename(tex_path) else 300

    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()

    projects = re.findall(
        r'\\noindent\\textbf\{(.+?)\} --- (.+?)(?=\n\\noindent|\\vspace|\n\n|$)',
        content, re.DOTALL
    )

    if not projects:
        print(f"No project paragraphs found in {tex_path} (regex: \\noindent\\textbf{{...}} --- ...)")
        return 0

    all_ok = True
    print(f"TeX project length check (limit: {limit} chars):")
    for name, desc in projects:
        full = name + ' --- ' + desc.strip()
        status = 'OK' if len(full) <= limit else 'FAIL'
        if status == 'FAIL':
            all_ok = False
        print(f"  {status} | {name}: {len(full)} chars (limit: {limit})")

    if all_ok:
        print("All project paragraphs within limit.")
        return 0
    else:
        print("FAIL: One or more project paragraphs exceed the character limit.", file=sys.stderr)
        return 1


def main():
    args = sys.argv[1:]

    # --check-tex mode: LaTeX project paragraph length check only
    if '--check-tex' in args:
        args.remove('--check-tex')
        if len(args) < 1:
            print("Usage: python resume_parseability.py --check-tex <resume.tex>", file=sys.stderr)
            sys.exit(2)
        sys.exit(check_tex(args[0]))

    if len(args) < 2:
        print("Usage: python resume_parseability.py <resume.pdf> <resume.yaml> [output_dir]", file=sys.stderr)
        print("       python resume_parseability.py --check-tex <resume.tex>", file=sys.stderr)
        sys.exit(2)

    pdf_path = args[0]
    yaml_path = args[1]
    output_dir = args[2] if len(args) > 2 else os.path.dirname(os.path.abspath(pdf_path))

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found.", file=sys.stderr)
        sys.exit(2)

    if not os.path.exists(yaml_path):
        print(f"Error: YAML file '{yaml_path}' not found.", file=sys.stderr)
        sys.exit(2)

    # Run the audit
    report = run_audit(pdf_path, yaml_path)
    if report is None:
        print("Error: Audit could not be completed.", file=sys.stderr)
        sys.exit(2)

    # Write YAML report
    yaml_out = os.path.join(output_dir, "Parseability_Report.yaml")
    with open(yaml_out, 'w', encoding='utf-8') as f:
        yaml.safe_dump(report, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Parseability report YAML written: {yaml_out}")

    # Generate PDF report via the renderer
    pdf_out = os.path.join(output_dir, "Parseability_Report.pdf")

    # Add the renderer to the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    from renderers.parseability_report import create_parseability_report_pdf
    create_parseability_report_pdf(report, pdf_out)
    print(f"Parseability report PDF written: {pdf_out}")

    # Print summary to console
    print()
    print("=" * 60)
    print("PARSE-INTEGRITY AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Overall:        {report['overall_status'].upper()}")
    print(f"  Unicode:        {report['unicode_status']}")
    print(f"  Keywords:       {report['keyword_recovery_pct']}% ({report['keywords_recovered']}/{report['keywords_total']})")
    print(f"  Sections:       {report['sections_found']}/{report['sections_total']}")
    print(f"  Contact:        {report['contact_fields_found']}/{report['contact_fields_total']}")
    print(f"  Pages:          {report['pages']}")
    print(f"  Text extracted: {report['total_chars']} chars / {report['total_words']} words")
    if report['keywords_missing']:
        print(f"  Missing:        {report['keywords_missing']}")
    print("=" * 60)

    # Exit code
    sys.exit(0 if report['overall_status'] == 'Pass' else 1)


if __name__ == '__main__':
    main()
