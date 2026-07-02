"""
Resume renderer — LaTeX primary, ReportLab fallback.
Handles documents with type: resume
"""
import os
import sys
import shutil

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from .utils import TEXT_DARK, TEXT_MUTED, LINE_COLOR, escape_latex, run_pdflatex


# ── Language Helpers & Dynamic Headers ────────────────────────────────────────

HEADERS = {
    'english': {
        'summary': 'Summary',
        'education': 'Education',
        'technical_skills': 'Technical Skills',
        'projects': 'Projects',
        'professional_experience': 'Professional Experience',
        'spoken_languages': 'Spoken Languages'
    },
    'german': {
        'summary': 'Zusammenfassung',
        'education': 'Ausbildung',
        'technical_skills': 'Technische Fähigkeiten',
        'projects': 'Projekte',
        'professional_experience': 'Berufserfahrung',
        'spoken_languages': 'Sprachen'
    }
}


def get_resume_language(data):
    # Check top-level language field first
    lang = str(data.get('language', '')).lower().strip()
    if 'german' in lang or 'deutsch' in lang or lang == 'de':
        return 'german'
    if 'english' in lang or lang == 'en':
        return 'english'
    
    # Fallback to key heuristics
    german_keys = {'zusammenfassung', 'ausbildung', 'berufserfahrung', 'projekte', 'sprachen', 'technische_fähigkeiten', 'technische fähigkeiten'}
    for key in german_keys:
        if key in data:
            return 'german'
            
    return 'english'


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def create_resume_pdf(data, output_path):
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
                shutil.copy2(resolved_photo, os.path.join(pdf_dir, photo_filename))
            except Exception as e:
                print(f"Warning: Failed to copy photo: {e}", file=sys.stderr)
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
    except Exception as e:
        print(f"Error compiling LaTeX: {e}", file=sys.stderr)
        print("Falling back to ReportLab compilation...", file=sys.stderr)
        create_resume_pdf_reportlab(data, output_path)
    finally:
        if has_photo:
            temp_photo_path = os.path.join(pdf_dir, photo_filename)
            if os.path.exists(temp_photo_path):
                try:
                    os.remove(temp_photo_path)
                except Exception as e:
                    print(f"Warning: Could not remove copied photo: {e}", file=sys.stderr)


# ── ReportLab fallback ────────────────────────────────────────────────────────

_OPEN_SANS_REGISTERED = False

def _register_open_sans():
    """Register Open Sans TTF fonts with ReportLab. Falls back silently if files are missing."""
    global _OPEN_SANS_REGISTERED
    if _OPEN_SANS_REGISTERED:
        return True
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = r"C:\Windows\Fonts"
        regular  = os.path.join(font_dir, "OpenSans-Regular.ttf")
        bold     = os.path.join(font_dir, "OpenSans-Semibold.ttf")  # Semibold as bold

        if not (os.path.exists(regular) and os.path.exists(bold)):
            return False

        pdfmetrics.registerFont(TTFont("OpenSans",        regular))
        pdfmetrics.registerFont(TTFont("OpenSans-Bold",   bold))
        # ReportLab italic synthesis: register same file under italic names
        pdfmetrics.registerFont(TTFont("OpenSans-Italic",     regular))
        pdfmetrics.registerFont(TTFont("OpenSans-BoldItalic", bold))
        pdfmetrics.registerFontFamily(
            "OpenSans",
            normal="OpenSans",
            bold="OpenSans-Bold",
            italic="OpenSans-Italic",
            boldItalic="OpenSans-BoldItalic",
        )
        _OPEN_SANS_REGISTERED = True
        return True
    except Exception as e:
        print(f"Warning: Could not register Open Sans fonts: {e}", file=sys.stderr)
        return False


def create_resume_pdf_reportlab(data, output_path):
    use_open_sans = _register_open_sans()
    F_REG    = "OpenSans"        if use_open_sans else "Helvetica"
    F_BOLD   = "OpenSans-Bold"   if use_open_sans else "Helvetica-Bold"
    F_ITALIC = "OpenSans-Italic" if use_open_sans else "Helvetica-Oblique"

    margin = 0.4 * inch
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    printable_width = A4[0] - (2 * margin)
    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'ResName', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=18, leading=22, textColor=colors.black,
    )
    contact_style = ParagraphStyle(
        'ResContact', parent=styles['Normal'],
        fontName=F_REG, fontSize=8.5, leading=11.5, textColor=TEXT_MUTED,
    )
    section_title_style = ParagraphStyle(
        'ResSectionTitle', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=10.5, leading=13, textColor=colors.HexColor('#1A365D'),
    )
    summary_style = ParagraphStyle(
        'ResSummary', parent=styles['Normal'],
        fontName=F_REG, fontSize=9.5, leading=13.5, alignment=4, textColor=TEXT_DARK,
    )
    comp_style = ParagraphStyle(
        'ResComp', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=9.5, leading=12, textColor=colors.black,
    )
    date_style = ParagraphStyle(
        'ResDate', parent=styles['Normal'],
        fontName=F_REG, fontSize=9, leading=12, alignment=2, textColor=TEXT_DARK,
    )
    title_style = ParagraphStyle(
        'ResTitle', parent=styles['Normal'],
        fontName=F_ITALIC, fontSize=8.5, leading=11, textColor=TEXT_MUTED,
    )
    bullet_style = ParagraphStyle(
        'ResBullet', parent=styles['Normal'],
        fontName=F_REG, fontSize=9.5, leading=13.5,
        leftIndent=12, firstLineIndent=-8, spaceAfter=2, textColor=TEXT_DARK,
    )
    skill_val_style = ParagraphStyle(
        'ResSkillVal', parent=styles['Normal'],
        fontName=F_REG, fontSize=9, leading=12,
        leftIndent=6, firstLineIndent=-6, textColor=TEXT_DARK,
    )
    proj_title_style = ParagraphStyle(
        'ResProjTitle', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=9.5, leading=12, textColor=colors.black,
    )

    story = []

    # Header
    contact  = data.get('contact_info', {})
    raw_name = contact.get('name', 'Sagar Marthandan')
    if raw_name.isupper():
        raw_name = raw_name.title()
    name_str = f"<font color='#1A365D'><b>{raw_name}</b></font>"

    loc    = contact.get('location', '')
    phone  = contact.get('phone', '')
    github = contact.get('github', '')
    line1  = f"{loc} &nbsp;&bull;&nbsp; {phone}"
    if github:
        line1 += f" &nbsp;&bull;&nbsp; <a href='https://{github}' color='#0000EE'>{github}</a>"

    email    = contact.get('email', '')
    linkedin = contact.get('linkedin', '')
    line2    = ""
    if email:
        line2 += f"<a href='mailto:{email}' color='#0000EE'>{email}</a>"
    if linkedin:
        if line2: line2 += " &nbsp;&bull;&nbsp; "
        line2 += f"<a href='https://{linkedin}' color='#0000EE'>{linkedin}</a>"

    visa  = contact.get('visa', '')
    avail = contact.get('availability', '')
    line3 = f"{visa} &nbsp;&bull;&nbsp; {avail}"

    contact_text      = f"{name_str}<br/><font size=8.5 color='#333333'>{line1}<br/>{line2}<br/>{line3}</font>"
    contact_paragraph = Paragraph(contact_text, contact_style)

    photo_path = contact.get('photo_path', '')
    photo_elem = Paragraph("", contact_style)
    if photo_path:
        resolved_photo = os.path.abspath(photo_path)
        if os.path.exists(resolved_photo):
            photo_elem = Image(resolved_photo, width=80, height=70)
            photo_elem.hAlign = 'RIGHT'
        else:
            print(f"Warning: Photo path not found: {resolved_photo}", file=sys.stderr)

    header_table = Table([[contact_paragraph, photo_elem]], colWidths=[445, 92])
    header_table.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    def add_section_header(title):
        t = Table([[Paragraph(f"<b>{title.upper()}</b>", section_title_style)]], colWidths=[printable_width])
        t.setStyle(TableStyle([
            ('LINEBELOW',     (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))
        return t

    # Summary
    lang_code = get_resume_language(data)
    h = HEADERS[lang_code]

    summary_val = data.get('summary', data.get('zusammenfassung'))
    if summary_val:
        summary_block = [
            add_section_header(h['summary']),
            Spacer(1, 4),
            Paragraph(" ".join(summary_val) if isinstance(summary_val, list) else summary_val, summary_style),
            Spacer(1, 6)
        ]
        story.extend(summary_block)

    # Technical Skills
    skills_list = data.get('technical_skills', data.get('technische_fähigkeiten', data.get('technische fähigkeiten', [])))
    if skills_list:
        skills_block = [
            add_section_header(h['technical_skills']),
            Spacer(1, 4)
        ]
        for i, cat in enumerate(skills_list):
            category_name = cat.get('category', '')
            skills_joined = " &bull; ".join(cat.get('skills', []))
            skills_block.append(Paragraph(f"<b>{category_name}:</b> {skills_joined}", skill_val_style))
            if i < len(skills_list) - 1:
                skills_block.append(Spacer(1, 2))
        skills_block.append(Spacer(1, 6))
        story.extend(skills_block)

    # Projects
    projects_list = data.get('projects', data.get('projekte', []))
    if projects_list:
        for i, proj in enumerate(projects_list):
            proj_block = []
            if i == 0:
                proj_block.append(add_section_header(h['projects']))
                proj_block.append(Spacer(1, 4))
            name       = proj.get('name', '')
            tools      = proj.get('tools', [])
            bullets    = proj.get('bullets', [])
            tools_str  = ", ".join(tools)
            proj_header_para = Paragraph(
                f"<b>{name}</b> &nbsp;&nbsp;&nbsp;<font size=8.5 color='#444444'><i>{tools_str}</i></font>",
                proj_title_style,
            )
            proj_block.append(proj_header_para)
            proj_block.append(Spacer(1, 3))
            for b in bullets:
                proj_block.append(Paragraph(f"&bull;&nbsp;&nbsp;{b}", bullet_style))
            # 8pt gap between projects; tighter gap after last project
            proj_block.append(Spacer(1, 8 if i < len(projects_list) - 1 else 4))
            story.extend(proj_block)

    # Professional Experience
    exp_list = data.get('professional_experience', data.get('berufserfahrung', []))
    if exp_list:
        for i, exp in enumerate(exp_list):
            exp_block  = []
            if i == 0:
                exp_block.append(add_section_header(h['professional_experience']))
                exp_block.append(Spacer(1, 4))
            company    = exp.get('company', '')
            date_range = exp.get('date', '')
            job_title  = exp.get('title', '')
            bullets    = exp.get('bullets', [])

            row1_left  = Paragraph(f"<b>{company}</b>", comp_style)
            row1_right = Paragraph(date_range, date_style)
            exp_table_data = [[row1_left, row1_right]]
            if job_title:
                exp_table_data.append([Paragraph(f"<i>{job_title}</i>", title_style), Paragraph("", date_style)])

            exp_table = Table(exp_table_data, colWidths=[387, 150])
            exp_table.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))
            exp_block.append(exp_table)
            exp_block.append(Spacer(1, 3))
            for b in bullets:
                exp_block.append(Paragraph(f"&bull;&nbsp;&nbsp;{b}", bullet_style))
            # 8pt gap between companies; tighter gap after last entry
            exp_block.append(Spacer(1, 8 if i < len(exp_list) - 1 else 4))
            story.extend(exp_block)

    # Education
    edu_list = data.get('education', data.get('ausbildung', []))
    if edu_list:
        edu_block = [
            add_section_header(h['education']),
            Spacer(1, 4)
        ]
        for edu in edu_list:
            degree      = edu.get('degree', '')
            univ        = edu.get('university', '')
            completion  = edu.get('date', '')
            left_para   = Paragraph(f"<b>{degree}</b> &nbsp;&nbsp;<i>{univ}</i>", comp_style)
            right_para  = Paragraph(completion, date_style)
            edu_table   = Table([[left_para, right_para]], colWidths=[387, 150])
            edu_table.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))
            edu_block.append(edu_table)
            edu_block.append(Spacer(1, 4))
        story.extend(edu_block)

    # Spoken Languages
    lang_items = data.get('languages', data.get('spoken_languages', data.get('sprachen', [])))
    if lang_items:
        lang_block = [
            add_section_header(h['spoken_languages']),
            Spacer(1, 4),
            Paragraph(" &bull; ".join(lang_items), skill_val_style),
            Spacer(1, 6)
        ]
        story.extend(lang_block)

    doc.build(story)
    print(f"Successfully compiled Resume via ReportLab: {output_path}")
