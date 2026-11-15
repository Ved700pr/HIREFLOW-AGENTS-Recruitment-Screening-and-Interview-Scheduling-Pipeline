"""Regenerate docs/architecture.png:  python docs/make_diagram.py"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).with_name("architecture.png")

INK, MUTED = "#1f2937", "#6b7280"
BLUE, GREEN, AMBER, GRAY = "#dbeafe", "#dcfce7", "#fef3c7", "#f3f4f6"
EDGE = {"b": "#2563eb", "g": "#16a34a", "a": "#d97706", "n": "#9ca3af"}

fig, ax = plt.subplots(figsize=(16, 6.8))
ax.set_xlim(0, 17.6)
ax.set_ylim(0, 7.2)
ax.axis("off")


def box(x, y, w, h, title, sub="", fill=GRAY, edge="n", title_size=11, sub_size=8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fill, ec=EDGE[edge], lw=1.6))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="center", fontsize=title_size, fontweight="bold", color=INK)
    if sub:
        ax.text(x + w / 2, y + (h - 0.55) / 2, sub, ha="center", va="center", fontsize=sub_size, color=MUTED, linespacing=1.5)


def arrow(p, q, color=INK, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=14, lw=1.5, color=color, linestyle=ls, shrinkA=0, shrinkB=0))


ax.text(0.2, 6.95, "HireFlow: sequential multi-agent pipeline", fontsize=15, fontweight="bold", color=INK, va="center")
ax.text(0.2, 6.6, "One Microsoft Semantic Kernel plugin per agent. Every stage reads and writes the same shared candidate pool.", fontsize=9.5, color=MUTED, va="center")

# Stage geometry
W, GAP, X0, Y0, H = 2.3, 0.3, 2.3, 2.55, 2.45
xs = [X0 + i * (W + GAP) for i in range(5)]
right = xs[-1] + W
mid = Y0 + H / 2

# Coordinator band above the stages
box(X0, 5.45, right - X0, 0.9, "Pipeline Coordinator", "load_job_description   |   load_resumes   |   run_stage   |   build_final_report", AMBER, "a", sub_size=8.5)

stages = [
    ("Parser Agent", "extract_name\nextract_skills\nextract_experience_years\nextract_education", BLUE, "b"),
    ("Matcher Agent", "compute_skill_overlap\nscore_experience\nscore_education\nbuild_score_breakdown\ntotal_score", BLUE, "b"),
    ("Ranker Agent", "sort_candidates\nformat_rationale\nbuild_rationale_prompt", BLUE, "b"),
    ("Bias Guard", "check_rationale_for_protected\ncheck_scoring_basis\nbuild_safe_rationale", GREEN, "g"),
    ("Scheduler Agent", "select_shortlist\nget_available_slots\nbook_slot", BLUE, "b"),
]
for x, (title, tools, fill, edge) in zip(xs, stages):
    box(x, Y0, W, H, title, tools, fill, edge, title_size=10.5, sub_size=7.3)
for a, b in zip(xs, xs[1:]):
    arrow((a + W, mid), (b, mid))
for x in xs:
    arrow((x + W / 2, 5.45), (x + W / 2, Y0 + H), color=EDGE["a"], ls="--")

# Input and output on the sides
box(0.2, mid - 0.75, 1.7, 1.5, "Inputs", "job description\n+ resumes (.txt)\n+ availability", GRAY, "n", sub_size=7.8)
box(right + 0.4, mid - 0.75, 1.8, 1.5, "Output", "ranked shortlist\n+ rationale\n+ interview slots", GRAY, "n", sub_size=7.8)
arrow((1.9, mid), (xs[0], mid))
arrow((right, mid), (right + 0.4, mid))

# Shared memory
box(X0, 1.2, right - X0, 0.95, "Shared Candidate Pool (shared memory)",
    "skills, experience, education  ->  score + breakdown  ->  rank + rationale  ->  bias flags  ->  slot + status", GRAY, "n", sub_size=8.5)
for x in xs:
    arrow((x + W / 2, Y0), (x + W / 2, 2.15), style="<|-|>", color=EDGE["n"])

# Supporting boxes
box(X0, 0.1, 5.9, 0.85, "Append-only run log", "every stage, tool call, warning and fallback", GRAY, "n", sub_size=8.5)
box(X0 + 6.2, 0.1, right - (X0 + 6.2), 0.85, "LLM fallback chain (used only by the Ranker)", "Gemini  ->  Groq  ->  Ollama  ->  template sentence", GRAY, "n", sub_size=8.5)

fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print("wrote", OUT)
