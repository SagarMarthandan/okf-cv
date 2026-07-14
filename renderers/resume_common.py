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
