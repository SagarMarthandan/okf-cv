"""
Cover letter LaTeX renderer.

Compiles a cover letter YAML into a PDF via pdflatex. If compilation fails,
the caller is responsible for triggering the ReportFallback renderer (see
cover_letter.py dispatcher).
"""
import os
import sys

from .utils import escape_latex, run_pdflatex, format_address


def create_cover_letter_pdf_latex(data, output_path):
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
        from .cover_letter_reportfallback import create_cover_letter_pdf_reportlab
        create_cover_letter_pdf_reportlab(data, output_path)
