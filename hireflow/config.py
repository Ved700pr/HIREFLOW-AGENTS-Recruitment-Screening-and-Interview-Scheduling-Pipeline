"""Central settings for HireFlow. Change numbers here, not inside the agents."""
import os
from pathlib import Path

try:  # optional: load API keys from a .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_PATH = ROOT / "logs" / "run_log.txt"

# ---- Scoring (points out of 100) -------------------------------------------
WEIGHTS = {
    "required": 40,        # required technical skills
    "preferred": 15,       # preferred skills
    "projects": 15,        # projects that use skills the job asks for
    "experience": 15,      # employment (internships count at half value)
    "education": 10,
    "certifications": 5,   # certifications / training (3) + achievements (2)
}
CERT_POINTS, ACHIEVEMENT_POINTS = 3.0, 2.0   # split of the 5 "certifications and achievements" points
INTERNSHIP_CREDIT = 0.5      # an internship month counts as half an employment month
SKILL_ONLY_IN_PROJECTS_CREDIT = 0.5   # a job skill shown only in projects/experience (not listed) earns half credit
PROJECTS_FOR_FULL_CREDIT = 2          # relevant projects needed for the full project points

# ---- Shortlisting ----------------------------------------------------------
TOP_N = 3                    # how many candidates get an interview slot
MIN_SHORTLIST_SCORE = 40.0   # below this a candidate is never shortlisted

# ---- Education levels ------------------------------------------------------
EDU_LEVELS = {"none": 0, "diploma": 1, "bachelor": 2, "master": 3, "phd": 4}
EDU_NAMES = {v: k for k, v in EDU_LEVELS.items()}

# Sentinel meaning "the resume did not state this" (never guessed).
NOT_STATED = -1.0

# ---- LLM fallback chain ----------------------------------------------------
# HIREFLOW_LLM=off  -> never call a model, always use the template sentence.
LLM_TIMEOUT_SECONDS = float(os.getenv("HIREFLOW_LLM_TIMEOUT", "20"))

# All three speak the OpenAI chat format, so Semantic Kernel's
# OpenAIChatCompletion connector can talk to each of them.
LLM_PROVIDERS = [
    {
        "name": "gemini",
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.5-flash",
    },
    {
        "name": "groq",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
    },
    {
        "name": "ollama",
        "key_env": None,  # local, no key; enabled with OLLAMA_ENABLED=1
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "model_env": "OLLAMA_MODEL",
        "default_model": "qwen2.5:3b",
    },
]
