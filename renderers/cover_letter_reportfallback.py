"""
Cover letter ReportFallback renderer.

Produces the same Geschäftsbrief layout as the LaTeX renderer (sender block,
recipient block, right-aligned date, bold subject, salutation, body
paragraphs, closing + signature) but via ReportLab using the Calibri font
family.

Used in two cases:
  1. The user selects `reportfallback` as the render mode at pipeline start.
  2. The LaTeX renderer fails to compile and this renderer is triggered
     automatically as a fallback.
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from .utils import TEXT_DARK, format_address, register_lm_roman_10


def create_cover_letter_pdf_reportlab(data, output_path):
    F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC = register_lm_roman_10()

    margin = 1.0 * inch
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    styles = getSampleStyleSheet()

    sender_style = ParagraphStyle(
        'CLSender', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12,
        textColor=colors.HexColor('#333333'),
    )
    recipient_style = ParagraphStyle(
        'CLRecipient', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12, textColor=colors.black,
    )
    date_style = ParagraphStyle(
        'CLDate', parent=styles['Normal'],
        fontName=F_REG, fontSize=10, leading=12, alignment=2, textColor=colors.black,
    )
    subject_style = ParagraphStyle(
        'CLSubject', parent=styles['Normal'],
        fontName=F_BOLD, fontSize=11, leading=13, textColor=colors.black,
    )
    body_style = ParagraphStyle(
        'CLBody', parent=styles['Normal'],
        fontName=F_REG, fontSize=10.5, leading=13.5, alignment=4, textColor=TEXT_DARK,
    )

    story = []

    sender      = data.get('sender', {})
    sender_addr = format_address(sender.get('address', ''), latex=False)

    raw_sender = sender.get('name', '')
    if raw_sender.isupper():
        raw_sender = raw_sender.title()
    sender_text = f"<b>{raw_sender}</b><br/>{sender_addr}<br/>{sender.get('phone', '')}<br/>{sender.get('email', '')}"
    story.append(Paragraph(sender_text, sender_style))
    story.append(Spacer(1, 14))

    recipient = data.get('recipient', {})
    rec_addr  = format_address(recipient.get('address', ''), latex=False)

    rec_text = f"<b>{recipient.get('company', '')}</b><br/>{recipient.get('department', '')}<br/>{rec_addr}"
    story.append(Paragraph(rec_text, recipient_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(data.get('date', ''), date_style))
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"<b>{data.get('subject', '')}</b>", subject_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(data.get('salutation', 'Sehr geehrte Damen und Herren,'), body_style))
    story.append(Spacer(1, 6))

    for p in data.get('paragraphs', []):
        story.append(Paragraph(p, body_style))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 8))

    closing    = data.get('closing', 'Mit freundlichen Grüßen,')
    sig_name   = data.get('signature_name', '')
    if sig_name.isupper():
        sig_name = sig_name.title()
    story.append(Paragraph(f"{closing}<br/><br/><b>{sig_name}</b>", body_style))

    doc.build(story)
    print(f"Successfully compiled Cover Letter via ReportLab (LM Roman 10): {output_path}")
