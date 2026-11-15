# HireFlow: Recruitment Screening and Interview Scheduling Pipeline

CSE476 Agentic AI and Intelligent Automation, Project 2 (Group 4). Built on **Microsoft Semantic Kernel** (Python).

Input: a job description and a folder of resumes. Output: a ranked shortlist with a one-line rationale per candidate and an interview slot for each top candidate.

## Agent roster (one module each, `hireflow/agents/`)

| Agent | Role | Tools (plain Python, `hireflow/tools/`) |
|---|---|---|
| Parser Agent | Resume text to structured profile | `extract_name`, `extract_skills`, `extract_experience_years`, `extract_education` |
| Matcher Agent | Score each profile against named requirements | `compute_skill_overlap`, `score_experience`, `score_education`, `build_score_breakdown`, `total_score` |
| Ranker Agent | Order candidates, write a one-line rationale | `sort_candidates`, `format_rationale`, `build_rationale_prompt` |
| Bias Guard (group-of-3) | Check ranking uses no protected attributes | `check_rationale_for_protected`, `check_scoring_basis`, `build_safe_rationale` |
| Scheduler Agent | Shortlist top N and book slots | `select_shortlist`, `get_available_slots`, `book_slot` |
| Pipeline Coordinator | Run stages in order, pass the pool on | `load_job_description`, `load_resumes`, `run_stage`, `build_final_report` |

## Architecture and why it fits

A **sequential pipeline**: Parser, Matcher, Ranker, Bias Guard, Scheduler (diagram: `docs/architecture.png`). Screening is naturally staged, because each step needs the previous step's output (you cannot score before parsing or schedule before ranking). A pipeline keeps the flow deterministic, easy to log and easy to test.

Each agent owns a Semantic Kernel `Kernel` with one plugin holding its tools, and every call goes through `kernel.invoke`. The Coordinator calls stages in a fixed order in code. The model never chooses which tool runs.

## What the memory holds

The **shared candidate pool** (`hireflow/shared_state.py`) is one object every agent reads and writes. Per candidate it carries skills, experience, education, completeness flags, score and per-requirement breakdown, rank, rationale, bias flags, interview slot and status. The **run log** (`logs/run_log.txt`) is append-only: it is only ever opened in append mode, and a test checks earlier lines are never changed.

## Scoring (deterministic, 100 points)

Skills 60 (80% required, 20% preferred), experience 25, education 15. Every point is tied to a named requirement, for example `Required skill: SQL +12/12`, so each score can be justified line by line.

## The model's limited job

Scores, ranking, slots and decisions are plain Python. A model is used only to polish the one-line rationale, through the fallback chain **Gemini, Groq, Ollama (local), template sentence** (`hireflow/llm.py`). With no keys, or with `HIREFLOW_LLM=off`, the fact-only template is used and the pipeline still completes.

## Honest failures handled

1. **Resume with no Skills section** (`resume_06`): the Parser marks it incomplete and does not guess skills from the summary text. It is not ranked or scheduled, and appears under "needs manual review".
2. **Model unavailable, slow or off-topic**: the reply is validated (non-empty, short, mentions the candidate). If it fails, the template sentence is used and `llm_fallback` is logged. Scores and order are unaffected.
3. **More shortlisted candidates than free slots**: the extras are marked `waitlisted` instead of being given a made-up slot.

## Requirements

- **Python 3.10 – 3.13** (check with `python --version`). Newer versions such as 3.14 may fail to install `semantic-kernel`'s dependencies.
- Internet access for the first `pip install`.
- No API key is needed. Without one, a fact-only template sentence is used and the pipeline still completes.

## Setup (virtual environment)

**Quick way**

```bash
# Linux / macOS / Git Bash
./setup.sh            # add "dev" to also install pytest + jupyter: ./setup.sh dev

# Windows (cmd / PowerShell)
setup.bat             # or: setup.bat dev
```

**Manual way**

```bash
cd hireflow

# 1. create the virtual environment
python -m venv .venv            # on Linux/macOS you may need: python3 -m venv .venv

# 2. activate it
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows (cmd or PowerShell)

# 3. install dependencies INTO the venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt   # optional: tests, notebook, diagram

# 4. optional: API keys for nicer rationale sentences
cp .env.example .env            # Windows: copy .env.example .env
```

`requirements.txt` holds only what is needed to run the app. `requirements-dev.txt` adds pytest, jupyter and matplotlib, which are large and only needed for tests and the notebook.

## Run it

Always activate the venv first (you should see `(.venv)` in your prompt).

```bash
streamlit run app.py                    # web frontend, opens at http://localhost:8501
python main.py                          # command line: prints the shortlist, appends to logs/run_log.txt
pytest -q                               # tests, no model calls needed (needs requirements-dev.txt)
jupyter notebook notebooks/demo.ipynb   # multi-agent trace (needs requirements-dev.txt)
```

## Optional: model-written rationales

Edit `.env` (never commit it):

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Free key from https://aistudio.google.com/ |
| `GROQ_API_KEY` | Free key from https://console.groq.com/ |
| `OLLAMA_ENABLED=1` | Use a local Ollama model (`ollama pull qwen2.5:3b`) |
| `HIREFLOW_LLM=off` | Never call a model; always use the template sentence |

## Troubleshooting

| Problem | Fix |
|---|---|
| Packages not installing / `No matching distribution found` for `semantic-kernel` | Wrong Python version. Use 3.10 to 3.13: `py -3.12 -m venv .venv` (Windows) or `python3.12 -m venv .venv`. Delete the old `.venv` first. |
| Packages install but `ModuleNotFoundError` when running | The venv is not active, or `pip` belongs to another Python. Activate it and install with `python -m pip install -r requirements.txt`. |
| `streamlit: command not found` | Same cause. Run `python -m streamlit run app.py`. |
| PowerShell: "running scripts is disabled" on activate | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use cmd and `.venv\Scripts\activate.bat`. |
| Install is very slow or times out | Install core first (skip dev). Retry with `python -m pip install --default-timeout 120 -r requirements.txt`. |
| Behind a proxy / corporate network | Set `HTTPS_PROXY`, or `pip install --proxy http://host:port -r requirements.txt`. |

## Project layout

```
app.py                Streamlit frontend
main.py               command-line runner
hireflow/             agents/, tools/, config, llm, shared state
data/                 sample job description, resumes, availability
tests/                pytest suite
notebooks/demo.ipynb  demo trace
docs/                 architecture diagram
logs/run_log.txt      append-only run log
requirements.txt      core dependencies
requirements-dev.txt  tests, notebook, diagram extras
```

## Frontend (`app.py`, Streamlit)

Enter a job title, required and preferred skills, minimum experience and education; choose sample resumes, upload `.txt` files, or paste resumes separated by `---`; set the number of interview slots and the free slots; press **Run pipeline**. Tabs show the shortlist, a per-requirement score breakdown for any candidate, the agent trace, the Bias Guard report and the run log (also appended to `logs/run_log.txt`).

## Tests (`tests/test_hireflow.py`)

Normal batch and slot booking; incomplete resume; more candidates than slots; bias guard catching a leaking rationale; model failure fallback; unusable model reply; append-only log; tool-level checks; roster rule (4+ agents, 2+ tools each). `tests/test_frontend.py` drives the web app with Streamlit's AppTest (sample run, pasted resumes, empty-input errors, in-memory pipeline inputs).
