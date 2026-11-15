"""Pipeline Coordinator tools: loading inputs, running a stage safely, building the final report."""
import re
import time
from pathlib import Path

from hireflow import config
from hireflow.tools.parser_tools import _field


def load_job_description(path: str) -> dict:
    """Read the job description file into named requirements."""
    return parse_job_description(Path(path).read_text(encoding="utf-8"))


def parse_job_description(text: str) -> dict:
    """Turn job description text (Title / Required skills / Preferred skills / Minimum experience / Minimum education lines) into named requirements."""

    def _list(label):
        raw = _field(text, label)
        return [s.strip() for s in raw.split(",") if s.strip()] if raw else []

    years = re.search(r"(\d+(?:\.\d+)?)", _field(text, "minimum experience") or "0")
    edu_raw = (_field(text, "minimum education") or "").lower().replace(".", "")
    min_level = next((lvl for name, lvl in config.EDU_LEVELS.items() if name in edu_raw), 0)
    return {
        "title": _field(text, "title") or "Untitled role",
        "required_skills": _list("required skills"),
        "preferred_skills": _list("preferred skills"),
        "min_experience_years": float(years.group(1)) if years else 0.0,
        "min_education_level": min_level,
    }


def load_resumes(folder: str) -> list[dict]:
    """Read every .txt resume in the folder as {'id': file name without extension, 'text': contents}."""
    return [{"id": p.stem, "text": p.read_text(encoding="utf-8")} for p in sorted(Path(folder).glob("*.txt"))]


def build_final_report(rows: list[dict], title: str) -> str:
    """Format the shortlist as a text table. Each row: cid, name, rank, score, slot, status, rationale."""
    lines = [f"Shortlist for: {title}", "-" * 100]
    ranked = sorted([r for r in rows if r["rank"] is not None], key=lambda r: r["rank"])
    for r in ranked:
        slot = r["slot"] or r["status"].upper()
        lines.append(f"{r['rank']}. {r['name']} | score {r['score']:g} | {slot}")
        lines.append(f"     {r['rationale']}")
    review = [r for r in rows if r["rank"] is None]
    if review:
        lines.append("-" * 100)
        lines.append("Needs manual review (not ranked, not scheduled):")
        for r in review:
            lines.append(f"   - {r['name']}: {r['rationale']}")
    return "\n".join(lines)


def run_stage(name: str, stage_fn, log) -> float:
    """Run one pipeline stage with timing and failure logging. Re-raises so a broken stage stops the run loudly."""
    start = time.perf_counter()
    log.write("coordinator", "stage_started", name)
    try:
        stage_fn()
    except Exception as exc:
        log.write("coordinator", "stage_failed", f"{name}: {exc!r}")
        raise
    elapsed = round(time.perf_counter() - start, 2)
    log.write("coordinator", "stage_finished", f"{name} in {elapsed}s")
    return elapsed
