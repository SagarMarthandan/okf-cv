"""
Resume LaTeX renderer.

Compiles a resume YAML into a PDF via pdflatex, then runs a parse-integrity
audit on the resulting PDF. If the audit fails, the caller is responsible for
triggering the ReportFallback renderer (see resume.py dispatcher).
"""
import os
import sys
import shutil
import yaml

from .utils import TEXT_DARK, escape_latex, run_pdflatex
from .resume_common import HEADERS, get_resume_language


# ── Parse-integrity audit ─────────────────────────────────────────────────────

def _audit_pdf_parse_integrity(pdf_path: str, resume_data: dict) -> dict:
    """Audit a generated PDF for ATS parse-integrity.

    Checks:
      1. Unicode corruption (replacement glyphs U+FFFD).
      2. Keyword recovery — critical tools/skills from resume_data must appear
         in the extracted text layer.

    Returns a dict:
      {
        "status": "Pass" | "Fail",
        "unicode_corruptions": [list of corrupted char positions],
        "missing_keywords": [list of keywords not found in text],
        "keyword_recovery_pct": int (0-100),
      }
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        pdf_text = "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"Warning: Could not extract PDF text for parse-integrity audit: {e}", file=sys.stderr)
        return {
            "status": "Fail",
            "unicode_corruptions": [],
            "missing_keywords": [],
            "keyword_recovery_pct": 0,
            "error": str(e),
        }

    # 1. Check for unicode corruptions
    corruptions = []
    for i, ch in enumerate(pdf_text):
        if ch == '\uFFFD':
            corruptions.append(i)

    # 2. Build keyword list from resume data
    keywords = set()
    # From project tools
    for proj in resume_data.get('projects', resume_data.get('projekte', [])):
        if isinstance(proj, dict):
            for t in proj.get('tools', []):
                if t and len(str(t)) > 1:
                    keywords.add(str(t).strip())
    # From technical skills
    for cat in resume_data.get('technical_skills', resume_data.get('technische_fähigkeiten', resume_data.get('technische fähigkeiten', []))):
        if isinstance(cat, dict):
            for s in cat.get('skills', []):
                if s and len(str(s)) > 1:
                    keywords.add(str(s).strip())
    # Always check these critical ATS terms
    keywords.update(['dbt', 'Snowflake', 'Airflow', 'Python', 'SQL'])

    # Check keyword recovery (case-insensitive substring match)
    pdf_text_lower = pdf_text.lower()
    missing = []
    for kw in sorted(keywords):
        if kw.lower() not in pdf_text_lower:
            missing.append(kw)

    total_keywords = len(keywords)
    recovered = total_keywords - len(missing)
    recovery_pct = int((recovered / total_keywords * 100)) if total_keywords > 0 else 100

    status = "Pass" if (not corruptions and recovery_pct == 100) else "Fail"

    return {
        "status": status,
        "unicode_corruptions": corruptions,
        "missing_keywords": missing,
        "keyword_recovery_pct": recovery_pct,
    }


def _write_parse_integrity_report(report_path: str, audit_result: dict, fallback_triggered: bool = False) -> None:
    """Write (or merge into) Layout_Audit_Report.yaml with parse-integrity results."""
    entry = {
        "status": audit_result["status"],
        "unicode_corruptions": audit_result.get("unicode_corruptions", []),
        "missing_keywords": audit_result.get("missing_keywords", []),
        "keyword_recovery_pct": audit_result.get("keyword_recovery_pct", 0),
        "fallback_triggered": fallback_triggered,
    }

    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f)
            if not isinstance(existing, dict):
                existing = {}
        except Exception:
            existing = {}
    else:
        existing = {}

    existing["parse_integrity_verification"] = entry

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(existing, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Warning: Could not write parse-integrity report to {report_path}: {e}", file=sys.stderr)


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def create_resume_pdf_latex(data, output_path):
    print(f"Attempting to compile Resume via LaTeX: {output_path}")

    # 1. Parse contact info and format header
    contact = data.get('contact_info', {})
    raw_name = contact.get('name', 'Sagar Marthandan')
    if raw_name.isupper():
        raw_name = raw_name.title()
    name = escape_latex(raw_name)

    loc    = escape_latex(contact.get('location', ''))
    phone  = escape_latex(contact.get('phone', ''))
    github = contact.get('github', '')
    email  = contact.get('email', '')
    linkedin = contact.get('linkedin', '')
    visa   = escape_latex(contact.get('visa', ''))
    avail  = escape_latex(contact.get('availability', ''))

    # Contact line 1
    line1_parts = []
    if loc:   line1_parts.append(loc)
    if phone: line1_parts.append(phone)
    if github:
        github_clean = github.replace('https://', '').replace('http://', '')
        line1_parts.append(f"\\href{{https://{github_clean}}}{{{escape_latex(github_clean)}}}")
    line1 = " $\\cdot$ ".join(line1_parts)

    # Contact line 2
    line2_parts = []
    if email:
        line2_parts.append(f"\\href{{mailto:{email}}}{{{escape_latex(email)}}}")
    if linkedin:
        linkedin_clean = linkedin.replace('https://', '').replace('http://', '')
        line2_parts.append(f"\\href{{https://{linkedin_clean}}}{{{escape_latex(linkedin_clean)}}}")
    line2 = " $\\cdot$ ".join(line2_parts)

    # Contact line 3
    line3_parts = []
    if visa:  line3_parts.append(visa)
    if avail: line3_parts.append(avail)
    line3 = " $\\cdot$ ".join(line3_parts)

    contact_lines = [l for l in [line1, line2, line3] if l]
    contact_details_str = " \\\\\n  ".join(contact_lines)

    # 2. Check and copy photo
    photo_path   = contact.get('photo_path', '')
    has_photo    = False
    photo_filename = ""
    pdf_dir      = os.path.dirname(os.path.abspath(output_path))

    if photo_path:
        resolved_photo = os.path.abspath(photo_path)
        if os.path.exists(resolved_photo):
            has_photo = True
            ext = os.path.splitext(resolved_photo)[1]
            photo_filename = f"temp_photo{ext}"
            try:
                shutil.copy(resolved_photo, os.path.join(pdf_dir, photo_filename))
            except Exception as e:
                print(f"Warning: Could not copy photo: {e}", file=sys.stderr)
                has_photo = False

    if has_photo:
        header_tex = f"""\\begin{{minipage}}[b]{{0.82\\textwidth}}
  {{\\Huge\\bfseries\\color{{darkblue}} {name}}} \\\\[6pt]
  {{\\small
  {contact_details_str}
  }}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[b]{{0.15\\textwidth}}
  \\raggedleft
  \\includegraphics[width=\\linewidth,height=2.5cm,keepaspectratio]{{{photo_filename}}}
\\end{{minipage}}
\\vspace{{0pt}}"""
    else:
        header_tex = f"""{{\\Huge\\bfseries\\color{{darkblue}} {name}}} \\\\[6pt]
{{\\small
{contact_details_str}
}}
\\vspace{{0pt}}"""

    # 3. Format sections

    lang_code = get_resume_language(data)
    h = HEADERS[lang_code]

    # A. Summary
    summary_text = ""
    summary_val = data.get('summary', data.get('zusammenfassung'))
    if summary_val:
        summary_text = escape_latex(" ".join(summary_val) if isinstance(summary_val, list) else summary_val)
    summary_tex = (
        f"\\vspace{{6pt}}\n"
        f"\\section{{{h['summary']}}}\n"
        f"{summary_text}"
    ) if summary_text else ""

    # B. Education
    edu_tex_items = []
    edu_list = data.get('education', data.get('ausbildung', []))
    for edu in edu_list:
        degree = escape_latex(edu.get('degree', ''))
        univ   = escape_latex(edu.get('university', ''))
        date   = escape_latex(edu.get('date', ''))
        edu_tex_items.append(f"\\eduEntry{{{degree}}}{{{univ}}}{{{date}}}")
    education_body = " \\\\\n".join(edu_tex_items)
    education_tex = (
        f"\\section{{{h['education']}}}\n"
        f"{education_body}"
    ) if edu_tex_items else ""

    # C. Technical Skills
    skills_tex_items = []
    skills_list = data.get('technical_skills', data.get('technische_fähigkeiten', data.get('technische fähigkeiten', [])))
    for skill_cat in skills_list:
        cat    = escape_latex(skill_cat.get('category', ''))
        skills = [escape_latex(s) for s in skill_cat.get('skills', [])]
        skills_joined = " $\\cdot$ ".join(skills)
        skills_tex_items.append(f"{{\\hangindent=6pt\\relax \\textbf{{{cat}:}} {skills_joined}}}")
    skills_body = "\\\\[1pt]\n".join(skills_tex_items)
    skills_tex = (
        f"\\section{{{h['technical_skills']}}}\n"
        f"{skills_body}"
    ) if skills_tex_items else ""

    # D. Projects
    proj_tex_items = []
    projects_list = data.get('projects', data.get('projekte', []))
    for i, proj in enumerate(projects_list):
        proj_name  = escape_latex(proj.get('name', ''))
        repo_url   = proj.get('repo_url', proj.get('url', ''))
        if repo_url:
            proj_name = f"{proj_name} (\\href{{{repo_url}}}{{\\color{{darkblue}}\\small[GitHub]}})"
        tools      = [escape_latex(t) for t in proj.get('tools', [])]
        tools_str  = ", ".join(tools)
        bullets    = [escape_latex(b) for b in proj.get('bullets', [])]
        bullets_tex = "\n".join([f"  \\resumeItem{{{b}}}" for b in bullets])

        item_tex = (
            f"\\resumeProject{{{proj_name}}} \\projectTools{{Tools: {tools_str}}}\n"
            f"\\vspace{{2pt}}\n"
            f"\\begin{{itemize}}[leftmargin=*,nosep,itemsep=1pt]\n{bullets_tex}\n\\end{{itemize}}\\par"
        )
        if i == 0:
            proj_tex_items.append(
                f"\\section{{{h['projects']}}}\n"
                f"\\vspace{{2pt}}\n"
                f"{item_tex}"
            )
        else:
            proj_tex_items.append(item_tex)
    projects_tex = "\n\\vspace{6pt}\n".join(proj_tex_items) if proj_tex_items else ""

    # E. Professional Experience
    exp_tex_items = []
    exp_list = data.get('professional_experience', data.get('berufserfahrung', []))
    for i, exp in enumerate(exp_list):
        company    = escape_latex(exp.get('company', ''))
        date       = escape_latex(exp.get('date', ''))
        title      = escape_latex(exp.get('title', ''))
        bullets    = [escape_latex(b) for b in exp.get('bullets', [])]
        bullets_tex = "\n".join([f"  \\resumeItem{{{b}}}" for b in bullets])

        item_tex = (
            f"\\jobEntry{{{company}}}{{{date}}}\\\\*\n"
            f"\\vspace{{2pt}}\n"
            f"\\jobTitle{{{title}}}\n"
            f"\\vspace{{2pt}}\n"
            f"\\begin{{itemize}}[leftmargin=*,nosep,itemsep=1pt]\n{bullets_tex}\n\\end{{itemize}}\\par"
        )
        if i == 0:
            exp_tex_items.append(
                f"\\section{{{h['professional_experience']}}}\n"
                f"\\vspace{{2pt}}\n"
                f"{item_tex}"
            )
        else:
            exp_tex_items.append(item_tex)
    experience_tex = "\n\\vspace{6pt}\n".join(exp_tex_items) if exp_tex_items else ""

    # F. Spoken Languages
    lang_items = data.get('languages', data.get('spoken_languages', data.get('sprachen', [])))
    if lang_items:
        lang_joined = " $\\cdot$ ".join([escape_latex(l) for l in lang_items])
        lang_tex = (
            f"\\section{{{h['spoken_languages']}}}\n"
            f"{lang_joined}"
        )
    else:
        lang_tex = ""

    sections = [s for s in [summary_tex, skills_tex, projects_tex,
                             experience_tex, education_tex, lang_tex] if s]
    body_tex = "\n\n\\vspace{6pt}\n\n".join(sections)

    # 4. Generate LaTeX document
    tex_content = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=0.4in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{titlesec}}
\\usepackage{{hyperref}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{graphicx}}
\\usepackage{{textcomp}}
\\usepackage{{xcolor}}

\\input{{glyphtounicode}}
\\pdfgentounicode=1
\\usepackage[none]{{hyphenat}}

\\definecolor{{darkblue}}{{HTML}}{{1A365D}}
\\definecolor{{BLACK}}{{HTML}}{{000000}}

\\pagestyle{{empty}}
\\setlength{{\\parindent}}{{0pt}}

\\titleformat{{\\section}}{{\\large\\bfseries\\color{{darkblue}}\\uppercase}}{{}}{{0em}}{{}}[\\color{{black}}\\titlerule]
\\titlespacing{{\\section}}{{0pt}}{{6pt}}{{4pt}}

\\newcommand{{\\resumeItem}}[1]{{\\item[$\\cdot$] {{#1}}}}
\\newcommand{{\\eduEntry}}[3]{{\\textbf{{#1}} {{\\small\\textit{{#2}}}} \\hfill {{\\small\\textit{{#3}}}}}}
\\newcommand{{\\resumeProject}}[1]{{{{\\normalsize\\textbf{{#1}}}}}}
\\newcommand{{\\projectTools}}[1]{{{{\\footnotesize\\textit{{#1}}}}}}
\\newcommand{{\\jobEntry}}[2]{{{{\\normalsize\\textbf{{#1}} \\hfill {{\\normalsize#2}}}}}}
\\newcommand{{\\jobTitle}}[1]{{{{\\small\\textit{{#1}}}}}}

\\hypersetup{{colorlinks=true,urlcolor=black,linkcolor=black}}

\\begin{{document}}

{header_tex}

{body_tex}

\\end{{document}}
"""

    pdf_name     = os.path.basename(output_path)
    base_name    = os.path.splitext(pdf_name)[0]
    tex_filename = f"{base_name}.tex"
    tex_path     = os.path.join(pdf_dir, tex_filename)

    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)

    try:
        run_pdflatex(tex_filename, pdf_dir, label="Resume", keep_tex=True)
        print(f"Successfully compiled Resume via LaTeX: {output_path}")

        # ── Parse-integrity audit ────────────────────────────────────────────
        layout_report_path = os.path.join(pdf_dir, "Layout_Audit_Report.yaml")
        if os.path.exists(output_path):
            audit = _audit_pdf_parse_integrity(output_path, data)
            fallback_triggered = False

            if audit["status"] == "Fail":
                print(f"\n*** PARSE-INTEGRITY AUDIT FAILED ***", file=sys.stderr)
                if audit.get("unicode_corruptions"):
                    print(f"  Unicode corruptions detected: {len(audit['unicode_corruptions'])} replacement glyphs (U+FFFD)", file=sys.stderr)
                if audit.get("missing_keywords"):
                    print(f"  Missing keywords from PDF text layer: {audit['missing_keywords']}", file=sys.stderr)
                print(f"  Keyword recovery: {audit['keyword_recovery_pct']}%", file=sys.stderr)
                print(f"  Triggering ReportLab fallback for ATS-safe PDF...", file=sys.stderr)

                # Lazy import to avoid circular dependency
                from .resume_reportfallback import create_resume_pdf_reportlab
                create_resume_pdf_reportlab(data, output_path)
                fallback_triggered = True

                # Re-audit the ReportLab PDF
                if os.path.exists(output_path):
                    rl_audit = _audit_pdf_parse_integrity(output_path, data)
                    if rl_audit["status"] == "Fail":
                        _write_parse_integrity_report(layout_report_path, rl_audit, fallback_triggered=True)
                        print(f"\n*** FATAL: ReportLab fallback PDF also failed parse-integrity audit ***", file=sys.stderr)
                        print(f"  Missing keywords: {rl_audit.get('missing_keywords', [])}", file=sys.stderr)
                        raise Exception("Both LaTeX and ReportLab PDFs failed parse-integrity audit. Pipeline halted.")
                    else:
                        print(f"  ReportLab fallback passed parse-integrity audit (recovery: {rl_audit['keyword_recovery_pct']}%)", file=sys.stderr)
                        _write_parse_integrity_report(layout_report_path, rl_audit, fallback_triggered=True)
            else:
                print(f"  Parse-integrity audit: PASS (keyword recovery: {audit['keyword_recovery_pct']}%)")
                _write_parse_integrity_report(layout_report_path, audit, fallback_triggered=False)

    except Exception as e:
        print(f"Error compiling LaTeX: {e}", file=sys.stderr)
        print("Falling back to ReportLab compilation...", file=sys.stderr)
        from .resume_reportfallback import create_resume_pdf_reportlab
        create_resume_pdf_reportlab(data, output_path)
    finally:
        if has_photo:
            temp_photo_path = os.path.join(pdf_dir, photo_filename)
            if os.path.exists(temp_photo_path):
                try:
                    os.remove(temp_photo_path)
                except Exception as e:
                    print(f"Warning: Could not remove copied photo: {e}", file=sys.stderr)
