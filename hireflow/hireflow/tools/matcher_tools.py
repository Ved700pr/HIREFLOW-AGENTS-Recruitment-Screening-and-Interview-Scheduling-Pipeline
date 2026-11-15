"""Matcher Agent tools: deterministic scoring against NAMED job requirements.

Every point in the score is tied to one requirement, so the justification can say
exactly where each point came from.
"""
from hireflow import config
from hireflow.tools.parser_tools import normalize_skill


def compute_skill_overlap(candidate_skills: list[str], required: list[str], preferred: list[str]) -> dict:
    """Split the job's required and preferred skills into matched and missing for this candidate."""
    have = {normalize_skill(s) for s in candidate_skills}
    out = {"matched_required": [], "missing_required": [], "matched_preferred": [], "missing_preferred": []}
    for skill in required:
        out["matched_required" if normalize_skill(skill) in have else "missing_required"].append(skill)
    for skill in preferred:
        out["matched_preferred" if normalize_skill(skill) in have else "missing_preferred"].append(skill)
    return out


def score_experience(years: float, min_years: float) -> dict:
    """Score experience out of its weight. Partial credit is proportional; unstated experience scores 0."""
    max_pts = float(config.WEIGHTS["experience"])
    if years == config.NOT_STATED:
        return {"points": 0.0, "max": max_pts, "met": False, "note": "experience not stated (not assumed)"}
    ratio = 1.0 if min_years <= 0 else min(years / min_years, 1.0)
    return {
        "points": round(max_pts * ratio, 1),
        "max": max_pts,
        "met": years >= min_years,
        "note": f"{years:g} yrs vs minimum {min_years:g}",
    }


def score_education(level: int, min_level: int) -> dict:
    """Score education out of its weight. Partial credit is proportional; unstated education scores 0."""
    max_pts = float(config.WEIGHTS["education"])
    if level == 0:
        return {"points": 0.0, "max": max_pts, "met": False, "note": "education not stated (not assumed)"}
    ratio = 1.0 if min_level <= 0 else min(level / min_level, 1.0)
    return {
        "points": round(max_pts * ratio, 1),
        "max": max_pts,
        "met": level >= min_level,
        "note": f"{config.EDU_NAMES.get(level, level)} vs minimum {config.EDU_NAMES.get(min_level, min_level)}",
    }


def build_score_breakdown(overlap: dict, experience: dict, education: dict) -> list[dict]:
    """Turn the pieces into one row per named requirement: {requirement, met, points, max}."""
    n_req = len(overlap["matched_required"]) + len(overlap["missing_required"])
    n_pref = len(overlap["matched_preferred"]) + len(overlap["missing_preferred"])
    skill_pts = float(config.WEIGHTS["skills"])
    if n_pref == 0:
        req_share, pref_share = 1.0, 0.0
    elif n_req == 0:
        req_share, pref_share = 0.0, 1.0
    else:
        req_share = config.REQUIRED_SHARE_OF_SKILLS
        pref_share = 1.0 - req_share
    req_each = skill_pts * req_share / n_req if n_req else 0.0
    pref_each = skill_pts * pref_share / n_pref if n_pref else 0.0

    rows = []
    for skill in overlap["matched_required"]:
        rows.append({"requirement": f"Required skill: {skill}", "met": True, "points": round(req_each, 1), "max": round(req_each, 1)})
    for skill in overlap["missing_required"]:
        rows.append({"requirement": f"Required skill: {skill}", "met": False, "points": 0.0, "max": round(req_each, 1)})
    for skill in overlap["matched_preferred"]:
        rows.append({"requirement": f"Preferred skill: {skill}", "met": True, "points": round(pref_each, 1), "max": round(pref_each, 1)})
    for skill in overlap["missing_preferred"]:
        rows.append({"requirement": f"Preferred skill: {skill}", "met": False, "points": 0.0, "max": round(pref_each, 1)})
    rows.append({"requirement": f"Experience: {experience['note']}", "met": experience["met"], "points": experience["points"], "max": experience["max"]})
    rows.append({"requirement": f"Education: {education['note']}", "met": education["met"], "points": education["points"], "max": education["max"]})
    return rows


def total_score(breakdown: list[dict]) -> float:
    """Sum the points of every breakdown row (0-100)."""
    return round(sum(row["points"] for row in breakdown), 1)
