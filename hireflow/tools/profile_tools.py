"""Profile extraction tools used by the Parser Agent.

Everything here is deterministic and evidence-based: a field is only filled when the
resume text says it. Anything absent is returned empty / NOT_STATED so the Matcher can
tell "missing information" apart from "genuinely does not qualify".

Protected attributes (age, gender, marital status, religion, DOB, photo) are never extracted.
"""
from __future__ import annotations

import re
from datetime import date

from hireflow import config

# --------------------------------------------------------------------------- text clean-up
_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "–": "-", "—": "-", "−": "-"}
_BULLETS = "•▪◦●○■□➢➤►▶✓✔·●"


def clean_resume_text(text: str) -> str:
    """Normalise PDF/DOCX artefacts (ligatures, bullets, (cid:x) glyphs, odd spaces) without changing meaning."""
    text = text or ""
    for old, new in _LIGATURES.items():
        text = text.replace(old, new)
    text = re.sub(r"\(cid:\d+\)", " ", text)
    text = text.replace(" ", " ").replace("\t", " ").replace("\r", "\n")
    text = re.sub(rf"^[ ]*[{re.escape(_BULLETS)}*]+[ ]*", "- ", text, flags=re.M)
    text = re.sub(rf"[{re.escape(_BULLETS)}]", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- sections
SECTION_HEADINGS = {
    "summary": {"summary", "professional summary", "career objective", "objective", "profile", "about me", "about"},
    "skills": {"skills", "technical skills", "core skills", "key skills", "competencies", "technical expertise", "skills and tools", "skills & tools", "tech stack", "technologies", "technical proficiencies"},
    "education": {"education", "educational qualification", "educational qualifications", "academic background", "academics", "qualification", "qualifications", "academic qualifications"},
    "experience": {"experience", "work experience", "professional experience", "employment", "employment history", "work history", "total experience", "industry experience"},
    "internships": {"internship", "internships", "internship experience", "training experience"},
    "projects": {"projects", "project", "academic projects", "personal projects", "key projects", "project experience", "selected projects", "technical projects"},
    "certifications": {"certifications", "certification", "certificates", "certificate", "training", "trainings", "courses", "training and certifications", "trainings and certifications", "training & certifications", "trainings & certifications", "certifications and training", "licenses and certifications", "courses and certifications", "professional certifications"},
    "achievements": {"achievements", "achievement", "awards", "honors", "honours", "awards and achievements", "achievements and awards", "awards & achievements", "accomplishments", "extracurricular", "extracurricular activities", "positions of responsibility", "co-curricular activities"},
}
_HEADING_LOOKUP = {name: key for key, names in SECTION_HEADINGS.items() for name in names}


def _heading_key(line: str):
    """Return (section_key, inline_rest) if this line starts a known section, else (None, '')."""
    stripped = line.strip().strip("-:|#*_ ").strip()
    if not stripped or len(stripped) > 70:
        return None, ""
    inline = re.match(r"^\s*([A-Za-z&/ ]{3,45}?)\s*[:：]\s*(.+)$", line.strip())
    if inline:
        key = _HEADING_LOOKUP.get(re.sub(r"\s+", " ", inline.group(1).strip().lower()))
        if key:
            return key, inline.group(2).strip()
    norm = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z&/ ]", " ", stripped).lower()).strip()
    key = _HEADING_LOOKUP.get(norm) or _HEADING_LOOKUP.get(norm.replace(" & ", " and "))
    return (key, "") if key else (None, "")


def split_sections(text: str) -> dict:
    """Split a resume into named sections (summary, skills, education, experience, internships, projects, certifications, achievements, header)."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in clean_resume_text(text).splitlines():
        key, rest = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            if rest:
                sections[current].append(rest)
            continue
        sections.setdefault(current, []).append(line.rstrip())
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


# --------------------------------------------------------------------------- contact
def extract_contact(text: str) -> dict:
    """Extract email, phone, LinkedIn and GitHub exactly as written on the resume ('' if absent)."""
    t = clean_resume_text(text)
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", t)
    phone_text = ""
    for match in re.finditer(r"(?<![\w.])(\+?\d{1,3}[\s-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}(?!\w)", t):
        digits = re.sub(r"\D", "", match.group(0))
        if 10 <= len(digits) <= 13:
            phone_text = match.group(0).strip()
            break
    linkedin = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9\-_%./]+", t, re.I)
    github = re.search(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_.]+", t, re.I)
    return {
        "email": email.group(0).strip(".,") if email else "",
        "phone": phone_text,
        "linkedin": re.sub(r"^https?://(www\.)?", "", linkedin.group(0), flags=re.I).rstrip("/.,") if linkedin else "",
        "github": re.sub(r"^https?://(www\.)?", "", github.group(0), flags=re.I).rstrip("/.,") if github else "",
    }


# --------------------------------------------------------------------------- skills
SKILL_VOCABULARY = [
    "python", "java", "c++", "c#", "c", "javascript", "typescript", "go", "rust", "php", "ruby", "kotlin", "swift", "r", "scala", "bash",
    "sql", "mysql", "postgresql", "sqlite", "mongodb", "redis", "oracle", "firebase", "nosql",
    "html", "css", "scss", "sass", "bootstrap", "tailwind", "react", "angular", "vue", "next.js", "node.js", "express", "django", "flask", "fastapi", "spring", "spring boot",
    "pandas", "numpy", "matplotlib", "scikit-learn", "tensorflow", "pytorch", "keras", "opencv", "machine learning", "deep learning", "nlp", "generative ai", "llm",
    "power bi", "tableau", "excel", "spark", "pyspark", "hadoop", "hive", "airflow", "kafka", "etl",
    "docker", "kubernetes", "git", "github", "gitlab", "jenkins", "ci/cd", "terraform", "ansible", "linux", "aws", "azure", "gcp", "vercel", "bolt.ai", "vercel.ai",
    "rest apis", "graphql", "microservices", "data analysis", "data visualization", "data structures", "algorithms", "oop", "agile", "jira",
]
_VOCAB_SORTED = sorted(set(SKILL_VOCABULARY), key=len, reverse=True)


def _norm_skill(skill: str) -> str:
    from hireflow.tools.parser_tools import normalize_skill

    return normalize_skill(skill.strip(" .:-••*"))


def _find_vocabulary(text: str) -> list[str]:
    """Controlled-vocabulary skills that appear verbatim in the text (never invented)."""
    found, seen = [], set()
    for skill in _VOCAB_SORTED:
        if re.search(rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#])", text, re.I):
            if any(longer.startswith(skill + ".") for longer in found):  # "vercel" inside "vercel.ai"
                continue
            canon = _norm_skill(skill)
            if canon not in seen:
                seen.add(canon)
                found.append(canon)
    return found


def extract_skill_categories(text: str) -> dict:
    """Read the Skills section into {'categories': {label: [skills]}, 'listed': [all listed skills]}. Lines like 'Languages: C++, Python' keep their label."""
    section = split_sections(text).get("skills", "")
    categories: dict[str, list[str]] = {}
    listed: list[str] = []
    if not section:
        return {"categories": {}, "listed": []}
    for raw_line in section.splitlines():
        line = raw_line.strip().lstrip("- ").strip()
        if not line:
            continue
        label, _, rest = line.partition(":")
        if rest and len(label) <= 30:
            category, items = label.strip().title(), rest
        else:
            category, items = "General", line
        for part in re.split(r"[,;|•]|\s{2,}|\s/\s", items):
            skill = _norm_skill(part)
            if skill and len(skill) <= 40 and len(skill.split()) <= 4 and skill not in listed:
                listed.append(skill)
                categories.setdefault(category, []).append(skill)
    return {"categories": categories, "listed": listed}


# --------------------------------------------------------------------------- education
_DEGREES = [
    (4, r"ph\.?\s?d|doctorate"),
    (3, r"m\.?\s?tech|m\.?\s?sc|m\.?\s?ca\b|\bmca\b|\bmba\b|master(?:'?s)?|m\.?\s?e\b(?!\w)|\bms\b|m\.?\s?s\.?\s+in"),
    (2, r"b\.?\s?tech|b\.?\s?e\b(?!\w)|b\.?\s?sc|\bbca\b|b\.?\s?com|bachelor(?:'?s)?|\bbs\b|\bba\b"),
    (1, r"diploma|polytechnic"),
]


def extract_education_details(text: str) -> dict:
    """Return {'degree','university','cgpa','level','label','year'} from the Education section ('' / 0 / None when not stated)."""
    sections = split_sections(text)
    block = sections.get("education", "")
    inline = re.search(r"(?im)^[ \t]*(?:education|educational qualification|qualification)[ \t]*[:：-][ \t]*(.+)$", clean_resume_text(text))
    if not block and inline:
        block = inline.group(1)
    out = {"degree": "", "university": "", "cgpa": None, "level": 0, "label": "not stated", "year": ""}
    if not block:
        return out
    lines = [l.strip().lstrip("- ").strip() for l in block.splitlines() if l.strip()]
    best_level, best_line = 0, ""
    for line in lines:
        for level, pattern in _DEGREES:
            if re.search(pattern, line, re.I) and level > best_level:
                best_level, best_line = level, line
    if best_level:
        out["level"] = best_level
        m = re.search(r"(ph\.?\s?d\.?|doctorate|m\.?\s?tech|m\.?\s?sc|mca|mba|master[^,|\n(]*|b\.?\s?tech|b\.?\s?e\.?|b\.?\s?sc|bca|b\.?\s?com|bachelor[^,|\n(]*|diploma[^,|\n(]*)((?:\s*[-–(]?\s*|\s+in\s+|\s+)(?:cse|computer science[^,|\n(]*|computer applications|information technology|[A-Za-z ]{0,40}))?", best_line, re.I)
        degree = (m.group(0) if m else best_line).strip(" ,.-|")
        degree = re.split(r"\s{2,}|\||,|\(|\d{4}|cgpa|gpa", degree, flags=re.I)[0].strip(" ,.-")
        out["degree"] = degree or best_line
        out["label"] = out["degree"]
    elif lines:
        out["label"] = lines[0]
    for line in lines:
        uni = re.search(r"([A-Z][A-Za-z.&' ]+(?:University|Institute of [A-Za-z ]+|Institute|College|School of [A-Za-z ]+|IIT|NIT|IIIT)[A-Za-z.&' ]*)", line)
        if uni:
            out["university"] = re.sub(r"\s+", " ", uni.group(1)).strip(" ,.-")
            break
    cg = re.search(r"(?:cgpa|gpa|c\.g\.p\.a)\s*[:\-]?\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?", block, re.I)
    if cg:
        out["cgpa"] = float(cg.group(1))
    years = re.findall(r"\b((?:19|20)\d{2})\b", block)
    if years:
        out["year"] = max(years)
    return out


# --------------------------------------------------------------------------- entries (projects / experience / certs)
def _bullet_blocks(section: str) -> list[list[str]]:
    """Group a section into entries. A new entry starts at a non-bullet line that follows a bullet/description line, or after a blank line."""
    blocks: list[list[str]] = []
    current: list[str] = []
    prev_was_bullet = False
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            prev_was_bullet = False
            continue
        is_bullet = line.startswith("- ")
        if not is_bullet and prev_was_bullet and current:
            blocks.append(current)
            current = []
        current.append(line.lstrip("- ").strip())
        prev_was_bullet = is_bullet
    if current:
        blocks.append(current)
    return blocks


def extract_projects(text: str) -> list[dict]:
    """Return projects as [{'name','description','skills'}]. Skills are only those literally named in the project text."""
    section = split_sections(text).get("projects", "")
    projects = []
    for block in _bullet_blocks(section):
        first = block[0]
        name = re.split(r"\s+[|–—-]\s+|\s*\(\s*|\s*:\s+", first, maxsplit=1)[0].strip(" -:|")
        body = " ".join(block)
        if len(name) > 90:
            name = name[:87] + "..."
        if not name or len(body) < 3:
            continue
        projects.append({"name": name, "description": re.sub(r"\s+", " ", body)[:600], "skills": _find_vocabulary(body)})
    return projects


def extract_certifications(text: str) -> list[str]:
    """Return certificates / trainings listed on the resume, one string per item."""
    section = split_sections(text).get("certifications", "")
    items = []
    for line in section.splitlines():
        item = line.strip().lstrip("- ").strip(" ,;")
        if item and len(item) > 3 and item.lower() not in {"certifications", "certificates"}:
            items.append(re.sub(r"\s+", " ", item))
    return items


def extract_achievements(text: str) -> list[str]:
    """Return achievements / awards listed on the resume, one string per item."""
    section = split_sections(text).get("achievements", "")
    items = []
    for line in section.splitlines():
        item = line.strip().lstrip("- ").strip(" ,;")
        if item and len(item) > 3:
            items.append(re.sub(r"\s+", " ", item))
    return items


# --------------------------------------------------------------------------- experience
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE = r"(?:(?P<{m}>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*)?(?P<{y}>(?:19|20)\d{{2}})"
_RANGE = re.compile(
    rf"{_DATE.format(m='m1', y='y1')}\s*(?:-|to|until|till)\s*(?:(?P<present>present|current|ongoing|now|till date)|{_DATE.format(m='m2', y='y2')})",
    re.I,
)


def _months_between(m1, y1, m2, y2) -> int:
    start = int(y1) * 12 + (_MONTHS.get((m1 or "jan")[:3].lower(), 1) - 1)
    end = int(y2) * 12 + (_MONTHS.get((m2 or "dec")[:3].lower(), 12) - 1)
    return max(end - start + (1 if m1 and m2 else 0), 0)


def _entries_from_section(section: str, kind: str, today: date) -> list[dict]:
    entries = []
    for block in _bullet_blocks(section):
        body = " ".join(block)
        months, period = 0, ""
        m = _RANGE.search(body)
        if m:
            if m.group("present"):
                months = _months_between(m.group("m1"), m.group("y1"), today.strftime("%b"), today.year) + (1 if m.group("m1") else 0)
            else:
                months = _months_between(m.group("m1"), m.group("y1"), m.group("m2"), m.group("y2"))
            period = m.group(0)
        dur = re.search(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?)\b", body, re.I)
        if not months and dur:
            n = float(dur.group(1))
            months = int(round(n * 12)) if dur.group(2).lower().startswith(("y",)) else int(round(n))
            period = dur.group(0)
        title = re.split(r"\s+[|–—-]\s+|,\s+|\s+at\s+|\s*\(", block[0], maxsplit=1)[0].strip(" -:|")
        entries.append({"title": title[:90] or kind, "kind": kind, "months": months, "period": period, "description": re.sub(r"\s+", " ", body)[:400], "skills": _find_vocabulary(body)})
    return [e for e in entries if e["title"]]


def extract_experience_entries(text: str) -> dict:
    """Return employment and internship entries separately: {'employment': [...], 'internships': [...], 'stated_years': float or -1}.
    Projects and training courses are never counted as experience."""
    sections = split_sections(text)
    today = date.today()
    employment = _entries_from_section(sections.get("experience", ""), "employment", today)
    internships = _entries_from_section(sections.get("internships", ""), "internship", today)
    # an "Internship" role listed inside the Experience section is an internship, not employment
    moved = [e for e in employment if re.search(r"intern", e["title"] + " " + e["description"][:80], re.I)]
    if moved:
        employment = [e for e in employment if e not in moved]
        internships += [{**e, "kind": "internship"} for e in moved]
    # a single-line statement such as "Experience: 4 years" / "Fresher"
    stated = config.NOT_STATED
    raw = sections.get("experience", "")
    inline = re.search(r"(?im)^[ \t]*(?:total experience|work experience|professional experience|experience)[ \t]*[:：-][ \t]*(.+)$", clean_resume_text(text))
    raw = inline.group(1) if inline else raw
    if raw:
        if re.search(r"\b(fresher|no experience|none|nil|not applicable|n/a)\b", raw, re.I):
            stated = 0.0
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(years?|yrs?|months?|mos?)\b", raw, re.I)
            if m:
                n = float(m.group(1))
                stated = n if m.group(2).lower().startswith("y") else round(n / 12, 2)
    if stated == config.NOT_STATED:
        generic = re.search(r"(?i)(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?(?:work\s+)?experience", clean_resume_text(text))
        if generic:
            stated = float(generic.group(1))
    return {"employment": employment, "internships": internships, "stated_years": stated}


def summarise_experience(entries: dict) -> dict:
    """Combine experience evidence: years = stated years, else the sum of dated employment. Internship months are reported separately."""
    employment_months = sum(e["months"] for e in entries["employment"])
    internship_months = sum(e["months"] for e in entries["internships"])
    if entries["stated_years"] != config.NOT_STATED:
        years = entries["stated_years"]
        basis = "stated on resume"
    elif employment_months:
        years = round(employment_months / 12, 2)
        basis = "sum of dated employment entries"
    elif entries["employment"]:
        years, basis = config.NOT_STATED, "employment listed without dates"
    else:
        years, basis = config.NOT_STATED, "no employment section found"
    return {"employment_years": years, "internship_months": internship_months, "basis": basis}


# --------------------------------------------------------------------------- context skills + optional AI gap filler
def find_context_skills(text: str, listed: list[str]) -> list[str]:
    """Technologies named in project / experience / certificate text that are NOT in the Skills section."""
    have = {_norm_skill(s) for s in listed}
    return [s for s in _find_vocabulary(text or "") if s not in have]


def enrich_missing_sections(text: str) -> dict:
    """Ask the configured LLM (Gemini/Groq/Ollama) for projects, certifications and achievements the rules could not find.
    Every returned item is kept ONLY if its name appears verbatim in the resume, so the model cannot invent evidence."""
    from hireflow import llm

    empty = {"projects": [], "certifications": [], "achievements": [], "source": ""}
    prompt = (
        "Extract from this resume ONLY what is written in it. Return JSON with keys "
        '"projects" (list of {"name","description"}), "certifications" (list of strings), "achievements" (list of strings). '
        "Copy names exactly as written. Use [] when absent. Never infer or invent.\n\nRESUME:\n" + text[:6000]
    )
    data, source = llm.generate_json(prompt)
    if not isinstance(data, dict):
        return empty
    low = re.sub(r"\s+", " ", text.lower())

    def verbatim(item: str) -> bool:
        return bool(item) and re.sub(r"\s+", " ", item.lower()).strip() in low

    projects = []
    for p in data.get("projects") or []:
        if isinstance(p, dict) and verbatim(str(p.get("name", ""))):
            body = str(p.get("description", ""))
            projects.append({"name": str(p["name"])[:90], "description": body[:600], "skills": _find_vocabulary(f"{p['name']} {body}")})
    certs = [str(c) for c in data.get("certifications") or [] if verbatim(str(c))]
    awards = [str(a) for a in data.get("achievements") or [] if verbatim(str(a))]
    return {"projects": projects, "certifications": certs, "achievements": awards, "source": source}


# --------------------------------------------------------------------------- one-call profile
_NOT_AN_ENTRY = re.compile(r"^\s*(?:\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?|months?|mos?)\b.*|fresher|none|nil|n/a|not applicable|no experience.*)\s*$", re.I)


def extract_profile(text: str) -> dict:
    """Build the full structured profile of one resume: contact, education, skills by category, projects, certifications, achievements, employment and internships."""
    cleaned = clean_resume_text(text)
    sections = split_sections(cleaned)
    contact = extract_contact(cleaned)
    edu = extract_education_details(cleaned)
    skills = extract_skill_categories(cleaned)
    projects = extract_projects(cleaned)
    certs = extract_certifications(cleaned)
    awards = extract_achievements(cleaned)
    entries = extract_experience_entries(cleaned)
    for kind in ("employment", "internships"):  # "Experience: 4 years" is a statement, not a job entry
        entries[kind] = [e for e in entries[kind] if not _NOT_AN_ENTRY.match(e["title"])]
    exp = summarise_experience(entries)
    evidence_text = "\n".join(sections.get(k, "") for k in ("projects", "experience", "internships"))
    context = find_context_skills(evidence_text, skills["listed"])
    return {
        "contact": contact,
        "degree": edu["degree"],
        "university": edu["university"],
        "cgpa": edu["cgpa"],
        "grad_year": edu["year"],
        "education_level": edu["level"],
        "education_label": edu["label"],
        "skills": skills["listed"],
        "skill_categories": skills["categories"],
        "context_skills": context,
        "projects": projects,
        "certifications": certs,
        "achievements": awards,
        "employment": entries["employment"],
        "internships": entries["internships"],
        "employment_years": exp["employment_years"],
        "internship_months": exp["internship_months"],
        "experience_basis": exp["basis"],
        "sections_found": sorted(k for k in sections if k != "header"),
    }
