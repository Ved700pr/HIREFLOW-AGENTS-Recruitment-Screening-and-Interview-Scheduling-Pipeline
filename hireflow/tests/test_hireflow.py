"""HireFlow tests. No test depends on a model's wording; decisions, scores and order are deterministic."""
import json

import pytest

from hireflow import llm
from hireflow.agents.coordinator import PipelineCoordinator
from hireflow.tools import bias_tools, matcher_tools, parser_tools


def run_pipeline(tmp_path, **kwargs):
    log_path = kwargs.pop("log_path", tmp_path / "run_log.txt")
    return PipelineCoordinator(log_path=log_path, **kwargs).run()


# ---------------------------------------------------------------- scenario 1
def test_normal_batch_ranks_and_books_top_three(tmp_path):
    pool = run_pipeline(tmp_path)
    ranked = [c.name for c in sorted((c for c in pool.all() if c.rank), key=lambda c: c.rank)]
    assert ranked == ["Sneha Iyer", "Priya Sharma", "Kavya Nair", "Rahul Kumar", "Aman Tiwari", "Arjun Mehta", "Vikram Singh"]
    assert pool.candidates["resume_04"].score == 100.0
    scheduled = {c.name: c.slot for c in pool.all() if c.status == "scheduled"}
    assert scheduled == {
        "Sneha Iyer": "Mon 17 Nov, 10:00",
        "Priya Sharma": "Mon 17 Nov, 11:00",
        "Kavya Nair": "Tue 18 Nov, 10:00",
    }
    # every point is justified against a named requirement
    for cand in pool.all():
        assert all(row["requirement"].split(":")[0] in {"Required skill", "Preferred skill", "Experience", "Education"} for row in cand.breakdown)
        assert cand.score == pytest.approx(sum(r["points"] for r in cand.breakdown))


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
    assert pool.candidates["resume_04"].score == 100.0     # decisions unaffected by the model failure


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


def test_perfect_candidate_scores_100():
    overlap = matcher_tools.compute_skill_overlap(["a", "b", "c"], ["a", "b"], ["c"])
    rows = matcher_tools.build_score_breakdown(overlap, matcher_tools.score_experience(5, 3), matcher_tools.score_education(2, 2))
    assert matcher_tools.total_score(rows) == 100.0


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
