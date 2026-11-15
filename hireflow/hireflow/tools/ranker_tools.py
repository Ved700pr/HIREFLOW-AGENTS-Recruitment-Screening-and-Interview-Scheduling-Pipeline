"""Ranker Agent tools: ordering and one-line rationale.

The template rationale is built from facts only, so it is also the safe fallback when no model is available.
"""
from hireflow import config


def sort_candidates(rows: list[dict]) -> dict:
    """Rank complete candidates by score (ties: more experience, then id). Incomplete ones go to 'needs_review'."""
    complete = [r for r in rows if r["complete"]]
    review = [r for r in rows if not r["complete"]]
    complete.sort(key=lambda r: (-r["score"], -max(r["experience_years"], 0), r["cid"]))
    return {"ranked": [r["cid"] for r in complete], "needs_review": [r["cid"] for r in review]}


def format_rationale(row: dict) -> str:
    """Build the fact-only one-line rationale for a candidate (no model involved)."""
    if not row["complete"]:
        return f"{row['name']}: incomplete profile ({'; '.join(row['issues'])}) - needs manual review, not ranked."
    overlap = row["overlap"]
    met = len(overlap["matched_required"])
    missing = overlap["missing_required"]
    miss_txt = f" (missing: {', '.join(missing)})" if missing else ""
    years = row["experience_years"]
    exp_txt = "experience not stated" if years == config.NOT_STATED else f"{years:g} yrs experience (min {row['min_years']:g})"
    return f"{row['name']}: {row['score']:g}/100. Meets {met} of {row['required_count']} required skills{miss_txt}; {exp_txt}; education {row['education_label']}."


def build_rationale_prompt(row: dict) -> str:
    """Build the prompt that asks the model to polish the rationale, using facts only."""
    return (
        "Write ONE sentence (max 30 words) summarising why this candidate fits the job. "
        f"Start with the candidate's first name. Facts: {format_rationale(row)}"
    )
