"""
Cover letter renderer — LaTeX primary, ReportLab fallback.
Handles documents with type: cover_letter
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from .utils import TEXT_DARK, escape_latex, run_pdflatex, format_address


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def create_cover_letter_pdf(data, output_path):
    print(f"Attempting to compile Cover Letter via LaTeX: {output_path}")

    sender      = data.get('sender', {})
    raw_sender  = sender.get('name', '')
    if raw_sender.isupper():
        raw_sender = raw_sender.title()
    sender_name = escape_latex(raw_sender)

    sender_addr = format_address(sender.get('address', ''), latex=True)

    sender_phone = escape_latex(sender.get('phone', ''))
    sender_email = escape_latex(sender.get('email', ''))

    recipient   = data.get('recipient', {})
    rec_company = escape_latex(recipient.get('company', ''))
    rec_dept    = escape_latex(recipient.get('department', ''))

    rec_addr = format_address(recipient.get('address', ''), latex=True)

    date_val       = escape_latex(data.get('date', ''))
    subject_val    = escape_latex(data.get('subject', ''))
    salutation_val = escape_latex(data.get('salutation', ''))

    paragraphs_tex = "\n\n".join([escape_latex(p) for p in data.get('paragraphs', [])])

    closing_val    = escape_latex(data.get('closing', ''))
    raw_sig        = data.get('signature_name', '')
    if raw_sig.isupper():
        raw_sig = raw_sig.title()
    signature_name = escape_latex(raw_sig)

    tex_content = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=1.0in]{{geometry}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{hyperref}}
\\usepackage{{parskip}}

\\pagestyle{{empty}}
\\setlength{{\\parindent}}{{0pt}}

\\hypersetup{{colorlinks=true,urlcolor=black,linkcolor=black}}

\\begin{{document}}

{{\\small
\\textbf{{{sender_name}}} \\\\
{sender_addr} \\\\
{sender_phone} \\\\
{sender_email}
}}

\\vspace{{20pt}}

\\textbf{{{rec_company}}} \\\\
{rec_dept} \\\\
{rec_addr}

\\vspace{{15pt}}

\\hfill {date_val}

\\vspace{{20pt}}

\\textbf{{\\large {subject_val}}}

\\vspace{{15pt}}

{salutation_val}

\\vspace{{10pt}}

{paragraphs_tex}

\\vspace{{15pt}}

{closing_val} \\\\
\\vspace{{30pt}} \\\\
\\textbf{{{signature_name}}}

\\end{{document}}
"""

    pdf_dir      = os.path.dirname(os.path.abspath(output_path))
    base_name    = os.path.splitext(os.path.basename(output_path))[0]
    tex_filename = f"{base_name}.tex"

    with open(os.path.join(pdf_dir, tex_filename), 'w', encoding='utf-8') as f:
        f.write(tex_content)

    try:
        run_pdflatex(tex_filename, pdf_dir, label="Cover Letter", keep_tex=True)
        print(f"Successfully compiled Cover Letter via LaTeX: {output_path}")
    except Exception as e:
        print(f"Error compiling LaTeX: {e}", file=sys.stderr)
        print("Falling back to ReportLab compilation...", file=sys.stderr)
        create_cover_letter_pdf_reportlab(data, output_path)


# ── ReportLab fallback ────────────────────────────────────────────────────────

def create_cover_letter_pdf_reportlab(data, output_path):
    margin = 1.0 * inch
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    styles = getSampleStyleSheet()

    sender_style = ParagraphStyle(
        'CLSender', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=colors.HexColor('#333333'),
    )
    recipient_style = ParagraphStyle(
        'CLRecipient', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14, textColor=colors.black,
    )
    date_style = ParagraphStyle(
        'CLDate', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14, alignment=2, textColor=colors.black,
    )
    subject_style = ParagraphStyle(
        'CLSubject', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=colors.black,
    )
    body_style = ParagraphStyle(
        'CLBody', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10.5, leading=15.5, alignment=4, textColor=TEXT_DARK,
    )

    story = []

    sender      = data.get('sender', {})
    sender_addr = format_address(sender.get('address', ''), latex=False)

    raw_sender = sender.get('name', '')
    if raw_sender.isupper():
        raw_sender = raw_sender.title()
    sender_text = f"<b>{raw_sender}</b><br/>{sender_addr}<br/>{sender.get('phone', '')}<br/>{sender.get('email', '')}"
    story.append(Paragraph(sender_text, sender_style))
    story.append(Spacer(1, 20))

    recipient = data.get('recipient', {})
    rec_addr  = format_address(recipient.get('address', ''), latex=False)

    rec_text = f"<b>{recipient.get('company', '')}</b><br/>{recipient.get('department', '')}<br/>{rec_addr}"
    story.append(Paragraph(rec_text, recipient_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph(data.get('date', ''), date_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"<b>{data.get('subject', '')}</b>", subject_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph(data.get('salutation', 'Sehr geehrte Damen und Herren,'), body_style))
    story.append(Spacer(1, 10))

    for p in data.get('paragraphs', []):
        story.append(Paragraph(p, body_style))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 12))

    closing    = data.get('closing', 'Mit freundlichen Grüßen,')
    sig_name   = data.get('signature_name', '')
    if sig_name.isupper():
        sig_name = sig_name.title()
    story.append(Paragraph(f"{closing}<br/><br/><br/><b>{sig_name}</b>", body_style))

    doc.build(story)
    print(f"Successfully compiled Cover Letter via ReportLab: {output_path}")
