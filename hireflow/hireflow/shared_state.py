"""Shared memory for the pipeline.

CandidatePool  - ONE object every agent reads and writes (the shared candidate pool).
RunLog         - append-only audit trail (file is only ever opened in "a" mode).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from hireflow import config


class RunLog:
    """Append-only run log. Nothing here ever rewrites or truncates the file."""

    def __init__(self, path: Optional[Path | str] = None, run_id: Optional[str] = None):
        self.path = Path(path) if path else None
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.entries: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.write("system", "run_started", "")

    def write(self, agent: str, event: str, detail: str = "") -> dict:
        ts = datetime.now().isoformat(timespec="seconds")
        entry = {"ts": ts, "run": self.run_id, "agent": agent, "event": event, "detail": str(detail)}
        self.entries.append(entry)
        if self.path:
            line = f"{ts} | {self.run_id} | {agent} | {event} | {detail}".replace("\n", " ")
            with open(self.path, "a", encoding="utf-8") as fh:  # "a" = append only
                fh.write(line + "\n")
        return entry


@dataclass
class Candidate:
    cid: str
    raw_text: str
    name: str = "Unknown"
    # --- written by the Parser ---
    skills: list[str] = field(default_factory=list)
    experience_years: float = config.NOT_STATED   # NOT_STATED (-1) = resume did not say
    education_label: str = "not stated"
    education_level: int = 0
    complete: bool = True
    issues: list[str] = field(default_factory=list)
    # --- written by the Matcher ---
    overlap: dict = field(default_factory=dict)
    breakdown: list[dict] = field(default_factory=list)
    score: float = 0.0
    # --- written by the Ranker ---
    rank: Optional[int] = None
    rationale: str = ""
    rationale_source: str = ""
    # --- written by the Bias Guard ---
    bias_flags: list[str] = field(default_factory=list)
    # --- written by the Scheduler ---
    slot: Optional[str] = None
    status: str = "new"   # new, parsed, scored, ranked, scheduled, waitlisted, not_shortlisted, needs_review

    def to_row(self, job: dict) -> dict:
        """Plain-dict view handed to tools (tools never see the dataclass)."""
        return {
            "cid": self.cid,
            "name": self.name,
            "score": self.score,
            "complete": self.complete,
            "issues": list(self.issues),
            "experience_years": self.experience_years,
            "education_label": self.education_label,
            "overlap": self.overlap,
            "required_count": len(job.get("required_skills", [])),
            "min_years": job.get("min_experience_years", 0.0),
            "breakdown": self.breakdown,
        }


class CandidatePool:
    """The shared object carried through every stage."""

    def __init__(self, job: dict, log: RunLog):
        self.job = job
        self.log = log
        self.candidates: dict[str, Candidate] = {}
        self.bias_report: list[dict] = []
        self.final_report: str = ""

    def add(self, cand: Candidate) -> None:
        self.candidates[cand.cid] = cand

    def all(self) -> list[Candidate]:
        return list(self.candidates.values())

    def rows(self) -> list[dict]:
        return [c.to_row(self.job) for c in self.all()]
