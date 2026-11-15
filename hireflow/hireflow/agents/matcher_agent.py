"""Matcher Agent - scores each profile against the NAMED job requirements."""
from hireflow.agents.base import BaseAgent
from hireflow.tools.matcher_tools import (
    build_score_breakdown,
    compute_skill_overlap,
    score_education,
    score_experience,
    total_score,
)


class MatcherAgent(BaseAgent):
    name = "matcher_agent"
    role = "Score each candidate out of 100 and justify every point against a named requirement."
    tools = [compute_skill_overlap, score_experience, score_education, build_score_breakdown, total_score]

    def run(self, pool) -> None:
        self.log = pool.log
        job = pool.job
        for cand in pool.all():
            cand.overlap = self.call(
                "compute_skill_overlap", cand.cid,
                candidate_skills=cand.skills,
                required=job["required_skills"],
                preferred=job["preferred_skills"],
            )
            exp = self.call("score_experience", cand.cid, years=cand.experience_years, min_years=job["min_experience_years"])
            edu = self.call("score_education", cand.cid, level=cand.education_level, min_level=job["min_education_level"])
            cand.breakdown = list(self.call("build_score_breakdown", cand.cid, overlap=cand.overlap, experience=exp, education=edu))
            cand.score = float(self.call("total_score", cand.cid, breakdown=cand.breakdown))
            cand.status = "scored"

            why = "; ".join(f"{r['requirement']} {'+' if r['met'] else ''}{r['points']:g}/{r['max']:g}" for r in cand.breakdown)
            self.say("scored", f"{cand.cid} {cand.name} = {cand.score:g}/100 :: {why}")
