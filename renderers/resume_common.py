"""
Shared helpers for the resume renderers (LaTeX and ReportFallback).

Keeps language detection and section headers in one place so both renderers
stay in sync.
"""
import re

MONTH_MAP = {
    'jan': '01', 'january': '01',
    'feb': '02', 'february': '02',
    'mar': '03', 'march': '03',
    'apr': '04', 'april': '04',
    'may': '05',
    'jun': '06', 'june': '06',
    'jul': '07', 'july': '07',
    'aug': '08', 'august': '08',
    'sep': '09', 'september': '09',
    'oct': '10', 'october': '10',
    'nov': '11', 'november': '11',
    'dec': '12', 'december': '12',
    'januar': '01', 'februar': '02', 'märz': '03', 'maerz': '03',
    'mai': '05', 'juni': '06', 'juli': '07',
    'oktober': '10', 'dezember': '12',
}


def format_date_numeric(date_str):
    """Convert month names in a date string to MM/YYYY numeric format.

    Examples:
      "Jan 2023 – April 2025" → "01/2023 – 04/2025"
      "08/2014 – 12/2018"     → "08/2014 – 12/2018" (already numeric)
      "present"               → "present"
    """
    if not date_str:
        return date_str

    def _replace_month(match):
        word = match.group(0).lower().strip('.,')
        year = match.group(1) if match.lastindex and match.lastindex >= 1 else ''
        # Re-match: the regex captures month word + optional year
        return MONTH_MAP.get(word, word)

    # Match month name (3+ letters) optionally followed by a year
    # Pattern: month word, then optional year (4 digits)
    def _convert(text):
        # Pattern: a month name followed by optional year
        pattern = r'\b([A-Za-zäöü]{3,})\.?\s+(\d{4})\b'
        def replacer(m):
            month_word = m.group(1).lower()
            year = m.group(2)
            numeric = MONTH_MAP.get(month_word)
            if numeric:
                return f"{numeric}/{year}"
            return m.group(0)
        return re.sub(pattern, replacer, text)

    return _convert(str(date_str))

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

# Default order of resume sections, top to bottom. Both renderers read from
# this list so they stay in sync. A resume YAML may override the order by
# supplying a top-level `section_order` key (a list of these section keys);
# any key not present in the data is skipped, and any unknown key is ignored.
DEFAULT_SECTION_ORDER = [
    'summary',
    'technical_skills',
    'projects',
    'professional_experience',
    'education',
    'spoken_languages',
]


def get_section_order(data):
    """Return the section order for a resume.

    Reads `data['section_order']` if present (must be a list of section keys
    from DEFAULT_SECTION_ORDER). Falls back to DEFAULT_SECTION_ORDER.
    Unknown keys are dropped; the result preserves the caller's ordering.
    """
    raw = data.get('section_order')
    if not raw or not isinstance(raw, list):
        return list(DEFAULT_SECTION_ORDER)
    valid = set(DEFAULT_SECTION_ORDER)
    return [k for k in raw if k in valid]


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
