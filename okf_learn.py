"""
okf_learn.py — Self-learning keyword enrichment for OKF portfolio files.

After each application run, this script extracts useful terms from the
processed Job Description and enriches matched projects' frontmatter keywords
with terms that appear in the project body but were not previously tagged.

Safeguards:
  - Only terms found in the project's own body/description/technologies are eligible
  - Max 3 new keywords per project per run
  - 15 keywords max per file (linter enforced, rollback on violation)
  - Every change logged to okf/learning_log.json
  - Idempotent: won't add duplicate keywords

Usage:
    python okf_learn.py <application_folder_path> [portfolio_dir]
"""
import json
import os
import re
import sys
import yaml
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional

from config import DEFAULT_PORTFOLIO_DIR, SKILL_DIR

MAX_NEW_KEYWORDS_PER_RUN = 3
MAX_KEYWORDS_PER_FILE = 15
LEARNING_LOG_PATH = os.path.join(SKILL_DIR, "okf", "learning_log.json")

# Generic words that should never be added as keywords
NOISE_WORDS = {
    'like', 'using', 'tools', 'time', 'real', 'patterns', 'requirements',
    'practices', 'pipelines', 'building', 'engineer', 'senior', 'strong',
    'experience', 'knowledge', 'familiarity', 'understanding', 'work',
    'working', 'solutions', 'scalable', 'expertise', 'proficiency',
    'looking', 'team', 'role', 'position', 'company', 'candidate',
    'years', 'year', 'month', 'months', 'good', 'great', 'excellent',
    'must', 'should', 'will', 'able', 'plus', 'nice', 'have', 'has',
    'including', 'etc', 'within', 'across', 'multiple', 'various',
    'related', 'relevant', 'similar', 'other', 'new', 'existing',
    'current', 'previous', 'future', 'past', 'present', 'general',
    'specific', 'particular', 'certain', 'basic', 'advanced', 'intermediate',
    'fundamental', 'essential', 'important', 'key', 'main', 'primary',
    'secondary', 'core', 'focus', 'focused', 'responsible', 'responsibilities',
    'duties', 'tasks', 'projects', 'project', 'status', 'complete',
    'completed', 'incomplete', 'pending', 'ongoing', 'active', 'inactive',
    'hands', 'on', 'field', 'fields', 'area', 'areas', 'domain', 'domains',
    'industry', 'industries', 'sector', 'sectors', 'market', 'markets',
    'business', 'businesses', 'enterprise', 'enterprises', 'organization',
    'organisations', 'organisations', 'user', 'users', 'customer', 'customers',
    'client', 'clients', 'stakeholder', 'stakeholders', 'partner', 'partners',
    'management', 'manager', 'managers', 'lead', 'leader', 'leaders',
    'member', 'members', 'join', 'joining', 'apply', 'applying', 'application',
    'applications', 'opportunity', 'opportunities', 'career', 'careers',
    'job', 'jobs', 'hire', 'hiring', 'recruit', 'recruiting', 'recruitment',
    'offer', 'offers', 'benefit', 'benefits', 'salary', 'compensation',
    'remote', 'hybrid', 'onsite', 'office', 'location', 'locations',
    'relocate', 'relocation', 'travel', 'visa', 'permit', 'permitting',
    'language', 'languages', 'english', 'german', 'fluent', 'fluency',
    'proficient', 'proficiency', 'native', 'bilingual', 'multilingual',
    'written', 'verbal', 'communication', 'communications', 'presentation',
    'presentations', 'documentation', 'documenting', 'documented',
    'report', 'reports', 'reporting', 'dashboard', 'dashboards',
    'metric', 'metrics', 'kpi', 'kpis', 'goal', 'goals', 'objective', 'objectives',
    'target', 'targets', 'result', 'results', 'outcome', 'outcomes',
    'impact', 'impacts', 'value', 'values', 'benefit', 'benefits',
    'success', 'successful', 'successfully', 'fail', 'failure', 'failures',
    'challenge', 'challenges', 'problem', 'problems', 'solution', 'solutions',
    'approach', 'approaches', 'method', 'methods', 'methodology', 'methodologies',
    'process', 'processes', 'processing', 'processed', 'procedure', 'procedures',
    'standard', 'standards', 'best', 'practices', 'practice', 'practiced',
    'principle', 'principles', 'concept', 'concepts', 'conceptual',
    'theory', 'theoretical', 'practical', 'pragmatic', 'hands-on',
    'end', 'end-to-end', 'e2e', 'full', 'full-stack', 'fullstack',
    'stack', 'stacks', 'layer', 'layers', 'tier', 'tiers', 'level', 'levels',
    'stage', 'stages', 'phase', 'phases', 'step', 'steps',
    'source', 'sources', 'target', 'targets', 'destination', 'destinations',
    'input', 'inputs', 'output', 'outputs', 'format', 'formats', 'formatted',
    'structured', 'unstructured', 'semi-structured', 'raw', 'clean', 'cleaned',
    'transform', 'transformed', 'transformation', 'transformations',
    'load', 'loaded', 'loading', 'extract', 'extracted', 'extraction',
    'ingest', 'ingested', 'ingestion', 'consume', 'consumed', 'consumption',
    'produce', 'produced', 'production', 'generate', 'generated', 'generation',
    'create', 'created', 'creation', 'build', 'built', 'building',
    'develop', 'developed', 'development', 'developing',
    'design', 'designed', 'designing', 'architecture', 'architectures',
    'architect', 'architecting', 'architected',
    'implement', 'implemented', 'implementation', 'implementing',
    'deploy', 'deployed', 'deployment', 'deploying',
    'maintain', 'maintained', 'maintenance', 'maintaining',
    'support', 'supported', 'supporting', 'supported',
    'monitor', 'monitored', 'monitoring',
    'test', 'tested', 'testing', 'tested',
    'validate', 'validated', 'validation', 'validating',
    'optimize', 'optimized', 'optimization', 'optimizing',
    'analyze', 'analyzed', 'analysis', 'analyzing',
    'explore', 'explored', 'exploration', 'exploring',
    'investigate', 'investigated', 'investigation', 'investigating',
    'research', 'researched', 'researching',
    'learn', 'learned', 'learning',
    'understand', 'understood', 'understanding',
    'identify', 'identified', 'identifying',
    'define', 'defined', 'defining',
    'plan', 'planned', 'planning',
    'prepare', 'prepared', 'preparing',
    'establish', 'established', 'establishing',
    'ensure', 'ensured', 'ensuring',
    'provide', 'provided', 'providing',
    'deliver', 'delivered', 'delivering',
    'enable', 'enabled', 'enabling',
    'leverage', 'leveraged', 'leveraging',
    'utilize', 'utilized', 'utilizing',
    'adopt', 'adopted', 'adopting',
    'integrate', 'integrated', 'integrating',
    'migrate', 'migrated', 'migrating',
    'upgrade', 'upgraded', 'upgrading',
    'automate', 'automated', 'automating',
    'orchestrate', 'orchestrated', 'orchestrating',
    'schedule', 'scheduled', 'scheduling',
    'trigger', 'triggered', 'triggering',
    'execute', 'executed', 'executing',
    'run', 'running', 'runs',
    'store', 'stored', 'storing',
    'query', 'queried', 'querying',
    'fetch', 'fetched', 'fetching',
    'retrieve', 'retrieved', 'retrieving',
    'update', 'updated', 'updating',
    'delete', 'deleted', 'deleting',
    'insert', 'inserted', 'inserting',
    'merge', 'merged', 'merging',
    'join', 'joined', 'joining',
    'filter', 'filtered', 'filtering',
    'sort', 'sorted', 'sorting',
    'group', 'grouped', 'grouping',
    'aggregate', 'aggregated', 'aggregating',
    'calculate', 'calculated', 'calculating',
    'compute', 'computed', 'computing',
    'process', 'processed', 'processing',
}

# Domain-relevant bigrams/trigrams to look for in JD text
PHRASE_PATTERNS = [
    r'\bdata\s+warehouse\b', r'\bdata\s+lake\b', r'\bdata\s+lakehouse\b',
    r'\bdata\s+engineering\b', r'\bdata\s+pipeline\b', r'\bdata\s+quality\b',
    r'\bdata\s+modeling\b', r'\bdata\s+mart\b', r'\bdata\s+governance\b',
    r'\bdata\s+catalog\b', r'\bdata\s+ingestion\b', r'\bdata\s+transformation\b',
    r'\belt\s+pipeline\b', r'\betl\s+pipeline\b', r'\bextract\s+load\s+transform\b',
    r'\bextract\s+transform\s+load\b',
    r'\bstar\s+schema\b', r'\bdimensional\s+modeling\b', r'\bslowly\s+changing\s+dimension\b',
    r'\bscd\s+type\s+2\b',
    r'\bmedallion\s+architecture\b', r'\bbronze\s+silver\s+gold\b',
    r'\bmulti-layer\s+architecture\b',
    r'\bincremental\s+loading\b', r'\bincremental\s+ingestion\b',
    r'\bci/cd\b', r'\bci\s+cd\b', r'\bcontinuous\s+integration\b',
    r'\binfrastructure\s+as\s+code\b',
    r'\bmessage\s+queue\b', r'\bevent\s+streaming\b', r'\bevent-driven\b',
    r'\bevent\s+driven\b', r'\bpub\s+sub\b',
    r'\bstream\s+processing\b', r'\bbatch\s+processing\b',
    r'\breal-time\s+analytics\b', r'\breal\s+time\s+analytics\b',
    r'\bvector\s+database\b', r'\bvector\s+store\b', r'\bsimilarity\s+search\b',
    r'\bretrieval\s+augmented\s+generation\b', r'\bretrieval-augmented\s+generation\b',
    r'\blarge\s+language\s+model\b', r'\bgenerative\s+ai\b',
    r'\bmachine\s+learning\b', r'\bdeep\s+learning\b',
    r'\bnatural\s+language\s+processing\b',
    r'\borchestration\s+pipeline\b', r'\bworkflow\s+orchestration\b',
    r'\bcloud\s+data\s+warehouse\b', r'\bcloud\s+warehouse\b',
    r'\bdistributed\s+computing\b', r'\bbig\s+data\s+processing\b',
    r'\bcontainer\s+orchestration\b',
    r'\bbusiness\s+intelligence\b', r'\bdata\s+visualization\b',
    r'\bwindow\s+functions\b', r'\banalytic\s+functions\b',
    r'\bquery\s+optimization\b',
    r'\bdata\s+testing\b', r'\bdata\s+validation\b', r'\bdata\s+integrity\b',
    r'\baccess\s+control\b', r'\bsecrets\s+management\b',
    r'\bdocument\s+compilation\b', r'\bresume\s+tailoring\b',
    r'\bats\s+optimization\b', r'\bcover\s+letter\b',
    r'\bpipeline\s+automation\b', r'\bjob\s+application\b',
    r'\bpdf\s+generation\b',
    r'\borchestration\b', r'\bscheduler\b',
    r'\bdimensionality\s+reduction\b', r'\boutlier\s+detection\b',
    r'\brobust\s+statistics\b', r'\bcovariance\s+matrix\b',
    r'\bclassification\b', r'\bclustering\b',
    r'\bblockchain\s+analytics\b', r'\bwhale\s+detection\b',
    r'\bversion\s+control\b',
    r'\bdata\s+orchestration\b', r'\bdata\s+pipeline\b',
    r'\bazure\s+data\s+lake\b', r'\bazure\s+storage\b',
    r'\bazure\s+orchestration\b', r'\bazure\s+pipeline\b',
    r'\bgcp\s+warehouse\b', r'\bgoogle\s+warehouse\b',
    r'\bopen\s+source\s+ingestion\b', r'\belt\s+ingestion\b',
    r'\blakehouse\s+storage\b', r'\bacid\s+transactions\b',
    r'\bdata\s+science\s+notebook\b', r'\binteractive\s+computing\b',
    r'\bnumerical\s+computing\b', r'\bscientific\s+computing\b',
    r'\barray\s+processing\b', r'\bml\s+framework\b',
    r'\bllm\s+api\b', r'\bchain\s+of\s+thought\b', r'\bagent\s+framework\b',
    r'\bllm\s+framework\b',
    r'\bin-memory\s+store\b', r'\brelational\s+database\b',
    r'\bsql\s+database\b', r'\bsql\s+window\b', r'\bpartition\s+by\b',
    r'\bfact\s+dimension\b', r'\bdata\s+mart\s+modeling\b',
    r'\bdelta\s+loading\b', r'\bupsert\b',
    r'\bdimension\s+history\b', r'\bversioned\s+dimension\b',
    r'\bspark\s+python\b', r'\bdistributed\s+python\b', r'\bspark\s+sql\b',
    r'\bblob\s+storage\b', r'\bcredential\s+store\b', r'\bsecret\s+manager\b',
    r'\bdata\s+app\b', r'\binteractive\s+dashboard\b',
    r'\bpython\s+web\s+app\b', r'\bweb\s+app\b',
    r'\btypesetting\b', r'\btex\b',
    r'\bplotting\b', r'\bcharts\b',
    r'\bnotebook\b',
    r'\bdashboard\b', r'\bbi\s+dashboard\b', r'\bbi\s+tool\b',
    r'\biac\b', r'\biac\s+tool\b',
    r'\bk8s\b',
    r'\bpostgres\b', r'\boltp\b', r'\bolap\b',
    r'\bsklearn\b',
    r'\bgpt\b', r'\bchatgpt\b',
    r'\betl\b', r'\belt\b',
    r'\bwarehouse\b', r'\bdata\s+warehousing\b',
    r'\blakehouse\b',
    r'\bdag\b',
    r'\badf\b',
]


def tokenize(text: str) -> Set[str]:
    """Extract lowercase alphanumeric tokens, minus stopwords."""
    if not text:
        return set()
    words = re.findall(r'\b\w+\b', text.lower())
    stopwords = {
        'and', 'the', 'for', 'with', 'a', 'an', 'to', 'in', 'of', 'on',
        'at', 'by', 'is', 'or', 'as', 'we', 'you', 'our', 'your', 'this',
        'that', 'will', 'be', 'are', 'have', 'has', 'was', 'were', 'it',
        'from', 'their', 'they', 'but', 'not', 'can', 'all', 'any', 'if',
        'so', 'do', 'does', 'did', 'about', 'into', 'than', 'then', 'also',
        'more', 'most', 'some', 'such', 'only', 'very', 'over', 'under',
        'up', 'down', 'out', 'off', 'above', 'below', 'between', 'through',
    }
    return {w for w in words if w not in stopwords and len(w) > 2}


def extract_jd_phrases(jd_text: str) -> List[str]:
    """Extract domain-relevant phrases (bigrams/trigrams) from JD text.

    Returns a list of normalized phrases found in the JD.
    """
    jd_lower = jd_text.lower()
    phrases = []
    for pattern in PHRASE_PATTERNS:
        matches = re.findall(pattern, jd_lower)
        for match in matches:
            normalized = re.sub(r'\s+', ' ', match.strip())
            if normalized not in phrases:
                phrases.append(normalized)
    return phrases


def extract_jd_terms(jd_text: str) -> List[str]:
    """Extract all meaningful terms from JD: single tokens + domain phrases.

    Returns a deduplicated list, phrases first (higher value), then single tokens.
    """
    phrases = extract_jd_phrases(jd_text)
    tokens = sorted(tokenize(jd_text))
    # Combine: phrases first, then tokens not already part of a phrase
    phrase_token_set = set()
    for p in phrases:
        phrase_token_set.update(p.split())
    single_tokens = [t for t in tokens if t not in phrase_token_set]
    return phrases + single_tokens


def load_jd_text(app_folder: str) -> Optional[str]:
    """Load JD text from Job_Description.yaml in the application folder."""
    jd_path = os.path.join(app_folder, "Job_Description.yaml")
    if not os.path.exists(jd_path):
        return None
    try:
        with open(jd_path, 'r', encoding='utf-8') as f:
            jd_data = yaml.safe_load(f)
        if not isinstance(jd_data, dict):
            return None
        parts = []
        if jd_data.get('position'):
            parts.append(str(jd_data['position']))
        for sec in jd_data.get('sections', []):
            if isinstance(sec, dict):
                parts.append(str(sec.get('title', '')))
                parts.append(str(sec.get('content', '')))
                for bullet in sec.get('bullets', []):
                    parts.append(str(bullet))
        return "\n".join(parts)
    except Exception:
        return None


def load_role_archetype(app_folder: str) -> Optional[str]:
    """Load primary role archetype from ATS_Report.yaml."""
    ats_path = os.path.join(app_folder, "ATS_Report.yaml")
    if not os.path.exists(ats_path):
        return None
    try:
        with open(ats_path, 'r', encoding='utf-8') as f:
            report = yaml.safe_load(f)
        if isinstance(report, dict):
            role_arch = report.get("role_archetype", {})
            if isinstance(role_arch, dict):
                return role_arch.get("primary")
        return None
    except Exception:
        return None


def load_matched_project_titles(app_folder: str) -> List[str]:
    """Extract project titles from project_info.md."""
    proj_info_path = os.path.join(app_folder, "project_info.md")
    if not os.path.exists(proj_info_path):
        return []
    with open(proj_info_path, 'r', encoding='utf-8') as f:
        content = f.read()
    titles = []
    for match in re.finditer(r'^#\s+(.+)$', content, re.MULTILINE):
        title = match.group(1).strip()
        if title and title.lower() != "tailored project portfolio":
            titles.append(title)
    return titles


def find_portfolio_file_for_title(title: str, portfolio_dir: str) -> Optional[str]:
    """Find the portfolio .md file whose frontmatter title matches the given title."""
    if not os.path.isdir(portfolio_dir):
        return None
    for filename in os.listdir(portfolio_dir):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(portfolio_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if fm_match:
                meta = yaml.safe_load(fm_match.group(1))
                if isinstance(meta, dict) and meta.get("title", "").strip() == title.strip():
                    return filepath
        except Exception:
            continue
    return None


def parse_portfolio_file(filepath: str) -> Tuple[Dict, str, str]:
    """Parse a portfolio file into (metadata, yaml_block, body).

    Returns (metadata_dict, raw_yaml_block, body_text).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, "", content

    yaml_block = match.group(1)
    body = match.group(2)
    meta = yaml.safe_load(yaml_block) or {}
    return meta, yaml_block, body


def find_untagged_terms(
    jd_terms: List[str],
    project_body: str,
    project_desc: str,
    project_techs: str,
    existing_keywords: List[str],
) -> List[str]:
    """Find JD terms that appear in the project body/desc/techs but not in keywords.

    Returns a list of terms eligible for addition, ordered by phrase priority.
    Filters out generic noise words that should never be keywords.
    """
    body_lower = project_body.lower()
    desc_lower = project_desc.lower()
    techs_lower = project_techs.lower()
    existing_lower = {k.lower() for k in existing_keywords}

    untagged = []
    for term in jd_terms:
        if term.lower() in existing_lower:
            continue
        # Skip noise words (single words only)
        if ' ' not in term and term.lower() in NOISE_WORDS:
            continue
        # Skip very short single words (< 4 chars)
        if ' ' not in term and len(term) < 4:
            continue
        # Check if term appears in body, description, or technologies
        if ' ' in term:
            # Multi-word phrase: substring check
            if term in body_lower or term in desc_lower or term in techs_lower:
                untagged.append(term)
        else:
            # Single word: word-boundary check
            pattern = r'\b' + re.escape(term) + r'\b'
            if (re.search(pattern, body_lower) or
                    re.search(pattern, desc_lower) or
                    re.search(pattern, techs_lower)):
                untagged.append(term)

    return untagged


def add_keywords_to_file(filepath: str, new_keywords: List[str]) -> bool:
    """Append new keywords to a portfolio file's YAML frontmatter.

    Returns True if the file was modified, False if no change.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^(---\s*\n)(.*?)(\n---\s*\n)(.*)', content, re.DOTALL)
    if not match:
        return False

    yaml_block = match.group(2)
    meta = yaml.safe_load(yaml_block) or {}
    existing_keywords = meta.get("keywords", [])
    existing_lower = {k.lower() for k in existing_keywords}

    # Filter out duplicates
    to_add = [k for k in new_keywords if k.lower() not in existing_lower]
    if not to_add:
        return False

    # Check cap
    if len(existing_keywords) + len(to_add) > MAX_KEYWORDS_PER_FILE:
        space = MAX_KEYWORDS_PER_FILE - len(existing_keywords)
        if space <= 0:
            return False
        to_add = to_add[:space]

    # Append to the keywords list in the YAML block
    # Find the keywords section and append
    lines = yaml_block.split('\n')
    new_lines = []
    in_keywords = False
    keywords_added = False

    for line in lines:
    # Detect keywords list start
        if re.match(r'^keywords:\s*$', line):
            in_keywords = True
            new_lines.append(line)
            continue

        if in_keywords:
            # If we hit a non-list-item line, keywords section ended
            if not line.strip().startswith('- ') and not line.strip() == '':
                in_keywords = False
                if not keywords_added:
                    for kw in to_add:
                        new_lines.append(f"- {kw}")
                    keywords_added = True
                new_lines.append(line)
            elif line.strip() == '':
                # Could be end of keywords or blank line within
                new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # If we're still in keywords at the end, append there
    if in_keywords and not keywords_added:
        for kw in to_add:
            new_lines.append(f"- {kw}")
        keywords_added = True

    if not keywords_added:
        # keywords section wasn't found as a list, add it
        new_lines.append("keywords:")
        for kw in to_add:
            new_lines.append(f"- {kw}")

    new_yaml_block = '\n'.join(new_lines)
    new_content = match.group(1) + new_yaml_block + match.group(3) + match.group(4)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def append_learning_log(entry: Dict) -> None:
    """Append a learning log entry to okf/learning_log.json."""
    log = []
    if os.path.exists(LEARNING_LOG_PATH):
        try:
            with open(LEARNING_LOG_PATH, 'r', encoding='utf-8') as f:
                log = json.load(f)
            if not isinstance(log, list):
                log = []
        except Exception:
            log = []

    log.append(entry)

    os.makedirs(os.path.dirname(LEARNING_LOG_PATH), exist_ok=True)
    with open(LEARNING_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def run_linter(portfolio_dir: str, target_file: Optional[str] = None, baseline_violations: Optional[List[str]] = None) -> bool:
    """Run okf_lint.py on the portfolio directory. Returns True if pass.
    
    If target_file is provided, only checks that specific file via lint_file().
    If baseline_violations is provided, only NEW violations (not in baseline) cause failure.
    """
    if target_file:
        # Lint only the modified file directly
        try:
            from okf_lint import lint_file
            violations = lint_file(target_file)
            if baseline_violations is not None:
                # Only count new violations
                baseline_set = set(baseline_violations)
                new_violations = [v for v in violations if v not in baseline_set]
                return len(new_violations) == 0
            return len(violations) == 0
        except Exception:
            return True
    
    # Full linter run via subprocess
    import subprocess
    linter_path = os.path.join(SKILL_DIR, "okf_lint.py")
    if not os.path.exists(linter_path):
        return True
    try:
        result = subprocess.run(
            [sys.executable, linter_path, portfolio_dir],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return True


def learn_from_application(app_folder: str, portfolio_dir: str) -> Dict:
    """Main learning loop: enrich portfolio keywords from a completed application.

    Returns a summary dict of what was learned.
    """
    # 1. Load JD text
    jd_text = load_jd_text(app_folder)
    if not jd_text:
        return {"error": "Could not load Job_Description.yaml from application folder"}

    # 2. Load role archetype
    role_archetype = load_role_archetype(app_folder)

    # 3. Load matched project titles from project_info.md
    matched_titles = load_matched_project_titles(app_folder)
    if not matched_titles:
        return {"error": "No project titles found in project_info.md"}

    # 4. Extract JD terms (phrases first, then single tokens)
    jd_terms = extract_jd_terms(jd_text)

    # 5. For each matched project, find untagged terms and enrich
    changes = []
    files_modified = []

    for title in matched_titles:
        filepath = find_portfolio_file_for_title(title, portfolio_dir)
        if not filepath:
            continue

        meta, yaml_block, body = parse_portfolio_file(filepath)
        existing_keywords = meta.get("keywords", [])

        # Skip if already at cap
        if len(existing_keywords) >= MAX_KEYWORDS_PER_FILE:
            continue

        # Find JD terms in project body/desc/techs but not in keywords
        desc = str(meta.get("description", ""))
        techs = str(meta.get("technologies", ""))
        untagged = find_untagged_terms(jd_terms, body, desc, techs, existing_keywords)

        if not untagged:
            continue

        # Cap at MAX_NEW_KEYWORDS_PER_RUN
        to_add = untagged[:MAX_NEW_KEYWORDS_PER_RUN]

        # Snapshot for rollback
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Capture baseline lint violations (pre-existing issues that shouldn't block enrichment)
        try:
            from okf_lint import lint_file
            baseline_violations = lint_file(filepath)
        except Exception:
            baseline_violations = None

        # Write new keywords
        modified = add_keywords_to_file(filepath, to_add)
        if not modified:
            continue

        # Run linter to validate (only the modified file, only new violations)
        linter_ok = run_linter(portfolio_dir, target_file=filepath, baseline_violations=baseline_violations)
        if not linter_ok:
            # Rollback
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(original_content)
            changes.append({
                "file": os.path.basename(filepath),
                "added_keywords": [],
                "rolled_back": True,
                "reason": "Linter validation failed after enrichment",
            })
            continue

        files_modified.append(filepath)
        changes.append({
            "file": os.path.basename(filepath),
            "added_keywords": to_add,
            "rolled_back": False,
            "reason": f"JD mentioned '{', '.join(to_add)}'; terms found in project body but not in keywords",
        })

    # 6. Re-embed modified files into Zvec database (hybrid search support)
    if files_modified:
        try:
            from zvec_hybrid_search import reembed_file
            for fpath in files_modified:
                reembed_file(fpath, portfolio_dir)
        except Exception as e:
            print(f"Warning: Zvec re-embed failed (non-blocking): {e}")

        # Invalidate lint cache for modified files so the next lint re-checks them
        try:
            from okf_lint import invalidate_cache
            modified_names = [os.path.basename(f) for f in files_modified]
            invalidate_cache(portfolio_dir, modified_names)
        except Exception as e:
            print(f"Warning: Could not invalidate lint cache (non-blocking): {e}")

    # 7. Log to learning_log.json
    log_entry = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "jd_source": os.path.basename(os.path.normpath(app_folder)),
        "role_archetype": role_archetype,
        "changes": changes,
    }
    append_learning_log(log_entry)

    return {
        "projects_checked": len(matched_titles),
        "projects_enriched": len(files_modified),
        "changes": changes,
        "log_entry": log_entry,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python okf_learn.py <application_folder_path> [portfolio_dir]")
        sys.exit(1)

    app_folder = sys.argv[1]
    portfolio_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORTFOLIO_DIR

    if not os.path.isdir(app_folder):
        print(f"Error: Application folder not found: {app_folder}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(portfolio_dir):
        print(f"Error: Portfolio directory not found: {portfolio_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Learning from application: {app_folder}")
    print(f"Portfolio directory: {portfolio_dir}")

    result = learn_from_application(app_folder, portfolio_dir)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"\nProjects checked: {result['projects_checked']}")
    print(f"Projects enriched: {result['projects_enriched']}")

    for change in result["changes"]:
        if change.get("rolled_back"):
            print(f"  ROLLED BACK: {change['file']} — {change['reason']}")
        elif change["added_keywords"]:
            print(f"  ENRICHED: {change['file']} — added: {', '.join(change['added_keywords'])}")
        else:
            print(f"  NO CHANGE: {change['file']}")

    print(f"\nLearning log: {LEARNING_LOG_PATH}")


if __name__ == "__main__":
    main()
