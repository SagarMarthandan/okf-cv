"""
Resume ReportFallback renderer.

Produces the same visual layout as the LaTeX renderer (header with name +
contact + photo, ruled section headers, single-paragraph project entries,
tabbed experience rows) but via ReportLab using the Calibri font family.

Used in two cases:
  1. The user selects `reportfallback` as the render mode at pipeline start.
  2. The LaTeX renderer's parse-integrity audit fails and this renderer is
     triggered automatically as an ATS-safe fallback.
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from .utils import (
    TEXT_DARK, TEXT_MUTED, LINE_COLOR,
    register_lm_roman_10,
)
from .resume_common import HEADERS, get_resume_language


def create_resume_pdf_reportlab(data, output_path):
    F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC = register_lm_roman_10()

    margin = 0.4 * inch
    printable_width = A4[0] - (2 * margin)
    printable_height = A4[1] - (2 * margin)
    # Use BaseDocTemplate with a zero-padding frame so that Tables (section
    # headers) and Paragraphs (body text) both start at the exact same x
    # position. SimpleDocTemplate uses a default 6pt frame padding which
    # causes Paragraphs to appear 6pt indented relative to Tables.
    doc = BaseDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    frame = Frame(
        margin, margin, printable_width, printable_height,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id='normal',
    )
    doc.addPageTemplates([PageTemplate(id='all', frames=[frame], pagesize=A4)])
    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'ResName', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=22, leading=25, textColor=colors.HexColor('#1A365D'),
        leftIndent=0, firstLineIndent=0,
    )
    contact_style = ParagraphStyle(
        'ResContact', parent=styles['Normal'],
        fontName=F_REG, fontSize=9, leading=10.5, textColor=TEXT_MUTED,
        leftIndent=0, firstLineIndent=0,
    )
    section_title_style = ParagraphStyle(
        'ResSectionTitle', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=11, leading=12, textColor=colors.HexColor('#1A365D'),
        leftIndent=0, firstLineIndent=0,
    )
    summary_style = ParagraphStyle(
        'ResSummary', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12.5, alignment=4, textColor=TEXT_DARK,
        leftIndent=0, firstLineIndent=0,
    )
    comp_style = ParagraphStyle(
        'ResComp', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=10, leading=11.5, textColor=colors.black,
        leftIndent=0, firstLineIndent=0,
    )
    date_style = ParagraphStyle(
        'ResDate', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=11.5, alignment=2, textColor=TEXT_DARK,
        leftIndent=0, firstLineIndent=0,
    )
    title_style = ParagraphStyle(
        'ResTitle', parent=styles['Normal'],
        fontName=F_ITALIC, fontSize=9, leading=10.5, textColor=TEXT_MUTED,
        leftIndent=0, firstLineIndent=0,
    )
    bullet_style = ParagraphStyle(
        'ResBullet', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12.5,
        leftIndent=12, firstLineIndent=-8, spaceAfter=1, textColor=TEXT_DARK,
    )
    skill_val_style = ParagraphStyle(
        'ResSkillVal', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12,
        leftIndent=0, firstLineIndent=0, textColor=TEXT_DARK,
    )
    proj_title_style = ParagraphStyle(
        'ResProjTitle', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=10, leading=11.5, textColor=colors.black,
        leftIndent=0, firstLineIndent=0,
    )
    # Single-paragraph project prose style (mirrors the LaTeX polished format)
    proj_para_style = ParagraphStyle(
        'ResProjPara', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12.5, alignment=4,
        leftIndent=0, firstLineIndent=0, spaceAfter=1, textColor=TEXT_DARK,
    )
    # Education: degree bold + university italic only (not bold), same font size
    edu_style = ParagraphStyle(
        'ResEdu', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=11.5, textColor=colors.black,
        leftIndent=0, firstLineIndent=0,
    )

    story = []

    # Header (no photo — name is the dominant element)
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

    # Name on its own line, large; contact lines below in small muted text.
    story.append(Paragraph(name_str, name_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"<font size=8.5 color='#333333'>{line1}<br/>{line2}<br/>{line3}</font>", contact_style))
    story.append(Spacer(1, 5))

    def add_section_header(title):
        t = Table([[Paragraph(f"<b>{title.upper()}</b>", section_title_style)]], colWidths=[printable_width])
        t.setStyle(TableStyle([
            ('LINEBELOW',     (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
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
            Paragraph(
                " ".join(summary_val) if isinstance(summary_val, list) else summary_val,
                summary_style,
            ),
            Spacer(1, 4)
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
                skills_block.append(Spacer(1, 1))
        skills_block.append(Spacer(1, 4))
        story.extend(skills_block)

    # Projects — single-paragraph format (mirrors the LaTeX polished layout)
    projects_list = data.get('projects', data.get('projekte', []))
    if projects_list:
        for i, proj in enumerate(projects_list):
            proj_block = []
            if i == 0:
                proj_block.append(add_section_header(h['projects']))
                proj_block.append(Spacer(1, 4))
            name       = proj.get('name', '')
            repo_url   = proj.get('repo_url', proj.get('url', ''))
            tools      = proj.get('tools', [])
            bullets    = proj.get('bullets', [])
            tools_str  = ", ".join(tools)
            github_link = f" &nbsp;<a href='{repo_url}' color='#1A365D'><font size=8>[GitHub]</font></a>" if repo_url else ""

            # Join bullets into a single prose paragraph to match the LaTeX
            # single-paragraph project format. Tools are woven into the prose
            # only if a bullet already references them; otherwise appended.
            prose = " ".join(bullets).strip()
            # Tools line: 1 font size less than title, compressed (no spaces after
            # commas) to keep on one line. Replace spaces within tool names with
            # non-breaking spaces so ReportLab doesn't wrap mid-tool.
            tools_nbsp = [t.strip().replace(" ", "&nbsp;") for t in tools]
            tools_compressed = ",".join(tools_nbsp)
            # Adaptive font size: smaller for longer headers to fit on one line
            header_len = len(name) + (12 if repo_url else 0) + len(tools_compressed)
            if header_len <= 65:
                tools_size = 7.5
            elif header_len <= 80:
                tools_size = 7.0
            else:
                tools_size = 6.5
            proj_header_para = Paragraph(
                f"<b>{name}</b>{github_link} <font size={tools_size} color='#555555'><i>{tools_compressed}</i></font>",
                proj_title_style,
            )
            proj_block.append(proj_header_para)
            proj_block.append(Spacer(1, 3))
            if prose:
                proj_block.append(Paragraph(prose, proj_para_style))
            # 4pt gap between projects; tighter gap after last project
            proj_block.append(Spacer(1, 4 if i < len(projects_list) - 1 else 2))
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
            # 4pt gap between companies; tighter gap after last entry
            exp_block.append(Spacer(1, 4 if i < len(exp_list) - 1 else 2))
            story.extend(exp_block)

    # Education — degree (bold) + university (italic only, not bold) on the left,
    # date right-aligned (same two-column layout as Professional Experience).
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
            left_para   = Paragraph(f"<b>{degree}</b> <i>{univ}</i>", edu_style)
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
            edu_block.append(Spacer(1, 3))
        story.extend(edu_block)

    # Spoken Languages
    lang_items = data.get('languages', data.get('spoken_languages', data.get('sprachen', [])))
    if lang_items:
        lang_block = [
            add_section_header(h['spoken_languages']),
            Spacer(1, 3),
            Paragraph(" &bull; ".join(lang_items), skill_val_style),
            Spacer(1, 4)
        ]
        story.extend(lang_block)

    doc.build(story)
    print(f"Successfully compiled Resume via ReportLab (LM Roman 10): {output_path}")
