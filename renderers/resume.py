"""
Resume renderer — dispatcher.

Routes to the LaTeX renderer or the ReportFallback (ReportLab + Calibri)
renderer based on the `render_mode` key in the YAML data.

  render_mode: latex          → renderers/resume_latex.py
  render_mode: reportfallback → renderers/resume_reportfallback.py
  (missing / unknown)         → latex (primary, with automatic fallback)

Backward compatible: callers that imported `create_resume_pdf` from this
module continue to work. The shared language helpers (`HEADERS`,
`get_resume_language`) are re-exported from resume_common for legacy imports.
"""
from .resume_common import HEADERS, get_resume_language
from .resume_latex import create_resume_pdf_latex
from .resume_reportfallback import create_resume_pdf_reportlab

# Backward-compatible alias used by the LaTeX renderer's audit fallback path.
create_resume_pdf_reportlab = create_resume_pdf_reportlab


def _resolve_render_mode(data) -> str:
    mode = str(data.get('render_mode', '')).lower().strip()
    if mode in ('latex', 'reportfallback', 'report', 'reportlab'):
        if mode in ('report', 'reportlab'):
            return 'reportfallback'
        return mode
    return 'latex'


def create_resume_pdf(data, output_path):
    mode = _resolve_render_mode(data)
    if mode == 'reportfallback':
        print(f"Render mode: reportfallback (ReportLab + Calibri)")
        create_resume_pdf_reportlab(data, output_path)
    else:
        print(f"Render mode: latex")
        create_resume_pdf_latex(data, output_path)
