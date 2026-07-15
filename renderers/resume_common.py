"""
Shared helpers for the resume renderers (LaTeX and ReportFallback).

Keeps language detection and section headers in one place so both renderers
stay in sync.
"""

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
