"""HireFlow web frontend.   Run with:  streamlit run app.py

Fill in a job description, provide resumes, press Run. The same five-agent
pipeline used by main.py runs behind the button.
"""
import os
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from hireflow import config, llm
from hireflow.agents.coordinator import PipelineCoordinator
from hireflow.tools.coordinator_tools import load_resumes, parse_job_description

st.set_page_config(page_title="HireFlow", page_icon=":briefcase:", layout="wide")

SAMPLE_JOB = parse_job_description((config.DATA_DIR / "job_description.txt").read_text(encoding="utf-8"))
SAMPLE_SLOTS = "\n".join(__import__("json").loads((config.DATA_DIR / "availability.json").read_text())["slots"])
EDU_OPTIONS = ["diploma", "bachelor", "master", "phd"]
PASTE_HINT = "Name: Asha Rao\nSkills: Python, SQL, Git\nExperience: 3 years\nEducation: B.Tech Computer Science\n---\nName: ..."
STATUS_TEXT = {
    "scheduled": "Interview scheduled",
    "waitlisted": "Shortlisted, no free slot",
    "not_shortlisted": "Not shortlisted",
    "needs_review": "Needs manual review",
}


def build_job_text(title, required, preferred, years, edu) -> str:
    return (
        f"Title: {title}\nRequired skills: {required}\nPreferred skills: {preferred}\n"
        f"Minimum experience: {years} years\nMinimum education: {edu}\n"
    )


def collect_resumes(source, uploads, pasted) -> list[dict]:
    if source == "Sample resumes (8)":
        return load_resumes(str(config.DATA_DIR / "resumes"))
    if source == "Upload .txt files":
        return [{"id": Path(f.name).stem, "text": f.getvalue().decode("utf-8", errors="replace")} for f in uploads or []]
    blocks = [b.strip() for b in pasted.split("\n---") if b.strip()]
    return [{"id": f"pasted_{i}", "text": b} for i, b in enumerate(blocks, start=1)]


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    top_n = st.slider("Interview slots to fill (top N)", 1, 10, config.TOP_N)
    min_score = st.slider("Minimum score to be shortlisted", 0, 100, int(config.MIN_SHORTLIST_SCORE))
    bias_guard = st.toggle("Bias Guard reviewer", value=True, help="Checks rationales and scoring for protected attributes.")
    slots_text = st.text_area("Free interview slots (one per line)", SAMPLE_SLOTS, height=140)
    st.divider()
    providers = [p["name"] for p in llm.active_providers()]
    if providers:
        st.caption("Rationale sentences written by: " + " -> ".join(providers) + " (template if all fail)")
    else:
        st.caption("No model configured: fact-only template sentences are used. Scores and ranking are unaffected.")

st.title("HireFlow")
st.caption("Multi-agent recruitment screening: Parser, Matcher, Ranker, Bias Guard and Scheduler, run in order by a Coordinator over one shared candidate pool.")

# ------------------------------------------------------------------ inputs
left, right = st.columns(2, gap="large")
with left:
    st.subheader("1. Job description")
    title = st.text_input("Job title", SAMPLE_JOB["title"])
    required = st.text_input("Required skills (comma separated)", ", ".join(SAMPLE_JOB["required_skills"]))
    preferred = st.text_input("Preferred skills (comma separated)", ", ".join(SAMPLE_JOB["preferred_skills"]))
    c1, c2 = st.columns(2)
    years = c1.number_input("Minimum experience (years)", 0.0, 40.0, float(SAMPLE_JOB["min_experience_years"]), step=0.5)
    edu = c2.selectbox("Minimum education", EDU_OPTIONS, index=EDU_OPTIONS.index(config.EDU_NAMES[SAMPLE_JOB["min_education_level"]]))

with right:
    st.subheader("2. Resumes")
    source = st.radio("Source", ["Sample resumes (8)", "Upload .txt files", "Paste text"], horizontal=True)
    uploads, pasted = None, ""
    if source == "Upload .txt files":
        uploads = st.file_uploader("Resume files (.txt)", type=["txt"], accept_multiple_files=True)
    elif source == "Paste text":
        pasted = st.text_area("Paste resumes, separate each with a line containing ---", height=210, placeholder=PASTE_HINT)
    else:
        st.info("Using the 8 built-in sample resumes. One has no Skills section and one mentions protected details, to show how the agents handle them.")
    st.caption("Resume format: lines like `Name:`, `Skills:`, `Experience:`, `Education:`. Missing fields are flagged, never guessed.")

run = st.button("Run pipeline", type="primary", width="stretch")

# ------------------------------------------------------------------ run
if run:
    resumes = collect_resumes(source, uploads, pasted)
    slots = [s.strip() for s in slots_text.splitlines() if s.strip()]
    if not required.strip():
        st.error("Add at least one required skill.")
    elif not resumes:
        st.error("Add at least one resume.")
    else:
        with st.spinner("Agents are working..."):
            tmp = Path(tempfile.mkdtemp())
            (tmp / "slots.json").write_text(__import__("json").dumps({"slots": slots}))
            coordinator = PipelineCoordinator(
                availability_path=tmp / "slots.json",
                top_n=top_n,
                min_score=float(min_score),
                log_path=os.getenv("HIREFLOW_LOG_PATH") or config.LOG_PATH,
                bias_guard=bias_guard,
            )
            st.session_state["pool"] = coordinator.run(job_text=build_job_text(title, required, preferred, years, edu), resumes=resumes)

# ------------------------------------------------------------------ results
pool = st.session_state.get("pool")
if pool:
    cands = pool.all()
    st.divider()
    st.subheader("Results")
    m = st.columns(5)
    m[0].metric("Resumes processed", len(cands))
    m[1].metric("Interviews scheduled", sum(c.status == "scheduled" for c in cands))
    m[2].metric("Waitlisted", sum(c.status == "waitlisted" for c in cands))
    m[3].metric("Need manual review", sum(c.status == "needs_review" for c in cands))
    m[4].metric("Bias flags", len(pool.bias_report))

    tab_short, tab_break, tab_trace, tab_bias, tab_log = st.tabs(["Shortlist", "Score breakdown", "Agent trace", "Bias guard", "Run log"])

    with tab_short:
        ordered = sorted([c for c in cands if c.rank], key=lambda c: c.rank) + [c for c in cands if not c.rank]
        table = pd.DataFrame(
            {
                "Rank": [str(c.rank) if c.rank else "-" for c in ordered],
                "Candidate": [c.name for c in ordered],
                "Score": [f"{c.score:g}" if c.rank else "-" for c in ordered],
                "Status": [STATUS_TEXT.get(c.status, c.status) for c in ordered],
                "Interview slot": [c.slot or "" for c in ordered],
                "Rationale": [c.rationale for c in ordered],
            }
        )
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                "Rank": st.column_config.TextColumn(width="small"),
                "Score": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="medium"),
                "Interview slot": st.column_config.TextColumn(width="medium"),
                "Rationale": st.column_config.TextColumn(width="large"),
            },
        )

    with tab_break:
        by_name = {f"{c.name} ({c.cid})": c for c in cands}
        pick = by_name[st.selectbox("Candidate", list(by_name))]
        if not pick.complete:
            st.warning("Incomplete profile: " + "; ".join(pick.issues) + ". Missing fields score 0 and are never assumed.")
        st.write(f"**Total: {pick.score:g} / 100**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Requirement": [r["requirement"] for r in pick.breakdown],
                    "Met": ["yes" if r["met"] else "no" for r in pick.breakdown],
                    "Points": [r["points"] for r in pick.breakdown],
                    "Out of": [r["max"] for r in pick.breakdown],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    with tab_trace:
        st.caption("Who did what, in order. Individual tool calls are in the Run log tab.")
        events = [e for e in pool.log.entries if e["event"] != "tool_call"]
        st.dataframe(
            pd.DataFrame({"Time": [e["ts"][11:] for e in events], "Agent": [e["agent"] for e in events],
                          "Event": [e["event"] for e in events], "Detail": [e["detail"] for e in events]}),
            hide_index=True, width="stretch",
        )
        calls = Counter(e["agent"] for e in pool.log.entries if e["event"] == "tool_call")
        st.write("**Tool calls through Semantic Kernel:** " + ", ".join(f"{a} {n}" for a, n in calls.items()))

    with tab_bias:
        if not pool.bias_report:
            st.success("No protected attributes were used in any rationale or scoring row." if bias_guard else "Bias Guard is switched off.")
        for item in pool.bias_report:
            st.error(f"{pool.candidates[item['cid']].name}: flagged {', '.join(item['flags'])}")
            st.write("Before:", item["original"])
            st.write("After:", item["replaced_with"])

    with tab_log:
        lines = [f"{e['ts']} | {e['agent']} | {e['event']} | {e['detail']}" for e in pool.log.entries]
        st.caption(f"Run {pool.log.run_id}: {len(lines)} entries, appended to the run log file.")
        st.code("\n".join(lines), language="text")
        st.download_button("Download this run's log", "\n".join(lines), file_name=f"hireflow_run_{pool.log.run_id}.txt")
else:
    st.info("Set up the job and resumes above, then press **Run pipeline**.")
