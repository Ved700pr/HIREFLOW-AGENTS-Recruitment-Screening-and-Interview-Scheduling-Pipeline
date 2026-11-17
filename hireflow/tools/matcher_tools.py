"""Matcher Agent tools: deterministic, evidence-backed scoring against NAMED job requirements.

Scoring model (points out of 100, weights in config.WEIGHTS):
    Required skills 40 | Preferred skills 15 | Relevant projects 15 | Experience 15 | Education 10 | Certifications + achievements 5

Rules that keep the score honest:
  * Every row carries its evidence (where in the resume the point came from).
  * Row status is "met", "partial", "not_met" (resume shows the requirement is not satisfied)
    or "not_stated" (the resume says nothing, so it needs human verification, not a penalty narrative).
  * Training courses never earn experience points. Projects, internships and employment are scored separately.
"""
from hireflow import config
from hireflow.tools.parser_tools import normalize_skill


def _canon(skills) -> set:
    return {normalize_skill(s) for s in skills or []}


def compute_skill_overlap(candidate_skills: list[str], required: list[str], preferred: list[str], context_skills: list[str] | None = None) -> dict:
    """Split the job's required and preferred skills into listed, shown-in-projects-only and missing for this candidate."""
    listed, context = _canon(candidate_skills), _canon(context_skills) - _canon(candidate_skills)
    out = {"matched_required": [], "missing_required": [], "matched_preferred": [], "missing_preferred": [], "context_required": [], "context_preferred": []}
    for kind, wanted in (("required", required), ("preferred", preferred)):
        for skill in wanted:
            key = normalize_skill(skill)
            if key in listed:
                out[f"matched_{kind}"].append(skill)
            elif key in context:
                out[f"context_{kind}"].append(skill)
            else:
                out[f"missing_{kind}"].append(skill)
    return out


def score_experience(years: float, min_years: float, internship_months: int = 0) -> dict:
    """Score experience out of its weight. Employment counts fully, internship months at half value; training and projects never count."""
    max_pts = float(config.WEIGHTS["experience"])
    stated = years != config.NOT_STATED
    if not stated and not internship_months:
        return {"points": 0.0, "max": max_pts, "met": False, "status": "not_stated",
                "note": "no employment or internship stated", "evidence": "Resume lists no employment or internship; projects and training are scored separately. Needs human verification."}
    emp = max(years, 0.0) if stated else 0.0
    effective = emp + config.INTERNSHIP_CREDIT * internship_months / 12
    ratio = 1.0 if min_years <= 0 else min(effective / min_years, 1.0)
    parts = [f"{emp:g} yrs employment" if stated else "employment not stated"]
    if internship_months:
        parts.append(f"{internship_months} months internship counted at {config.INTERNSHIP_CREDIT:.0%}")
    met = effective >= min_years
    return {"points": round(max_pts * ratio, 1), "max": max_pts, "met": met,
            "status": "met" if met else ("partial" if ratio > 0 else "not_met"),
            "note": f"{effective:g} effective yrs vs minimum {min_years:g}", "evidence": "; ".join(parts)}


def score_education(level: int, min_level: int, degree: str = "") -> dict:
    """Score education out of its weight. Partial credit is proportional; unstated education scores 0."""
    max_pts = float(config.WEIGHTS["education"])
    if level == 0:
        return {"points": 0.0, "max": max_pts, "met": False, "status": "not_stated",
                "note": "education not stated", "evidence": "No recognisable degree in the resume. Needs human verification."}
    ratio = 1.0 if min_level <= 0 else min(level / min_level, 1.0)
    met = level >= min_level
    return {"points": round(max_pts * ratio, 1), "max": max_pts, "met": met,
            "status": "met" if met else "partial",
            "note": f"{config.EDU_NAMES.get(level, level)} vs minimum {config.EDU_NAMES.get(min_level, min_level)}",
            "evidence": degree or config.EDU_NAMES.get(level, str(level))}


def score_projects(projects: list[dict], required: list[str], preferred: list[str]) -> dict:
    """Score projects by how many of them literally name a skill the job asks for (full points at config.PROJECTS_FOR_FULL_CREDIT)."""
    max_pts = float(config.WEIGHTS["projects"])
    if not projects:
        return {"points": 0.0, "max": max_pts, "met": False, "status": "not_stated", "note": "no projects listed",
                "evidence": "No Projects section found. Needs human verification."}
    wanted = _canon(required) | _canon(preferred)
    relevant = []
    for p in projects:
        hits = sorted(_canon(p.get("skills", [])) & wanted)
        if hits:
            relevant.append(f"{p['name']} ({', '.join(hits)})")
    ratio = min(len(relevant) / config.PROJECTS_FOR_FULL_CREDIT, 1.0)
    status = "met" if ratio >= 1 else ("partial" if ratio > 0 else "not_met")
    evidence = ("Relevant: " + "; ".join(relevant)) if relevant else f"{len(projects)} project(s) listed, none name a skill the job asks for"
    return {"points": round(max_pts * ratio, 1), "max": max_pts, "met": ratio >= 1, "status": status,
            "note": f"{len(relevant)} relevant of {len(projects)} listed", "evidence": evidence}


def score_certifications(certifications: list[str], achievements: list[str], required: list[str], preferred: list[str]) -> dict:
    """Score certifications (3 pts: full if one names a job skill, half otherwise) and achievements (2 pts)."""
    max_pts = float(config.WEIGHTS["certifications"])
    if not certifications and not achievements:
        return {"points": 0.0, "max": max_pts, "met": False, "status": "not_stated", "note": "none listed", "evidence": "No certifications or achievements listed."}
    wanted = _canon(required) | _canon(preferred)
    cert_pts, bits = 0.0, []
    if certifications:
        from hireflow.tools.profile_tools import _find_vocabulary

        relevant = [c for c in certifications if _canon(_find_vocabulary(c)) & wanted]
        cert_pts = config.CERT_POINTS if relevant else config.CERT_POINTS / 2
        bits.append(f"{len(certifications)} certification/training item(s), {len(relevant)} naming a job skill")
    ach_pts = config.ACHIEVEMENT_POINTS if achievements else 0.0
    if achievements:
        bits.append(f"{len(achievements)} achievement(s)")
    points = round(min(cert_pts + ach_pts, max_pts), 1)
    return {"points": points, "max": max_pts, "met": points >= max_pts, "status": "met" if points >= max_pts else "partial",
            "note": "; ".join(bits), "evidence": "; ".join(bits)}


def build_score_breakdown(overlap: dict, experience: dict, education: dict, projects: dict | None = None, certifications: dict | None = None) -> list[dict]:
    """One row per named requirement: {requirement, met, status, points, max, evidence}."""
    w = config.WEIGHTS
    n_req = sum(len(overlap[k]) for k in ("matched_required", "context_required", "missing_required"))
    n_pref = sum(len(overlap[k]) for k in ("matched_preferred", "context_preferred", "missing_preferred"))
    req_pool, pref_pool = float(w["required"]), float(w["preferred"])
    if n_pref == 0:           # job lists no preferred skills: their points go to the required skills
        req_pool, pref_pool = req_pool + pref_pool, 0.0
    if n_req == 0:
        req_pool, pref_pool = 0.0, pref_pool + req_pool
    req_each = req_pool / n_req if n_req else 0.0
    pref_each = pref_pool / n_pref if n_pref else 0.0

    rows = []
    for kind, each, label in (("required", req_each, "Required skill"), ("preferred", pref_each, "Preferred skill")):
        for skill in overlap[f"matched_{kind}"]:
            rows.append({"requirement": f"{label}: {skill}", "met": True, "status": "met", "points": round(each, 2), "max": round(each, 2), "evidence": "Listed in the Skills section"})
        for skill in overlap[f"context_{kind}"]:
            rows.append({"requirement": f"{label}: {skill}", "met": False, "status": "partial", "points": round(each * config.SKILL_ONLY_IN_PROJECTS_CREDIT, 2), "max": round(each, 2),
                         "evidence": "Not in the Skills section, but named in project/experience text (half credit)"})
        for skill in overlap[f"missing_{kind}"]:
            rows.append({"requirement": f"{label}: {skill}", "met": False, "status": "not_met", "points": 0.0, "max": round(each, 2), "evidence": "Not found anywhere in the resume"})
    if projects is not None:
        rows.append({"requirement": f"Projects: {projects['note']}", "met": projects["met"], "status": projects["status"], "points": projects["points"], "max": projects["max"], "evidence": projects["evidence"]})
    rows.append({"requirement": f"Experience: {experience['note']}", "met": experience["met"], "status": experience["status"], "points": experience["points"], "max": experience["max"], "evidence": experience["evidence"]})
    rows.append({"requirement": f"Education: {education['note']}", "met": education["met"], "status": education["status"], "points": education["points"], "max": education["max"], "evidence": education["evidence"]})
    if certifications is not None:
        rows.append({"requirement": f"Certifications and achievements: {certifications['note']}", "met": certifications["met"], "status": certifications["status"], "points": certifications["points"], "max": certifications["max"], "evidence": certifications["evidence"]})
    return rows


def total_score(breakdown: list[dict]) -> float:
    """Sum the points of every breakdown row (0-100)."""
    return round(sum(row["points"] for row in breakdown), 1)
