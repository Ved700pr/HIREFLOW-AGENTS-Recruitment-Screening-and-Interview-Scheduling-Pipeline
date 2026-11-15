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
    match = re.search(rf"^[ \t]*{label}[ \t]*:[ \t]*(.+?)[ \t]*$", text, re.I | re.M)
    return match.group(1) if match else None


def extract_name(text: str) -> str:
    """Return the candidate's name from the 'Name:' line, or 'Unknown'."""
    return _field(text, "name") or "Unknown"


def extract_skills(text: str) -> list[str]:
    """Return normalized skills listed on the 'Skills:' line. Empty list if there is no such line."""
    raw = _field(text, "skills")
    if not raw:
        return []
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
        return config.NOT_STATED
    if re.search(r"fresher|no experience|none|nil", raw, re.I):
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)", raw)
    return float(match.group(1)) if match else config.NOT_STATED


def extract_education(text: str) -> dict:
    """Return {'label': original text, 'level': 0-4} from the 'Education:' line (level 0 = not stated)."""
    raw = _field(text, "education")
    if not raw:
        return {"label": "not stated", "level": 0}
    tokens = set(re.findall(r"[a-z]+", raw.lower().replace(".", "")))
    level = 0
    for lvl, names in _EDU_TOKENS:
        if tokens & names:
            level = max(level, lvl)
    return {"label": raw, "level": level}
