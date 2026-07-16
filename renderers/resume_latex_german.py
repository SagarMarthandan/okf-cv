"""
Resume LaTeX renderer — German market style.

Produces a Lebenslauf PDF with German-convention section ordering:
  Summary → Professional Experience → Education → Technical Skills →
  Projects → Spoken Languages

Language is determined by get_resume_language(data) — automatic from JD.
The renderer works for both German and English language content; the
*style* (section order) is always German market.

Used when the user selects:
  render_mode: latex
  resume_style: german
"""
import os
import sys

from .utils import TEXT_DARK, escape_latex, run_pdflatex
from .resume_common import HEADERS, get_resume_language, get_section_order, format_date_numeric


# ── German-style section order ───────────────────────────────────────────────

GERMAN_STYLE_SECTION_ORDER = [
    'summary',
    'professional_experience',
    'education',
    'technical_skills',
    'spoken_languages',
]


def _generate_resume_tex_germany(data, output_path):
    """Generate the .tex source file for a German-style resume."""
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

    line1_parts = []
    if loc:   line1_parts.append(loc)
    if phone: line1_parts.append(phone)
    if github:
        github_clean = github.replace('https://', '').replace('http://', '')
        line1_parts.append(f"\\href{{https://{github_clean}}}{{{escape_latex(github_clean)}}}")
    line1 = " $\\cdot$ ".join(line1_parts)

    line2_parts = []
    if email:
        line2_parts.append(f"\\href{{mailto:{email}}}{{{escape_latex(email)}}}")
    if linkedin:
        linkedin_clean = linkedin.replace('https://', '').replace('http://', '')
        line2_parts.append(f"\\href{{https://{linkedin_clean}}}{{{escape_latex(linkedin_clean)}}}")
    line2 = " $\\cdot$ ".join(line2_parts)

    line3_parts = []
    if visa:  line3_parts.append(visa)
    if avail: line3_parts.append(avail)
    line3 = " $\\cdot$ ".join(line3_parts)

    contact_lines = [l for l in [line1, line2, line3] if l]
    contact_details_str = " \\\\\n  ".join(contact_lines)

    pdf_dir = os.path.dirname(os.path.abspath(output_path))

    header_tex = f"""{{\\Huge\\bfseries\\color{{darkblue}} {name}}} \\\\[6pt]
{{\\small
{contact_details_str}
}}
\\vspace{{0pt}}"""

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

    # B. Professional Experience
    exp_tex_items = []
    exp_list = data.get('professional_experience', data.get('berufserfahrung', []))
    for i, exp in enumerate(exp_list):
        company    = escape_latex(exp.get('company', ''))
        date       = escape_latex(format_date_numeric(exp.get('date', '')))
        title      = escape_latex(exp.get('title', ''))
        bullets    = [escape_latex(b) for b in exp.get('bullets', [])]

        # Project-style bullets (name --- [GitHub] --- summary format)
        project_bullets = exp.get('project_bullets', [])
        proj_bullets_tex = ""
        if project_bullets:
            proj_lines = []
            for pb in project_bullets:
                pb_name    = escape_latex(pb.get('name', ''))
                pb_url     = pb.get('repo_url', pb.get('url', ''))
                pb_bullets = [escape_latex(b) for b in pb.get('bullets', [])]
                pb_summary = " ".join(pb_bullets).strip()
                pb_link = f" --- \\href{{{pb_url}}}{{\\color{{darkblue}}\\small[GitHub]}}" if pb_url else ""
                proj_lines.append(f"  \\resumeItem{{\\textbf{{{pb_name}}}{pb_link} --- {pb_summary.rstrip('.')} .}}")
            proj_bullets_tex = "\n".join(proj_lines) + "\n"

        bullets_tex = "\n".join([f"  \\resumeItem{{{b}}}" for b in bullets])
        all_bullets_tex = "\n".join(filter(None, [proj_bullets_tex, bullets_tex]))

        item_tex = (
            f"\\jobEntry{{{company}}}{{{date}}}\\\\*\n"
            f"\\vspace{{2pt}}\n"
            f"\\jobTitle{{{title}}}\n"
            f"\\vspace{{2pt}}\n"
            f"\\begin{{itemize}}[leftmargin=1.2em, itemindent=0pt, labelsep=0.4em, labelwidth=0.5em, nosep, itemsep=1pt]\n{all_bullets_tex}\n\\end{{itemize}}\\par"
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

    # C. Education
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

    # D. Technical Skills
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

    # E. Projects — single-paragraph format
    proj_tex_items = []
    projects_list = data.get('projects', data.get('projekte', []))
    for i, proj in enumerate(projects_list):
        proj_name  = escape_latex(proj.get('name', ''))
        repo_url   = proj.get('repo_url', proj.get('url', ''))
        bullets    = [escape_latex(b) for b in proj.get('bullets', [])]
        summary    = " ".join(bullets).strip()

        link_tex = f" --- \\href{{{repo_url}}}{{\\color{{darkblue}}\\small[GitHub]}}" if repo_url else ""
        item_tex = f"\\noindent\\textbf{{{proj_name}}}{link_tex} --- {summary}.\\par"

        if i == 0:
            proj_tex_items.append(
                f"\\section{{{h['projects']}}}\n"
                f"\\vspace{{2pt}}\n"
                f"{item_tex}"
            )
        else:
            proj_tex_items.append(item_tex)
    projects_tex = "\n\\vspace{4pt}\n".join(proj_tex_items) if proj_tex_items else ""

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

    section_map = {
        'summary': summary_tex,
        'technical_skills': skills_tex,
        'projects': projects_tex,
        'professional_experience': experience_tex,
        'education': education_tex,
        'spoken_languages': lang_tex,
    }

    # German style uses its own fixed order — no YAML override needed.
    # But respect section_order if explicitly provided (for flexibility).
    raw_order = data.get('section_order')
    if raw_order and isinstance(raw_order, list):
        valid = set(GERMAN_STYLE_SECTION_ORDER)
        order = [k for k in raw_order if k in valid]
    else:
        order = GERMAN_STYLE_SECTION_ORDER

    sections = [section_map[k] for k in order
                if k in section_map and section_map[k]]
    body_tex = "\n\n\\vspace{6pt}\n\n".join(sections)

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

\\newcommand{{\\resumeItem}}[1]{{\\item[$\\cdot$] \\fussy {{#1}}}}
\\newcommand{{\\eduEntry}}[3]{{\\textbf{{#1}} {{\\small\\textit{{#2}}}} \\hfill {{\\small\\textit{{#3}}}}}}
\\newcommand{{\\resumeProject}}[1]{{{{\\normalsize\\textbf{{#1}}}}}}
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

    return tex_path, pdf_dir


def create_resume_pdf_latex_germany_tex_only(data, output_path):
    """Write the .tex source file without running pdflatex."""
    print(f"Generating German-style Resume .tex (tex-only mode): {output_path}")
    tex_path, pdf_dir = _generate_resume_tex_germany(data, output_path)
    print(f"Wrote LaTeX source: {tex_path}")


def create_resume_pdf_latex_germany(data, output_path):
    """Compile a German-style resume via LaTeX."""
    print(f"Attempting to compile German-style Resume via LaTeX: {output_path}")
    tex_path, pdf_dir = _generate_resume_tex_germany(data, output_path)
    tex_filename = os.path.basename(tex_path)

    try:
        run_pdflatex(tex_filename, pdf_dir, label="Resume (German style)", keep_tex=True)
        print(f"Successfully compiled German-style Resume via LaTeX: {output_path}")

    except Exception as e:
        print(f"Error compiling LaTeX: {e}", file=sys.stderr)
        print("Falling back to ReportLab German-style compilation...", file=sys.stderr)
        from .resume_reportfallback_german import create_resume_pdf_reportlab_germany
        create_resume_pdf_reportlab_germany(data, output_path)
