"""Parser Agent tools: plain Python functions that read a resume's text.

Rule: only read what the resume actually says. Missing fields are reported as
missing (empty list / NOT_STATED / level 0), never guessed.
Protected details such as age, gender or marital status are never extracted.
"""
import re

from hireflow import config

SKILL_ALIASES = {
    "rest": "rest apis",
    "rest api": "rest apis",
    "restful api": "rest apis",
    "restful apis": "rest apis",
    "postgres": "sql",
    "postgresql": "sql",
    "mysql": "sql",
    "amazon web services": "aws",
    "python3": "python",
    "js": "javascript",
    "nodejs": "node.js",
    "node": "node.js",
}

_EDU_TOKENS = [
    (4, {"phd", "doctorate"}),
    (3, {"mtech", "me", "msc", "mca", "mba", "ms", "master", "masters"}),
    (2, {"btech", "be", "bsc", "bca", "bcom", "bs", "ba", "bachelor", "bachelors"}),
    (1, {"diploma"}),
]


def normalize_skill(skill: str) -> str:
    """Lower-case a skill name and map common aliases to one canonical form."""
    key = re.sub(r"\s+", " ", skill.strip().lower())
    return SKILL_ALIASES.get(key, key)


def _field(text: str, label: str):
    aliases = {
        "name": r"name|candidate name|full name",
        "skills": r"skills|technical skills|core skills|key skills|competencies|technical expertise",
        "experience": r"experience|work experience|total experience|professional experience",
        "education": r"education|educational qualification|academic background|qualification",
    }
    pattern = aliases.get(label.lower(), re.escape(label))
    match = re.search(rf"^[ \t]*(?:{pattern})[ \t]*[:：-][ \t]*(.+?)[ \t]*$", text, re.I | re.M)
    if match:
        return match.group(1).strip()
    if label.lower() == "skills":
        section = re.search(r"(?ims)^\s*(?:technical skills|skills|core skills|key skills|competencies)\s*:?\s*\n(.*?)(?=^\s*(?:education|experience|projects|certifications|work history|achievements)\b|\Z)", text)
        if section:
            return re.sub(r"\s+", " ", section.group(1)).strip(" \n:,-")
    return None


def extract_name(text: str) -> str:
    """Return the candidate's name from the 'Name:' line, or 'Unknown'."""
    name = _field(text, "name")
    if name:
        return name
    for line in text.splitlines():
        candidate = line.strip().strip("|•- ")
        if candidate and len(candidate) < 70 and not re.search(r"@|https?://|resume|curriculum vitae|\b(phone|email|linkedin)\b", candidate, re.I) and not re.search(r"\d{3}", candidate):
            if len(candidate.split()) <= 5 and not candidate.endswith(":"):
                return candidate
    return "Unknown"


def extract_skills(text: str) -> list[str]:
    """Return normalized skills listed in the Skills section. Empty list if there is none (never inferred from prose)."""
    raw = _field(text, "skills")
    if not raw:
        return []   # no Skills section: nothing is guessed from summary or project prose
    seen, skills = set(), []
    for part in re.split(r"[,;|]", raw):
        skill = normalize_skill(part)
        if skill and skill not in seen:
            seen.add(skill)
            skills.append(skill)
    return skills


def extract_experience_years(text: str) -> float:
    """Return years of experience from the 'Experience:' line. Returns -1 if it is not stated."""
    raw = _field(text, "experience")
    if raw is None:
        raw = re.search(r"(?i)(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?experience", text)
        raw = raw.group(0) if raw else None
    if raw is None:
        return config.NOT_STATED
    if re.search(r"fresher|no experience|none|nil", raw, re.I):
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)", raw)
    return float(match.group(1)) if match else config.NOT_STATED


def extract_education(text: str) -> dict:
    """Return the stated qualification and its normalized level (0 = not stated)."""
    raw = _field(text, "education")
    if not raw:
        return {"label": "not stated", "level": 0}
    normalized = re.sub(r"[^a-z]", "", raw.lower())
    tokens = set(re.findall(r"[a-z]+", raw.lower()))
    level = 0
    for lvl, names in _EDU_TOKENS:
        if tokens & names:
            level = max(level, lvl)
    if re.search(r"phd|doctorate", normalized):
        level = 4
    elif any(term in normalized for term in ("mtech", "mba", "mca", "msc", "master")) or re.search(r"^\s*m[.\s-]*e(?:[.\s]|$)", raw.lower()):
        level = max(level, 3)
    elif any(term in normalized for term in ("btech", "bachelor", "bsc", "bca", "bcom")) or re.search(r"^\s*b[.\s-]*e(?:[.\s]|$)", raw.lower()):
        level = max(level, 2)
    elif "diploma" in normalized:
        level = max(level, 1)
    return {"label": raw, "level": level}
