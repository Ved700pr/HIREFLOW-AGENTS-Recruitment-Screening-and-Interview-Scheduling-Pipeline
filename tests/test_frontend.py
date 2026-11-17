"""Frontend tests using Streamlit's built-in AppTest (no browser needed)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from hireflow.agents.coordinator import PipelineCoordinator

APP = str(Path(__file__).resolve().parent.parent / "app.py")

PASTED = """Name: Asha Rao
Skills: Python, SQL, REST APIs, Git, Docker
Experience: 4 years
Education: B.Tech Computer Science
---
Name: Ben Cole
Skills: Python, Git
Experience: 1 year
Education: Diploma in IT
"""


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("HIREFLOW_LOG_PATH", str(tmp_path / "ui_log.txt"))
    return AppTest.from_file(APP, default_timeout=60)


def by_label(elements, start):
    return next(e for e in elements if e.label.startswith(start))


def test_sample_run_shows_shortlist_and_metrics(app):
    app.run()
    assert not app.exception
    app.radio[0].set_value("Use demo candidates")
    app.run()
    app.button[0].click().run()
    assert not app.exception and not app.error
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["CVs analyzed"] == "8"
    assert metrics["Interviews booked"] == "3"
    assert metrics["Manual review"] == "1"
    table = app.dataframe[0].value
    assert list(table["Candidate"][:3]) == ["Sneha Iyer", "Priya Sharma", "Kavya Nair"]
    database = next(df.value for df in app.dataframe if "Email" in df.value.columns)   # candidate database tab
    assert len(database) == 8


def test_pasted_resumes_and_custom_job_are_used(app):
    app.run()
    app.radio[0].set_value("Paste resume text")
    app.run()
    by_label(app.text_area, "Paste the complete CV").set_value(PASTED)
    by_label(app.text_input, "Must-have skills").set_value("Python, SQL")
    app.button[0].click().run()
    assert not app.exception and not app.error
    table = app.dataframe[0].value
    assert list(table["Candidate"]) == ["Asha Rao", "Ben Cole"]
    assert {m.label: m.value for m in app.metric}["CVs analyzed"] == "2"


def test_empty_inputs_show_clear_errors(app):
    app.run()
    by_label(app.text_input, "Must-have skills").set_value("")
    app.button[0].click().run()
    assert any("must-have skill" in e.value for e in app.error)

    by_label(app.text_input, "Must-have skills").set_value("Python")
    app.radio[0].set_value("Paste resume text")
    app.run()
    app.button[0].click().run()
    assert any("No readable resumes" in e.value for e in app.error)


def test_pipeline_accepts_in_memory_inputs(tmp_path):
    job_text = "Title: Data Analyst\nRequired skills: SQL, Python\nPreferred skills: Tableau\nMinimum experience: 2 years\nMinimum education: Bachelor\n"
    resumes = [{"id": "x1", "text": "Name: Zed\nSkills: SQL, Python, Tableau\nExperience: 3 years\nEducation: B.Sc"}]
    pool = PipelineCoordinator(log_path=tmp_path / "log.txt").run(job_text=job_text, resumes=resumes)
    assert pool.job["title"] == "Data Analyst" and pool.job["required_skills"] == ["SQL", "Python"]
    # skills 40 + preferred 15 + experience 15 + education 10 = 80 (no projects or certifications on this CV)
    assert pool.candidates["x1"].score == 80.0 and pool.candidates["x1"].status == "scheduled"
