"""
Shared utilities, color constants, and common imports for all PDF renderers.
"""
import os
import sys
import subprocess
import shutil
from typing import Tuple

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

# ── Color palette ─────────────────────────────────────────────────────────────
TEXT_DARK  = colors.HexColor("#222222")
TEXT_MUTED = colors.HexColor("#444444")
LINE_COLOR = colors.HexColor("#111111")
LINK_COLOR = colors.HexColor("#0000EE")


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in a string."""
    if not isinstance(text, str):
        return text

    # Replace non-breaking spaces
    text = text.replace('\xa0', ' ')

    special_chars = {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}',
        '\u201c': '``',
        '\u201d': "''",
        '\u2018': '`',
        '\u2019': "'",
        '\u2013': '--',
        '\u2014': '---',
    }

    result = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char == '\\':
            if i + 1 < n and text[i + 1] in special_chars:
                result.append('\\')
            else:
                result.append('\\textbackslash{}')
        elif char in special_chars:
            if result and result[-1] == '\\':
                result.append(char)
            else:
                result.append(special_chars[char])
        else:
            result.append(char)
        i += 1

    return "".join(result)


def run_pdflatex(tex_filename: str, pdf_dir: str, label: str = "document", keep_tex: bool = False) -> bool:
    """
    Run pdflatex twice in pdf_dir and raise on failure.
    Cleans up auxiliary files afterwards.
    Returns True on success.
    """
    base_name = os.path.splitext(tex_filename)[0]
    try:
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_filename],
                cwd=pdf_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                raise Exception(
                    f"pdflatex exited with code {result.returncode}.\n"
                    f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
                )
        print(f"Successfully compiled {label} via LaTeX.")
        return True
    finally:
        exts = ['.aux', '.log', '.out']
        if not keep_tex:
            exts.append('.tex')
        for ext in exts:
            tmp = os.path.join(pdf_dir, f"{base_name}{ext}")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception as e:
                    print(f"Warning: Could not remove {tmp}: {e}", file=sys.stderr)


def _find_and_register_font_family(
    family_name: str,
    font_names: Tuple[str, str, str, str],
    fallback_names: Tuple[str, str, str, str],
    cache_var: list
) -> Tuple[str, str, str, str]:
    """
    Helper function to find font files in system directories and register them with ReportLab.
    
    Args:
        family_name: Name of the font family to register
        font_names: Tuple of (regular, bold, italic, bold_italic) font filenames
        fallback_names: Tuple of fallback font names if fonts not found
        cache_var: List containing the cached registration result (mutable for closure)
    
    Returns:
        Tuple of (regular, bold, italic, bold_italic) registered font names
    """
    if cache_var[0] is not None:
        return cache_var[0]

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Search in local font directories only (not system-wide)
        # Can be overridden via YAML_CV_FONT_DIRS environment variable (colon-separated)
        font_dirs_env = os.environ.get("YAML_CV_FONT_DIRS", "")
        if font_dirs_env:
            dirs = font_dirs_env.split(os.pathsep)
        else:
            # Default to local directories relative to project
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
            user_fonts = os.path.join(local_appdata, "Microsoft", "Windows", "Fonts") if local_appdata else ""
            dirs = [
                os.path.join(script_dir, "fonts"),
                os.path.join(script_dir, "okf", "fonts"),
            ]
            if win_fonts and os.path.exists(win_fonts):
                dirs.append(win_fonts)
            if user_fonts and os.path.exists(user_fonts):
                dirs.append(user_fonts)
        
        regular_file, bold_file, italic_file, bold_italic_file = font_names

        regular_path = None
        bold_path = None
        italic_path = None
        bold_italic_path = None

        for d in dirs:
            if not d or not os.path.exists(d):
                continue
            r_p = os.path.join(d, regular_file)
            b_p = os.path.join(d, bold_file)
            i_p = os.path.join(d, italic_file)
            bi_p = os.path.join(d, bold_italic_file)
            
            if os.path.exists(r_p) and os.path.exists(b_p):
                regular_path = r_p
                bold_path = b_p
                if os.path.exists(i_p):
                    italic_path = i_p
                if os.path.exists(bi_p):
                    bold_italic_path = bi_p
                break

        if not regular_path or not bold_path:
            cache_var[0] = fallback_names
            return fallback_names

        pdfmetrics.registerFont(TTFont(f"{family_name}", regular_path))
        pdfmetrics.registerFont(TTFont(f"{family_name}-Bold", bold_path))
        pdfmetrics.registerFont(TTFont(f"{family_name}-Italic", italic_path if italic_path else regular_path))
        pdfmetrics.registerFont(TTFont(f"{family_name}-BoldItalic", bold_italic_path if bold_italic_path else bold_path))
        
        pdfmetrics.registerFontFamily(
            family_name,
            normal=family_name,
            bold=f"{family_name}-Bold",
            italic=f"{family_name}-Italic",
            boldItalic=f"{family_name}-BoldItalic",
        )
        registered_names = (family_name, f"{family_name}-Bold", f"{family_name}-Italic", f"{family_name}-BoldItalic")
        cache_var[0] = registered_names
        return registered_names
    except Exception as e:
        print(f"Warning: Could not register {family_name}: {e}", file=sys.stderr)
        cache_var[0] = fallback_names
        return fallback_names


_GOOGLE_SANS_CODE_REGISTERED = [None]

def register_google_sans_code() -> Tuple[str, str, str, str]:
    """
    Registers Google Sans Code TTF fonts with ReportLab.
    Looks in local font directories (project/fonts, okf/fonts) or YAML_CV_FONT_DIRS env var.
    Returns (F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC) representing the registered font names,
    or falls back to ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique') if not found.
    """
    return _find_and_register_font_family(
        family_name="GoogleSansCode",
        font_names=("GoogleSansCode-Regular.ttf", "GoogleSansCode-Bold.ttf", "GoogleSansCode-Italic.ttf", "GoogleSansCode-BoldItalic.ttf"),
        fallback_names=("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
        cache_var=_GOOGLE_SANS_CODE_REGISTERED
    )


_LM_ROMAN_10_REGISTERED = [None]

def register_lm_roman_10() -> Tuple[str, str, str, str]:
    """
    Registers LM Roman 10 TTF fonts with ReportLab.
    Looks in local font directories (project/fonts, okf/fonts) or YAML_CV_FONT_DIRS env var.
    Returns (F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC) representing the registered font names,
    or falls back to ('Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic') if not found.
    """
    return _find_and_register_font_family(
        family_name="LMRoman10",
        font_names=("lmroman10-regular.ttf", "lmroman10-bold.ttf", "lmroman10-italic.ttf", "lmroman10-bolditalic.ttf"),
        fallback_names=("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
        cache_var=_LM_ROMAN_10_REGISTERED
    )


_CMU_CONCRETE_REGISTERED = [None]

def register_cmu_concrete() -> Tuple[str, str, str, str]:
    """
    Registers CMU Concrete TTF fonts with ReportLab.
    Returns (F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC) or falls back to
    ('Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic') if not found.
    """
    return _find_and_register_font_family(
        family_name="CMUConcrete",
        font_names=("cmunorm.ttf", "cmunobx.ttf", "cmunoti.ttf", "cmunobi.ttf"),
        fallback_names=("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
        cache_var=_CMU_CONCRETE_REGISTERED
    )


_CALIBRI_REGISTERED = [None]

def register_calibri() -> Tuple[str, str, str, str]:
    """
    Registers Calibri TTF fonts with ReportLab (standard Windows system font).
    Returns (F_REG, F_BOLD, F_ITALIC, F_BOLDITALIC) or falls back to
    ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique') if not found.
    """
    return _find_and_register_font_family(
        family_name="Calibri",
        font_names=("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
        fallback_names=("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
        cache_var=_CALIBRI_REGISTERED
    )


def format_address(address, latex: bool = False) -> str:
    """
    Format address for output (LaTeX or HTML/ReportLab).
    
    Args:
        address: Address as string or list of strings
        latex: If True, format for LaTeX (with \\\\). If False, format for HTML (with <br/>)
    
    Returns:
        Formatted address string
    """
    from typing import Union, List
    
    if isinstance(address, list):
        if latex:
            return " \\\\\n  ".join([escape_latex(line) for line in address])
        else:
            return "<br/>".join(address)
    else:
        if latex:
            return " \\\\\n  ".join([escape_latex(line) for line in address.split("\n")])
        else:
            return address.replace("\n", "<br/>")
