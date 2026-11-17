"""HireFlow - Recruitment Screening and Talent Intelligence Platform."""

import json
import os
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from hireflow import config, llm
from hireflow.agents.coordinator import PipelineCoordinator
from hireflow.tools import report_tools
from hireflow.tools.coordinator_tools import load_resumes, parse_job_description
from hireflow.tools.resume_ingestion import (
    extract_resume_text,
    split_pasted_resumes,
)


st.set_page_config(
    page_title="HireFlow | Talent Intelligence",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

EDU_OPTIONS = ["diploma", "bachelor", "master", "phd"]

STATUS_TEXT = {
    "scheduled": "Interview scheduled",
    "waitlisted": "Shortlisted - waitlist",
    "not_shortlisted": "Not shortlisted",
    "needs_review": "Manual review",
}


ACRONYMS = {"sql", "aws", "gcp", "html", "css", "scss", "nlp", "llm", "etl", "oop", "ci/cd", "rest apis", "nosql", "php", "r", "c", "c++", "c#", "gcp"}


def pretty_skill(skill):
    """Display a skill name: keep acronyms upper-case (SQL, AWS, REST APIs), title-case the rest."""
    low = skill.lower()
    if low == "rest apis":
        return "REST APIs"
    if low in ACRONYMS:
        return skill.upper()
    return skill.title()


def load_sample_job():
    try:
        path = config.DATA_DIR / "job_description.txt"
        return parse_job_description(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "title": "Backend Python Developer",
            "required_skills": ["Python", "SQL", "REST APIs", "Git"],
            "preferred_skills": ["Docker", "AWS", "FastAPI"],
            "min_experience_years": 3,
            "min_education_level": 1,
        }


def load_sample_slots():
    try:
        path = config.DATA_DIR / "availability.json"
        return "\n".join(
            json.loads(path.read_text(encoding="utf-8"))["slots"]
        )
    except Exception:
        return ""


SAMPLE_JOB = load_sample_job()
SAMPLE_SLOTS = load_sample_slots()


CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
    --ink: #172033;
    --muted: #52617a;
    --line: #e2e8f0;
    --blue: #435ff4;
    --violet: #7458e8;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #f5f7fc !important;
    color: var(--ink) !important;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.5rem;
    padding-bottom: 4rem;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: #10182b;
}

[data-testid="stSidebar"] * {
    color: #e8edff !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #c1cbe0 !important;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: #1b2740 !important;
    color: white !important;
}

.hero {
    padding: 34px;
    border-radius: 22px;
    color: white;
    background:
        radial-gradient(circle at 90% 0%, rgba(145,128,255,.5), transparent 32%),
        linear-gradient(115deg, #17233f, #293d76 58%, #5147a8);
    box-shadow: 0 18px 45px rgba(40,54,110,.14);
    margin-bottom: 25px;
}

.hero-kicker {
    text-transform: uppercase;
    letter-spacing: 2px;
    font-size: 11px;
    font-weight: 800;
    color: #c7d2fe;
}

.hero h1 {
    font-family: Manrope, sans-serif;
    font-size: 35px;
    margin: 10px 0 7px;
    color: white !important;
    font-weight: 800;
}

.hero p {
    color: #e0e7ff !important;
    margin: 0;
    font-size: 14px;
}

.section-card {
    background: white;
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 5px 18px rgba(31,45,80,.035);
    margin-bottom: 18px;
}

.section-head {
    font-family: Manrope, sans-serif;
    font-weight: 800;
    font-size: 18px;
    color: #172033 !important;
    margin-bottom: 6px;
}

.section-sub {
    color: #52617a !important;
    font-size: 13px;
    margin-bottom: 16px;
}

.step {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 29px;
    height: 29px;
    border-radius: 9px;
    color: white !important;
    background: linear-gradient(135deg, #4968ff, #7957e8);
    font-weight: 800;
    margin-right: 9px;
    font-size: 12px;
}

.small-note {
    font-size: 12px;
    color: #52617a !important;
}

.upload-hint {
    background: #eff4ff;
    border: 1px dashed #9aabdc;
    padding: 14px;
    border-radius: 12px;
    color: #34466d !important;
    font-size: 12px;
    margin-top: 10px;
}

/* Main text visibility */

.stApp label,
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stCaptionContainer"] p,
.stApp .stRadio label,
.stApp .stCheckbox label {
    color: #344054 !important;
    opacity: 1 !important;
}

.stApp [data-testid="stWidgetLabel"] p {
    font-weight: 600 !important;
}

.stApp input,
.stApp textarea {
    background: #ffffff !important;
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 9px !important;
}

.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #8290a7 !important;
    -webkit-text-fill-color: #8290a7 !important;
}

.stApp [data-baseweb="input"] > div,
.stApp [data-baseweb="textarea"] > div,
.stApp [data-baseweb="select"] > div {
    background: #ffffff !important;
    border-color: #cbd5e1 !important;
}

.stApp [data-baseweb="select"] *,
.stApp [data-baseweb="select"] input {
    color: #172033 !important;
}

.stApp [role="radiogroup"] label,
.stApp [role="radiogroup"] label * {
    color: #344054 !important;
    opacity: 1 !important;
}

.stApp [data-testid="stFileUploader"] section {
    background: #ffffff !important;
    border: 1px dashed #94a3b8 !important;
    border-radius: 14px !important;
}

.stApp [data-testid="stFileUploader"] section * {
    color: #344054 !important;
    opacity: 1 !important;
}

.stApp [data-testid="stMetric"] {
    background: white;
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 16px;
    box-shadow: 0 5px 18px rgba(31,45,80,.035);
}

.stApp [data-testid="stMetricLabel"] {
    color: #52617a !important;
}

.stApp [data-testid="stMetricValue"] {
    color: #172033 !important;
    font-family: Manrope, sans-serif;
    font-weight: 800;
}

.stApp [data-testid="stTabs"] button {
    font-weight: 700;
    color: #344054 !important;
}

.stApp [data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
}

.stApp div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    min-height: 42px;
}

.stApp div.stButton > button[kind="primary"] {
    background: linear-gradient(100deg, #435ff4, #7458e8);
    color: white !important;
    border: 0;
    border-radius: 12px;
    padding: 12px 22px;
    font-weight: 800;
    box-shadow: 0 8px 20px rgba(76,91,226,.22);
}

.stApp [data-testid="stAlert"] {
    border-radius: 12px;
}

/* Specific colours that must win over the global text rule above */

.stApp .hero p {
    color: #e0e7ff !important;
}

.stApp .hero h1,
.stApp .hero .hero-kicker {
    color: white !important;
}

.stApp .hero .hero-kicker {
    color: #c7d2fe !important;
}

.stApp div.stButton > button[kind="primary"] p,
.stApp div.stButton > button[kind="primary"] span {
    color: white !important;
}

.stApp [data-testid="stSidebar"] label,
.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
.stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
.stApp [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stSidebar"] [data-testid="stSliderThumbValue"],
.stApp [data-testid="stSidebar"] [data-testid="stTickBarMin"],
.stApp [data-testid="stSidebar"] [data-testid="stTickBarMax"] {
    color: #dbe3f7 !important;
}

.stApp [data-testid="stSidebar"] [data-testid="stAlert"] p,
.stApp [data-testid="stSidebar"] [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stSidebar"] [data-testid="stAlert"] * {
    color: #172033 !important;
}

.stApp [data-testid="stSidebar"] textarea {
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
}

@media (max-width: 900px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .hero {
        padding: 24px 20px;
    }

    .hero h1 {
        font-size: 27px;
    }
}
"""

st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def build_job_text(title, required, preferred, years, edu):
    return (
        f"Title: {title}\n"
        f"Required skills: {required}\n"
        f"Preferred skills: {preferred}\n"
        f"Minimum experience: {years} years\n"
        f"Minimum education: {edu}\n"
    )


def collect_resumes(source, uploads=None, pasted=""):
    """
    Always returns:
        (list_of_resumes, list_of_errors)

    This consistent return format prevents the demo-candidate
    tuple-unpacking error.
    """

    resumes = []
    errors = []

    if source == "Use demo candidates":
        try:
            loaded = load_resumes(str(config.DATA_DIR / "resumes"))

            if isinstance(loaded, tuple) and len(loaded) == 2:
                resumes, errors = loaded
            else:
                resumes = loaded or []

            return resumes, errors

        except Exception as exc:
            return [], [f"Demo candidate loading failed: {exc}"]

    if source == "Upload CV files":
        for file in uploads or []:
            try:
                content = extract_resume_text(
                    file.name,
                    file.getvalue()
                )

                if not content or not content.strip():
                    raise ValueError(
                        "No readable text found in this document."
                    )

                resumes.append({
                    "id": Path(file.name).stem,
                    "text": content.strip()
                })

            except Exception as exc:
                errors.append(f"{file.name}: {exc}")

        return resumes, errors

    if source == "Paste resume text":
        if not pasted or not pasted.strip():
            return [], ["Please paste at least one complete resume."]

        try:
            chunks = split_pasted_resumes(pasted)

            if not chunks:
                chunks = [pasted.strip()]

            for index, chunk in enumerate(chunks, start=1):
                if chunk.strip():
                    resumes.append({
                        "id": f"pasted_{index}",
                        "text": chunk.strip()
                    })

        except Exception as exc:
            errors.append(f"Resume text processing failed: {exc}")

        return resumes, errors

    return [], ["Unknown resume input method."]


def create_pipeline(job_text, resumes, slots, top_n, min_score, bias_guard):
    with tempfile.TemporaryDirectory() as temp_dir:
        slots_file = Path(temp_dir) / "slots.json"

        slots_file.write_text(
            json.dumps({"slots": slots}, indent=2),
            encoding="utf-8"
        )

        coordinator = PipelineCoordinator(
            availability_path=slots_file,
            top_n=top_n,
            min_score=float(min_score),
            log_path=(
                os.getenv("HIREFLOW_LOG_PATH")
                or config.LOG_PATH
            ),
            bias_guard=bias_guard,
        )

        return coordinator.run(
            job_text=job_text,
            resumes=resumes
        )


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.markdown("# ✦ HireFlow")
    st.caption("RECRUITMENT INTELLIGENCE PLATFORM")

    st.markdown("---")

    st.markdown("### Pipeline settings")

    top_n = st.slider(
        "Interview slots to fill",
        min_value=1,
        max_value=10,
        value=int(config.TOP_N)
    )

    min_score = st.slider(
        "Shortlist score threshold",
        min_value=0,
        max_value=100,
        value=int(config.MIN_SHORTLIST_SCORE)
    )

    bias_guard = st.toggle(
        "Enable Bias Guard",
        value=True,
        help="Reviews candidate rationales for potentially biased criteria."
    )

    st.markdown("---")

    st.markdown("### Interview availability")

    slots_text = st.text_area(
        "Available slots · one per line",
        value=SAMPLE_SLOTS,
        height=150,
        placeholder="2026-11-20 10:00"
    )

    st.markdown("---")

    try:
        providers = llm.active_providers()

        if providers:
            provider_names = [
                provider.get("name", "Configured provider")
                for provider in providers
            ]

            st.success(
                "AI providers: " + ", ".join(provider_names)
            )
        else:
            st.info(
                "Deterministic scoring is active. "
                "Configure an AI provider for additional AI-generated insights."
            )

    except Exception:
        st.warning("AI provider status could not be loaded.")

    st.markdown("---")
    st.caption("HireFlow · Multi-Agent Recruitment System")
    st.caption("Human review remains essential for hiring decisions.")


# --------------------------------------------------
# HERO
# --------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">
            ✦ Agentic Talent Operations
        </div>
        <h1>Find the right talent. Faster.</h1>
        <p>
            Screen resumes, discover candidate strengths,
            compare job requirements and coordinate interviews
            in one intelligent recruitment workspace.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# MAIN INPUT WORKSPACE
# --------------------------------------------------

st.markdown(
    """
    <div class="section-card">
        <div class="section-head">
            Your screening workspace
        </div>
        <div class="section-sub">
            Configure the role, add candidate CVs,
            and run the multi-agent evaluation pipeline.
        </div>
    """,
    unsafe_allow_html=True
)

left, right = st.columns([1, 1], gap="large")

with left:

    st.markdown(
        """
        <div class="section-head">
            <span class="step">01</span>
            Role requirements
        </div>
        """,
        unsafe_allow_html=True
    )

    title = st.text_input(
        "Role title",
        value=SAMPLE_JOB["title"],
        placeholder="e.g. Junior Data Analyst"
    )

    required = st.text_input(
        "Must-have skills",
        value=", ".join(SAMPLE_JOB["required_skills"]),
        help="Separate skills using commas."
    )

    preferred = st.text_input(
        "Nice-to-have skills",
        value=", ".join(SAMPLE_JOB["preferred_skills"])
    )

    c1, c2 = st.columns(2)

    years = c1.number_input(
        "Minimum experience · years",
        min_value=0.0,
        max_value=40.0,
        value=float(SAMPLE_JOB["min_experience_years"]),
        step=0.5
    )

    edu_default = config.EDU_NAMES.get(
        SAMPLE_JOB["min_education_level"],
        "bachelor"
    )

    edu = c2.selectbox(
        "Minimum education",
        EDU_OPTIONS,
        index=(
            EDU_OPTIONS.index(edu_default)
            if edu_default in EDU_OPTIONS
            else 1
        )
    )


with right:

    st.markdown(
        """
        <div class="section-head">
            <span class="step">02</span>
            Candidate resumes
        </div>
        """,
        unsafe_allow_html=True
    )

    source = st.radio(
        "Choose input method",
        [
            "Upload CV files",
            "Paste resume text",
            "Use demo candidates"
        ],
        horizontal=True
    )

    uploads = None
    pasted = ""

    if source == "Upload CV files":

        uploads = st.file_uploader(
            "Drop CVs here or browse files",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            help=(
                "Supports text-based PDF, DOCX and TXT files. "
                "Scanned PDFs require OCR."
            )
        )

        st.markdown(
            """
            <div class="upload-hint">
                <b>Supported formats:</b> PDF · DOCX · TXT
                <br>
                Upload multiple candidates together.
                Each file is processed separately.
            </div>
            """,
            unsafe_allow_html=True
        )

        if uploads:
            st.success(
                f"{len(uploads)} resume file(s) selected."
            )

    elif source == "Paste resume text":

        pasted = st.text_area(
            "Paste the complete CV",
            height=230,
            placeholder=(
                "Paste a complete resume here.\n\n"
                "For multiple resumes, put --- on a separate "
                "line between each CV."
            )
        )

        st.caption(
            "One complete CV is automatically treated as one candidate. "
            "Use --- to separate multiple CVs."
        )

    else:

        st.info(
            "Load the eight included demo profiles to explore "
            "candidate ranking, score breakdowns, fairness review "
            "and interview scheduling."
        )


st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------
# ANALYSIS BUTTON
# --------------------------------------------------

run_col, note_col = st.columns(
    [1, 3],
    vertical_alignment="center"
)

with run_col:
    run = st.button(
        "✦ Analyze candidates",
        type="primary",
        use_container_width=True
    )

with note_col:
    st.markdown(
        """
        <div class="small-note">
            Evidence-based scoring. Missing candidate information
            is flagged for human review rather than fabricated.
        </div>
        """,
        unsafe_allow_html=True
    )


# --------------------------------------------------
# EXECUTE MULTI-AGENT PIPELINE
# --------------------------------------------------

if run:

    st.session_state.pop("pool", None)

    if not title.strip():
        st.error("Please enter a job role title.")

    elif not required.strip():
        st.error("Please enter at least one must-have skill.")

    else:

        resumes, errors = collect_resumes(
            source,
            uploads,
            pasted
        )

        for error in errors:
            st.error(error)

        slots = [
            slot.strip()
            for slot in slots_text.splitlines()
            if slot.strip()
        ]

        if not resumes:
            st.error(
                "No readable resumes found. "
                "Upload CV files, paste resume text or select demo candidates."
            )

        else:

            st.info(
                f"Preparing to analyze {len(resumes)} candidate resume(s)."
            )

            job_text = build_job_text(
                title,
                required,
                preferred,
                years,
                edu
            )

            try:

                with st.spinner(
                    "Running Parser, Matcher, Ranker, Bias Guard "
                    "and Scheduling agents..."
                ):

                    pool = create_pipeline(
                        job_text=job_text,
                        resumes=resumes,
                        slots=slots,
                        top_n=top_n,
                        min_score=min_score,
                        bias_guard=bias_guard
                    )

                    st.session_state["pool"] = pool
                    st.session_state["role_title"] = title
                    st.session_state["input_count"] = len(resumes)

                st.success(
                    "Candidate screening completed successfully!"
                )

            except Exception as exc:
                st.error(
                    "The screening pipeline encountered an error."
                )
                st.exception(exc)


# --------------------------------------------------
# RESULTS DASHBOARD
# --------------------------------------------------

pool = st.session_state.get("pool")


if pool:

    candidates = pool.all()

    ranked = sorted(
        [candidate for candidate in candidates if candidate.rank],
        key=lambda candidate: candidate.rank
    )

    st.markdown("---")

    st.markdown("## Screening overview")

    st.caption(
        f"Role: {st.session_state.get('role_title', 'Recruitment role')}"
    )

    metrics = st.columns(5)

    metrics[0].metric(
        "CVs analyzed",
        len(candidates)
    )

    metrics[1].metric(
        "Shortlisted",
        len(ranked)
    )

    metrics[2].metric(
        "Interviews booked",
        sum(
            candidate.status == "scheduled"
            for candidate in candidates
        )
    )

    metrics[3].metric(
        "Manual review",
        sum(
            candidate.status == "needs_review"
            for candidate in candidates
        )
    )

    metrics[4].metric(
        "Bias flags",
        len(pool.bias_report)
    )

    records = pool.records()

    (
        tab_short,
        tab_db,
        tab_insights,
        tab_break,
        tab_trace,
        tab_bias,
        tab_log
    ) = st.tabs(
        [
            "✦ Candidate shortlist",
            "Candidate database",
            "Candidate insights",
            "Score evidence",
            "Agent activity",
            "Fairness review",
            "Run log"
        ]
    )


    # ----------------------------------------------
    # SHORTLIST
    # ----------------------------------------------

    with tab_short:

        st.markdown("### Ranked candidate pipeline")

        st.caption(
            "Candidates are ordered by evidence-based fit. "
            "Scheduling status is separate from the match score."
        )

        ordered = ranked + [
            candidate
            for candidate in candidates
            if not candidate.rank
        ]

        table = pd.DataFrame({
            "Rank": [
                candidate.rank if candidate.rank else "—"
                for candidate in ordered
            ],
            "Candidate": [
                candidate.name
                for candidate in ordered
            ],
            "Match score": [
                f"{candidate.score:.1f}%"
                if candidate.rank else "—"
                for candidate in ordered
            ],
            "Decision": [
                STATUS_TEXT.get(
                    candidate.status,
                    candidate.status
                )
                for candidate in ordered
            ],
            "Interview slot": [
                candidate.slot or "—"
                for candidate in ordered
            ],
            "Evidence summary": [
                candidate.rationale or "No rationale available"
                for candidate in ordered
            ]
        })

        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Evidence summary": st.column_config.TextColumn(
                    width="large"
                ),
                "Candidate": st.column_config.TextColumn(
                    width="medium"
                )
            }
        )

        csv = table.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "Download shortlist · CSV",
            csv,
            file_name="hireflow_shortlist.csv",
            mime="text/csv"
        )


    # ----------------------------------------------
    # CANDIDATE DATABASE + REPORTS
    # ----------------------------------------------

    with tab_db:

        st.markdown("### Candidate database")

        st.caption(
            "Every field below is read from the resume text only. "
            "Blank means the resume did not state it."
        )

        db_rows = report_tools.database_rows(records)

        st.dataframe(
            pd.DataFrame(db_rows),
            hide_index=True,
            use_container_width=True
        )

        job_info = pool.job

        d1, d2, d3, d4 = st.columns(4)

        d1.download_button(
            "Candidate database · CSV",
            report_tools.to_csv_bytes(db_rows),
            file_name="hireflow_candidates.csv",
            mime="text/csv",
            use_container_width=True
        )

        d2.download_button(
            "Full workbook · Excel",
            report_tools.to_excel_bytes(records, job_info),
            file_name="hireflow_candidates.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )

        d3.download_button(
            "Recruitment report · Markdown",
            (pool.report_md or report_tools.recruitment_report_md(records, job_info)).encode("utf-8"),
            file_name="hireflow_recruitment_report.md",
            mime="text/markdown",
            use_container_width=True
        )

        d4.download_button(
            "Structured data · JSON",
            report_tools.to_json_bytes(records, job_info),
            file_name="hireflow_candidates.json",
            mime="application/json",
            use_container_width=True
        )


    # ----------------------------------------------
    # CANDIDATE INSIGHTS
    # ----------------------------------------------

    with tab_insights:

        st.markdown("### Candidate profile intelligence")

        candidate_map = {
            f"{candidate.name} · {candidate.cid}": candidate
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    item.rank is None,
                    item.rank or 999
                )
            )
        }

        if candidate_map:

            selected = st.selectbox(
                "Select a candidate",
                list(candidate_map.keys()),
                key="insight_candidate"
            )

            candidate = candidate_map[selected]

            a, b, c, d = st.columns(4)

            a.metric(
                "Match score",
                f"{candidate.score:.1f}%"
            )

            b.metric(
                "Experience",
                (
                    f"{candidate.experience_years:g} yrs"
                    if candidate.experience_years >= 0
                    else "Not stated"
                )
            )

            c.metric(
                "Education",
                candidate.education_label.title()
            )

            d.metric(
                "Profile quality",
                "Complete" if candidate.complete else "Needs review"
            )

            st.markdown("#### Skills detected")

            if candidate.skills:
                st.write(
                    " · ".join(
                        pretty_skill(skill)
                        for skill in candidate.skills
                    )
                )
            else:
                st.warning(
                    "No recognizable skills were extracted. "
                    "Review the original resume."
                )

            if candidate.skills_from_projects:
                st.caption(
                    "Also named in projects or experience (not in the Skills section): "
                    + ", ".join(candidate.skills_from_projects)
                )

            if candidate.issues:
                st.warning(
                    "Profile gaps: "
                    + " · ".join(candidate.issues)
                )

            if candidate.notes:
                st.info(
                    "Needs human verification: "
                    + " · ".join(candidate.notes)
                )

            info_left, info_right = st.columns(2)

            with info_left:

                st.markdown("#### Contact")

                for label, key in (
                    ("Email", "email"),
                    ("Phone", "phone"),
                    ("LinkedIn", "linkedin"),
                    ("GitHub", "github"),
                ):
                    st.write(
                        f"**{label}:** "
                        f"{candidate.contact.get(key) or 'not stated'}"
                    )

                st.markdown("#### Education")

                st.write(f"**Degree:** {candidate.degree or candidate.education_label}")
                st.write(f"**University:** {candidate.university or 'not stated'}")
                st.write(
                    "**CGPA:** "
                    + (
                        f"{candidate.cgpa:g}"
                        if candidate.cgpa is not None
                        else "not stated"
                    )
                )

                st.markdown("#### Experience")

                if candidate.employment_years is None and not candidate.internship_months:
                    st.write(
                        "No formal employment or internship stated. "
                        "Projects and training are scored separately."
                    )
                else:
                    if candidate.employment_years is not None:
                        st.write(f"**Employment:** {candidate.employment_years:g} years")
                    if candidate.internship_months:
                        st.write(f"**Internships:** {candidate.internship_months} months")

            with info_right:

                st.markdown("#### Projects")

                if candidate.projects:
                    for project in candidate.projects:
                        st.write(
                            f"**{project['name']}** · "
                            + (", ".join(project["skills"]) or "no skills named")
                        )
                else:
                    st.caption("No projects listed.")

                st.markdown("#### Certifications and training")

                if candidate.certifications:
                    for item in candidate.certifications:
                        st.write(f"- {item}")
                else:
                    st.caption("None listed.")

                st.markdown("#### Achievements")

                if candidate.achievements:
                    for item in candidate.achievements:
                        st.write(f"- {item}")
                else:
                    st.caption("None listed.")

            st.markdown("#### Role fit summary")

            st.write(
                candidate.rationale or "No rationale available."
            )

            st.download_button(
                "Download candidate report · Markdown",
                report_tools.candidate_report_md(candidate.to_record()).encode("utf-8"),
                file_name=f"{candidate.cid}_report.md",
                mime="text/markdown",
                key=f"report_{candidate.cid}"
            )

            with st.expander("View extracted resume text"):
                st.text(candidate.raw_text or "No resume text available.")

        else:
            st.info("No candidate profiles are available.")


    # ----------------------------------------------
    # SCORE BREAKDOWN
    # ----------------------------------------------

    with tab_break:

        st.markdown("### Requirement score evidence")

        candidate_map = {
            f"{candidate.name} · {candidate.cid}": candidate
            for candidate in candidates
        }

        if candidate_map:

            selected_break = st.selectbox(
                "Candidate for evidence review",
                list(candidate_map.keys()),
                key="break_candidate"
            )

            candidate = candidate_map[selected_break]

            if not candidate.complete:
                st.warning(
                    "Incomplete profile: "
                    + "; ".join(candidate.issues)
                    + ". Missing fields are not assumed."
                )

            st.metric(
                "Requirement match score",
                f"{candidate.score:.1f} / 100"
            )

            breakdown = pd.DataFrame({
                "Requirement": [
                    item["requirement"]
                    for item in candidate.breakdown
                ],
                "Evidence met": [
                    "Yes" if item["met"] else "No"
                    for item in candidate.breakdown
                ],
                "Points earned": [
                    item["points"]
                    for item in candidate.breakdown
                ],
                "Maximum": [
                    item["max"]
                    for item in candidate.breakdown
                ],
                "Status": [
                    item.get("status", "")
                    for item in candidate.breakdown
                ],
                "Evidence": [
                    item.get("evidence", "")
                    for item in candidate.breakdown
                ]
            })

            st.dataframe(
                breakdown,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Evidence": st.column_config.TextColumn(width="large"),
                    "Requirement": st.column_config.TextColumn(width="large"),
                }
            )

            st.caption(
                "Status 'not_stated' means the resume says nothing on this "
                "point (needs human verification); 'not_met' means the resume "
                "shows the requirement is not satisfied."
            )

        else:
            st.info("No scoring evidence available.")


    # ----------------------------------------------
    # AGENT ACTIVITY
    # ----------------------------------------------

    with tab_trace:

        st.markdown("### Multi-agent execution trace")

        events = [
            event
            for event in pool.log.entries
            if event["event"] != "tool_call"
        ]

        if events:

            event_table = pd.DataFrame({
                "Time": [
                    event["ts"][11:]
                    for event in events
                ],
                "Agent": [
                    event["agent"]
                    for event in events
                ],
                "Event": [
                    event["event"]
                    for event in events
                ],
                "Details": [
                    event["detail"]
                    for event in events
                ]
            })

            st.dataframe(
                event_table,
                hide_index=True,
                use_container_width=True
            )

        else:
            st.info("No agent activity events were recorded.")

        calls = Counter(
            event["agent"]
            for event in pool.log.entries
            if event["event"] == "tool_call"
        )

        st.markdown("#### Tool execution summary")

        if calls:
            for agent, count in calls.items():
                st.write(f"**{agent}:** {count} tool call(s)")
        else:
            st.caption("No tool calls were recorded.")


    # ----------------------------------------------
    # FAIRNESS REVIEW
    # ----------------------------------------------

    with tab_bias:

        st.markdown("### Fairness and bias review")

        if not pool.bias_report:

            if bias_guard:
                st.success(
                    "No protected-attribute leakage was detected "
                    "in the reviewed rationales."
                )
            else:
                st.info(
                    "Fairness review was disabled for this run."
                )

        else:

            for item in pool.bias_report:

                candidate = pool.candidates.get(item["cid"])

                candidate_name = (
                    candidate.name
                    if candidate
                    else item["cid"]
                )

                with st.expander(
                    f"Review: {candidate_name}",
                    expanded=True
                ):

                    st.error(
                        "Potential fairness flags: "
                        + ", ".join(item["flags"])
                    )

                    st.markdown("**Original rationale**")

                    st.write(item["original"])

                    st.markdown("**Sanitized rationale**")

                    st.write(item["replaced_with"])

        st.caption(
            "Automated fairness checks are safeguards, not proof "
            "that a hiring process is free from bias. Human review is required."
        )


    # ----------------------------------------------
    # RUN LOG
    # ----------------------------------------------

    with tab_log:

        st.markdown("### Pipeline execution log")

        lines = [
            (
                f"{event['ts']} | "
                f"{event['agent']} | "
                f"{event['event']} | "
                f"{event['detail']}"
            )
            for event in pool.log.entries
        ]

        st.caption(
            f"Run {pool.log.run_id} · {len(lines)} events"
        )

        st.code(
            "\n".join(lines) if lines else "No log events.",
            language="text"
        )

        st.download_button(
            "Download run log",
            "\n".join(lines),
            file_name=f"hireflow_run_{pool.log.run_id}.txt",
            mime="text/plain"
        )


else:

    # ----------------------------------------------
    # EMPTY DASHBOARD
    # ----------------------------------------------

    st.markdown(
        """
        <div class="section-card">
            <div class="section-head">
                What happens when you analyze?
            </div>
            <div class="section-sub">
                A coordinated and explainable recruitment workflow,
                from raw resume to interview-ready shortlist.
            </div>
            <div style="
                display:flex;
                gap:14px;
                flex-wrap:wrap;
                color:#34466d;
                font-size:13px;
                font-weight:600;
            ">
                <span>① Resume parsing</span>
                <span>→</span>
                <span>② Skill matching</span>
                <span>→</span>
                <span>③ Candidate ranking</span>
                <span>→</span>
                <span>④ Fairness review</span>
                <span>→</span>
                <span>⑤ Interview scheduling</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Platform capabilities")

    feature_columns = st.columns(3)

    features = [
        ("📄", "Smart resume ingestion", "Upload PDF, DOCX and TXT resumes or paste CV text."),
        ("🤖", "Multi-agent pipeline", "Parser, Matcher, Ranker, Bias Guard and Scheduler agents share one candidate pool."),
        ("🔎", "Evidence-backed scoring", "Every awarded point cites the resume text it came from. Missing data is flagged, never guessed."),
        ("🗂️", "Candidate database", "Contacts, education, skills, projects, certificates and achievements for every CV."),
        ("⚖️", "Fairness review", "Rationales are checked for protected attributes before anything reaches a recruiter."),
        ("📅", "Interview scheduling", "Top candidates are booked into your free slots; overflow is waitlisted."),
        ("📥", "Downloadable reports", "Export the candidate database, score evidence and full recruitment report."),
    ]

    for index, (icon, heading, text) in enumerate(features):
        with feature_columns[index % 3]:
            st.markdown(
                f"""
                <div class="section-card">
                    <div class="section-head">{icon} {heading}</div>
                    <div class="section-sub">{text}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
