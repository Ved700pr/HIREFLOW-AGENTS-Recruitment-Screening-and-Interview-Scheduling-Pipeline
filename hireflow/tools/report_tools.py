"""Report tools: turn the finished candidate pool into a candidate database and downloadable recruitment reports.

All functions take plain records (Candidate.to_record()) so they work for the coordinator, the UI and the tests.
"""
from __future__ import annotations

import io
import json
from datetime import datetime

STATUS_TEXT = {
    "scheduled": "Interview scheduled",
    "waitlisted": "Shortlisted - waitlist",
    "not_shortlisted": "Not shortlisted",
    "needs_review": "Manual review",
}


def _join(items, sep="; ") -> str:
    return sep.join(str(i) for i in items) if items else ""


def database_rows(records: list[dict]) -> list[dict]:
    """One flat row per candidate with every extracted field (for CSV / Excel / the Candidate database tab)."""
    rows = []
    for r in records:
        c = r["contact"]
        rows.append({
            "Rank": r["rank"] if r["rank"] else "",
            "Candidate": r["name"],
            "Score": r["score"] if r["rank"] else "",
            "Decision": STATUS_TEXT.get(r["status"], r["status"]),
            "Interview slot": r["slot"],
            "Email": c.get("email", ""),
            "Phone": c.get("phone", ""),
            "LinkedIn": c.get("linkedin", ""),
            "GitHub": c.get("github", ""),
            "Degree": r["degree"],
            "University": r["university"],
            "CGPA": r["cgpa"] if r["cgpa"] is not None else "",
            "Graduation year": r["graduation_year"],
            "Skills": _join(r["skills"], ", "),
            "Skills shown only in projects": _join(r["skills_from_projects"], ", "),
            "Projects": _join([p["name"] for p in r["projects"]]),
            "Certifications / training": _join(r["certifications"]),
            "Achievements": _join(r["achievements"]),
            "Employment (years)": "" if r["employment_years"] is None else r["employment_years"],
            "Internship (months)": r["internship_months"],
            "Experience note": r["experience_basis"],
            "Profile complete": "Yes" if r["complete"] else "No",
            "Profile gaps": _join(r["issues"]),
            "Notes": _join(r["notes"]),
            "Evidence summary": r["rationale"],
            "Candidate ID": r["id"],
        })
    return rows


def evidence_rows(records: list[dict]) -> list[dict]:
    """One row per awarded/withheld point: candidate x requirement with evidence."""
    out = []
    for r in records:
        for b in r["breakdown"]:
            out.append({"Candidate": r["name"], "Requirement": b["requirement"], "Status": b.get("status", "met" if b["met"] else "not_met"),
                        "Points": b["points"], "Maximum": b["max"], "Evidence": b.get("evidence", "")})
    return out


def to_csv_bytes(rows: list[dict]) -> bytes:
    import csv

    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def to_json_bytes(records: list[dict], job: dict) -> bytes:
    return json.dumps({"generated": datetime.now().isoformat(timespec="seconds"), "job": job, "candidates": records}, indent=2, ensure_ascii=False).encode("utf-8")


def to_excel_bytes(records: list[dict], job: dict) -> bytes:
    """Excel workbook: Candidates, Score evidence, Projects, Job."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    sheets = [
        ("Candidates", database_rows(records)),
        ("Score evidence", evidence_rows(records)),
        ("Projects", [{"Candidate": r["name"], "Project": p["name"], "Skills used": _join(p["skills"], ", "), "Description": p["description"]} for r in records for p in r["projects"]]),
        ("Job", [{"Field": "Title", "Value": job.get("title", "")}, {"Field": "Required skills", "Value": _join(job.get("required_skills", []), ", ")},
                 {"Field": "Preferred skills", "Value": _join(job.get("preferred_skills", []), ", ")}, {"Field": "Minimum experience (years)", "Value": job.get("min_experience_years", 0)}]),
    ]
    for i, (title, rows) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = title
        if not rows:
            ws.append(["No data"])
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row[h] for h in headers])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="435FF4")
        for col_idx, header in enumerate(headers, start=1):
            longest = max(len(str(header)), *(len(str(row[header])) for row in rows))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(12, longest + 2), 60)
        ws.freeze_panes = "A2"
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def candidate_report_md(r: dict) -> str:
    """Single-candidate screening report with evidence for every score line."""
    c = r["contact"]
    lines = [f"# {r['name']}", "", f"**Decision:** {STATUS_TEXT.get(r['status'], r['status'])}"
             + (f" - {r['slot']}" if r["slot"] else "") + (f"  |  **Rank:** {r['rank']}" if r["rank"] else ""),
             f"**Match score:** {r['score']:g}/100", "", "## Contact"]
    for label, key in (("Email", "email"), ("Phone", "phone"), ("LinkedIn", "linkedin"), ("GitHub", "github")):
        lines.append(f"- {label}: {c.get(key) or 'not stated'}")
    lines += ["", "## Education", f"- Degree: {r['degree'] or r['education_level']}", f"- University: {r['university'] or 'not stated'}",
              f"- CGPA: {r['cgpa'] if r['cgpa'] is not None else 'not stated'}", f"- Graduation year: {r['graduation_year'] or 'not stated'}", "", "## Skills"]
    if r["skill_categories"]:
        lines += [f"- {cat}: {', '.join(vals)}" for cat, vals in r["skill_categories"].items()]
    else:
        lines.append(f"- {_join(r['skills'], ', ') or 'none extracted'}")
    lines += ["", "## Projects"]
    lines += [f"- **{p['name']}** - skills used: {_join(p['skills'], ', ') or 'none named'}" for p in r["projects"]] or ["- none listed"]
    lines += ["", "## Certifications and training"] + ([f"- {x}" for x in r["certifications"]] or ["- none listed"])
    lines += ["", "## Achievements"] + ([f"- {x}" for x in r["achievements"]] or ["- none listed"])
    lines += ["", "## Experience"]
    if r["employment_years"] is None and not r["internship_months"]:
        lines.append("- No formal employment or internship stated. Projects and training are evaluated separately and do not count as experience.")
    else:
        if r["employment_years"] is not None:
            lines.append(f"- Employment: {r['employment_years']:g} years ({r['experience_basis']})")
        if r["internship_months"]:
            lines.append(f"- Internships: {r['internship_months']} months")
    lines += ["", "## Score evidence", "", "| Requirement | Status | Points | Evidence |", "|---|---|---|---|"]
    for b in r["breakdown"]:
        lines.append(f"| {b['requirement']} | {b.get('status', '')} | {b['points']:g}/{b['max']:g} | {str(b.get('evidence', '')).replace('|', '/')} |")
    if r["issues"] or r["notes"]:
        lines += ["", "## Needs human verification"] + [f"- {x}" for x in [*r["issues"], *r["notes"]]]
    lines += ["", "## Summary", r["rationale"] or "No rationale available.", "",
              "_Extracted from the resume text only; nothing is verified independently. Human review is required for hiring decisions._"]
    return "\n".join(lines)


def recruitment_report_md(records: list[dict], job: dict) -> str:
    """Full recruitment report: job, shortlist, manual-review list, then every candidate."""
    ranked = [r for r in records if r["rank"]]
    review = [r for r in records if not r["rank"]]
    lines = [f"# Recruitment report - {job.get('title', 'Role')}", f"_Generated {datetime.now():%Y-%m-%d %H:%M}_", "", "## Role requirements",
             f"- Required skills: {_join(job.get('required_skills', []), ', ')}", f"- Preferred skills: {_join(job.get('preferred_skills', []), ', ') or 'none'}",
             f"- Minimum experience: {job.get('min_experience_years', 0):g} years", "",
             f"## Summary", f"- CVs analysed: {len(records)}", f"- Ranked: {len(ranked)}", f"- Interviews scheduled: {sum(r['status'] == 'scheduled' for r in records)}",
             f"- Manual review: {len(review)}", "", "## Ranked shortlist", "", "| Rank | Candidate | Score | Decision | Slot |", "|---|---|---|---|---|"]
    lines += [f"| {r['rank']} | {r['name']} | {r['score']:g} | {STATUS_TEXT.get(r['status'], r['status'])} | {r['slot'] or '-'} |" for r in ranked]
    if review:
        lines += ["", "## Manual review (not ranked)"] + [f"- **{r['name']}**: {_join(r['issues'])}" for r in review]
    lines += ["", "---", ""]
    lines += ["\n\n---\n\n".join(candidate_report_md(r) for r in records)]
    return "\n".join(lines)
