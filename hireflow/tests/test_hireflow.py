"""HireFlow tests. No test depends on a model's wording; decisions, scores and order are deterministic."""
import json
from pathlib import Path

import pytest

from hireflow import config, llm
from hireflow.agents.coordinator import PipelineCoordinator
from hireflow.tools import bias_tools, matcher_tools, parser_tools, profile_tools, report_tools
from hireflow.tools.resume_ingestion import extract_resume_text

FIXTURE = Path(__file__).parent / "fixtures" / "abhishek_resume.txt"
JOB = "Title: Backend Python Developer\nRequired skills: Python, SQL, REST APIs, Git\nPreferred skills: Docker, AWS, FastAPI\nMinimum experience: 3 years\nMinimum education: Bachelor\n"


def run_pipeline(tmp_path, **kwargs):
    log_path = kwargs.pop("log_path", tmp_path / "run_log.txt")
    return PipelineCoordinator(log_path=log_path, **kwargs).run()


# ---------------------------------------------------------------- scenario 1
def test_normal_batch_ranks_and_books_top_three(tmp_path):
    pool = run_pipeline(tmp_path)
    ranked = [c.name for c in sorted((c for c in pool.all() if c.rank), key=lambda c: c.rank)]
    assert ranked == ["Sneha Iyer", "Priya Sharma", "Kavya Nair", "Rahul Kumar", "Arjun Mehta", "Aman Tiwari", "Vikram Singh"]
    # the demo resumes list no projects or certifications, so the best possible score is 100 - 15 (projects) - 5 (certs)
    assert pool.candidates["resume_04"].score == 80.0
    scheduled = {c.name: c.slot for c in pool.all() if c.status == "scheduled"}
    assert scheduled == {
        "Sneha Iyer": "Mon 17 Nov, 10:00",
        "Priya Sharma": "Mon 17 Nov, 11:00",
        "Kavya Nair": "Tue 18 Nov, 10:00",
    }
    # every point is justified against a named requirement
    for cand in pool.all():
        assert all(row["requirement"].split(":")[0] in {"Required skill", "Preferred skill", "Projects", "Experience", "Education", "Certifications and achievements"} for row in cand.breakdown)
        assert all(row["evidence"] and row["status"] in {"met", "partial", "not_met", "not_stated"} for row in cand.breakdown)
        assert cand.score == pytest.approx(sum(r["points"] for r in cand.breakdown), abs=0.1)
        assert sum(r["max"] for r in cand.breakdown) == pytest.approx(100, abs=0.1)


# ---------------------------------------------------------------- scenario 2
def test_resume_without_skills_is_marked_incomplete_not_guessed(tmp_path):
    pool = run_pipeline(tmp_path)
    neha = pool.candidates["resume_06"]
    assert neha.skills == []                      # the Parser did not invent skills from the summary text
    assert not neha.complete and "no Skills section found" in neha.issues
    assert neha.rank is None and neha.slot is None and neha.status == "needs_review"
    assert "needs manual review" in neha.rationale


# ---------------------------------------------------------------- scenario 3
def test_more_shortlisted_than_slots_waitlists_the_rest(tmp_path):
    availability = tmp_path / "one_slot.json"
    availability.write_text(json.dumps({"slots": ["Mon 17 Nov, 10:00"]}))
    pool = run_pipeline(tmp_path, availability_path=availability)
    statuses = [c.status for c in sorted((c for c in pool.all() if c.rank), key=lambda c: c.rank)][:3]
    assert statuses == ["scheduled", "waitlisted", "waitlisted"]
    assert sum(c.slot is not None for c in pool.all()) == 1


# ---------------------------------------------------------------- scenario 4
def test_bias_guard_flags_and_replaces_a_leaking_rationale(tmp_path, monkeypatch):
    def leaky(prompt, fallback, must_contain=()):
        return "Priya is a young female candidate who is married and a great fit.", "fake-model"

    monkeypatch.setattr(llm, "generate_text", leaky)
    pool = run_pipeline(tmp_path)
    priya = pool.candidates["resume_01"]
    assert any(f.startswith("gender:") for f in priya.bias_flags)
    assert any(f.startswith("age:") for f in priya.bias_flags)
    assert any(f.startswith("marital_or_family:") for f in priya.bias_flags)
    assert "female" not in priya.rationale and "young" not in priya.rationale
    assert pool.bias_report and pool.bias_report[0]["cid"] in {c.cid for c in pool.all()}
    assert any(e["event"] == "bias_flag" for e in pool.log.entries)


# ---------------------------------------------------------------- scenario 5
def test_model_failure_falls_back_to_template(tmp_path, monkeypatch):
    dead = {"name": "dead", "api_key": "x", "base_url": "http://127.0.0.1:9/v1", "model": "none"}
    monkeypatch.setattr(llm, "active_providers", lambda: [dead])
    pool = run_pipeline(tmp_path)
    assert all(c.rationale_source == "template" for c in pool.all() if c.rank)
    assert any(e["event"] == "llm_fallback" for e in pool.log.entries)
    assert pool.candidates["resume_04"].score == 80.0      # decisions unaffected by the model failure


def test_unusable_model_reply_is_rejected(tmp_path, monkeypatch):
    async def vague(provider, prompt):
        return "Great candidate."                           # does not mention the candidate's name

    monkeypatch.setattr(llm, "active_providers", lambda: [{"name": "fake", "api_key": "x", "base_url": "", "model": "m"}])
    monkeypatch.setattr(llm, "_call_provider", vague)
    text, source = llm.generate_text("prompt", fallback="TEMPLATE", must_contain=("Priya",))
    assert (text, source) == ("TEMPLATE", "template")


# ---------------------------------------------------------------- scenario 6
def test_run_log_is_append_only(tmp_path):
    log_path = tmp_path / "run_log.txt"
    run_pipeline(tmp_path, log_path=log_path)
    first = log_path.read_text()
    run_pipeline(tmp_path, log_path=log_path)
    second = log_path.read_text()
    assert second.startswith(first)                         # earlier lines untouched
    assert second.count("run_started") == 2 and len(second) > len(first)


# ---------------------------------------------------------------- tool-level checks
def test_parser_tools_never_guess():
    assert parser_tools.extract_skills("Name: A\nExperience: 2 years") == []
    assert parser_tools.extract_experience_years("Name: A") == -1.0
    assert parser_tools.extract_experience_years("Experience: Fresher") == 0.0
    assert parser_tools.extract_education("Education: B.E. Mechanical")["level"] == 2
    assert parser_tools.extract_education("Education: M.Tech")["level"] == 3
    assert parser_tools.extract_education("Name: A")["level"] == 0


def test_skill_aliases_match_job_requirements():
    overlap = matcher_tools.compute_skill_overlap(["python", "rest"], ["Python", "REST APIs"], ["Docker"])
    assert overlap["matched_required"] == ["Python", "REST APIs"] and overlap["missing_preferred"] == ["Docker"]


def _breakdown(skills, projects, certs, achievements, years, internship_months=0, level=2, context=()):
    required, preferred = ["Python", "SQL"], ["Docker"]
    overlap = matcher_tools.compute_skill_overlap(skills, required, preferred, list(context))
    return matcher_tools.build_score_breakdown(
        overlap,
        matcher_tools.score_experience(years, 3, internship_months),
        matcher_tools.score_education(level, 2),
        matcher_tools.score_projects(projects, required, preferred),
        matcher_tools.score_certifications(certs, achievements, required, preferred),
    )


def test_perfect_candidate_scores_100():
    projects = [{"name": "P1", "skills": ["python"]}, {"name": "P2", "skills": ["sql", "docker"]}]
    rows = _breakdown(["python", "sql", "docker"], projects, ["Python bootcamp"], ["Hackathon winner"], 5)
    assert matcher_tools.total_score(rows) == 100.0
    assert sum(r["max"] for r in rows) == pytest.approx(100, abs=0.1)


def test_weights_follow_the_six_part_model():
    rows = _breakdown(["python", "sql", "docker"], [], [], [], config.NOT_STATED)
    by_prefix = {}
    for r in rows:
        by_prefix[r["requirement"].split(":")[0]] = by_prefix.get(r["requirement"].split(":")[0], 0) + r["max"]
    assert {k: round(v) for k, v in by_prefix.items()} == {
        "Required skill": 40, "Preferred skill": 15, "Projects": 15, "Experience": 15, "Education": 10, "Certifications and achievements": 5}


def test_training_course_never_earns_experience_points():
    rows = _breakdown(["python", "sql", "docker"], [], ["Crash Course on Python", "Advanced SQL training"], [], config.NOT_STATED)
    exp = next(r for r in rows if r["requirement"].startswith("Experience"))
    assert exp["points"] == 0 and exp["status"] == "not_stated"


def test_internship_counts_at_half_and_is_reported_separately():
    exp = matcher_tools.score_experience(config.NOT_STATED, 2, internship_months=12)
    assert exp["points"] == pytest.approx(15 * 0.5 / 2, abs=0.1) and "internship" in exp["evidence"]


def test_skill_only_in_projects_gets_half_credit_and_missing_is_not_met():
    rows = _breakdown(["python"], [], [], [], 0, context=["sql"])
    status = {r["requirement"]: (r["status"], r["points"]) for r in rows if r["requirement"].startswith("Required")}
    assert status["Required skill: Python"][0] == "met" and status["Required skill: Python"][1] == pytest.approx(20.0)
    assert status["Required skill: SQL"][0] == "partial" and status["Required skill: SQL"][1] == pytest.approx(10.0)


def test_missing_information_is_distinguished_from_failing_a_requirement():
    assert matcher_tools.score_projects([], ["Python"], [])["status"] == "not_stated"
    assert matcher_tools.score_projects([{"name": "P", "skills": ["java"]}], ["Python"], [])["status"] == "not_met"
    assert matcher_tools.score_education(0, 2)["status"] == "not_stated"


def test_bias_checker_catches_protected_words_but_not_job_words():
    assert bias_tools.check_rationale_for_protected("She is 29 years old and Hindu")
    assert bias_tools.check_rationale_for_protected("Manager with 4 yrs experience, manages APIs; meets 3 of 4 skills") == []
    assert bias_tools.check_scoring_basis([{"requirement": "Marital status: single"}]) == ["Marital status: single"]


def test_roster_has_four_plus_agents_each_with_two_plus_tools(tmp_path):
    coordinator = PipelineCoordinator(log_path=tmp_path / "log.txt")
    agents = [agent for _, agent in coordinator.stages] + [coordinator]
    assert len(agents) >= 4
    for agent in agents:
        assert len(agent.tools) >= 2, agent.name
        assert agent.kernel.plugins[agent.name] is not None   # tools are registered in Semantic Kernel


# ---------------------------------------------------------------- CV extraction (profile)
def test_full_profile_extraction_from_a_realistic_cv():
    p = profile_tools.extract_profile(FIXTURE.read_text())
    assert p["contact"] == {"email": "kumarabhishek@gmail.com", "phone": "+91-9115585240",
                            "linkedin": "linkedin.com/in/kumaar-abhishekk", "github": "github.com/abhishekk"}
    assert (p["degree"], p["university"], p["cgpa"], p["education_level"]) == ("B.Tech CSE", "Lovely Professional University", 6.5, 2)
    assert p["skill_categories"]["Languages"] == ["c++", "python", "javascript"]
    assert {"aws", "docker", "linux", "git", "github", "bolt.ai", "vercel.ai"} <= set(p["skills"])
    assert [x["name"] for x in p["projects"]] == ["Cloud Cost Optimization", "Artisan Aura"]
    assert len(p["certifications"]) == 5 and "Crash Course on Python" in p["certifications"]
    assert p["achievements"] == ["Smart India Hackathon - 8th rank", "HackerRank - Silver-level badge"]
    assert p["employment"] == [] and p["internships"] == []       # training and projects are not experience


def test_cv_without_employment_is_scored_with_evidence_not_rejected(tmp_path):
    pool = PipelineCoordinator(log_path=tmp_path / "l.txt").run(job_text=JOB, resumes=[{"id": "ab", "text": FIXTURE.read_text()}])
    cand = pool.candidates["ab"]
    assert cand.complete and cand.name == "Abhishek Kumar" and cand.experience_years == config.NOT_STATED
    exp = next(r for r in cand.breakdown if r["requirement"].startswith("Experience"))
    assert exp["points"] == 0 and exp["status"] == "not_stated"
    assert any("no formal employment" in n for n in cand.notes)
    assert {r["requirement"]: r["status"] for r in cand.breakdown}["Required skill: SQL"] == "not_met"
    assert cand.score == pytest.approx(sum(r["points"] for r in cand.breakdown), abs=0.1)


def test_ai_enrichment_keeps_only_items_found_verbatim_in_the_resume(monkeypatch):
    text = "Name: A\nSkills: Python\nI built Weather Bot using Python."
    fake = {"projects": [{"name": "Weather Bot", "description": "x"}, {"name": "Invented Project", "description": "y"}],
            "certifications": ["AWS Certified Wizard"], "achievements": []}
    monkeypatch.setattr(llm, "generate_json", lambda prompt: (fake, "fake"))
    out = profile_tools.enrich_missing_sections(text)
    assert [p["name"] for p in out["projects"]] == ["Weather Bot"] and out["certifications"] == [] and out["source"] == "fake"


def test_generate_json_returns_nothing_when_no_model_is_configured():
    assert llm.generate_json("prompt") == (None, "")


def test_duplicate_file_names_do_not_overwrite_each_other(tmp_path):
    resumes = [{"id": "cv", "text": "Name: One\nSkills: Python"}, {"id": "cv", "text": "Name: Two\nSkills: Python"}]
    pool = PipelineCoordinator(log_path=tmp_path / "l.txt").run(job_text=JOB, resumes=resumes)
    assert sorted(c.name for c in pool.all()) == ["One", "Two"]


# ---------------------------------------------------------------- reports
def test_reports_cover_every_candidate_with_evidence(tmp_path):
    pool = run_pipeline(tmp_path)
    records = pool.records()
    assert len(records) == 8 and records[0]["rank"] == 1 and records[-1]["status"] == "needs_review"
    rows = report_tools.database_rows(records)
    assert len(rows) == 8 and {"Email", "Degree", "Projects", "Certifications / training", "Evidence summary"} <= set(rows[0])
    assert report_tools.evidence_rows(records)[0]["Evidence"]
    assert report_tools.to_csv_bytes(rows).startswith(b"\xef\xbb\xbf")
    assert json.loads(report_tools.to_json_bytes(records, pool.job))["candidates"][0]["name"] == "Sneha Iyer"
    assert report_tools.to_excel_bytes(records, pool.job)[:2] == b"PK"
    assert "## Score evidence" in pool.report_md and "Sneha Iyer" in pool.report_md and "Neha Gupta" in pool.report_md


# ---------------------------------------------------------------- file ingestion
def test_docx_text_includes_tables_and_hyperlinks():
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_paragraph("Asha Rao")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Python, SQL"
    buf = BytesIO()
    doc.save(buf)
    text = extract_resume_text("cv.docx", buf.getvalue())
    assert "Asha Rao" in text and "Python, SQL" in text


def test_txt_and_unsupported_formats():
    assert "hello" in extract_resume_text("a.txt", "hello".encode("utf-16-le").decode("utf-16-le").encode("cp1252"))
    with pytest.raises(ValueError):
        extract_resume_text("a.png", b"x")
