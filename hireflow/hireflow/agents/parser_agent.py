"""Parser Agent - turns each raw resume into a structured profile in the shared pool."""
from hireflow import config
from hireflow.agents.base import BaseAgent
from hireflow.tools.parser_tools import (
    extract_education,
    extract_experience_years,
    extract_name,
    extract_skills,
)


class ParserAgent(BaseAgent):
    name = "parser_agent"
    role = "Extract skills, experience and education from each resume. Never guess a missing field."
    tools = [extract_name, extract_skills, extract_experience_years, extract_education]

    def run(self, pool) -> None:
        self.log = pool.log
        for cand in pool.all():
            try:
                cand.name = self.call("extract_name", cand.cid, text=cand.raw_text)
                cand.skills = list(self.call("extract_skills", cand.cid, text=cand.raw_text) or [])
                cand.experience_years = float(self.call("extract_experience_years", cand.cid, text=cand.raw_text))
                edu = self.call("extract_education", cand.cid, text=cand.raw_text)
                cand.education_label, cand.education_level = edu["label"], int(edu["level"])

                cand.issues = []
                if not cand.skills:
                    cand.issues.append("no Skills section found")
                if cand.experience_years == config.NOT_STATED:
                    cand.issues.append("experience not stated")
                if cand.education_level == 0:
                    cand.issues.append("education not stated")
                cand.complete = not cand.issues
                cand.status = "parsed"
            except Exception as exc:  # one bad resume must not stop the batch
                cand.complete = False
                cand.issues.append(f"parse error: {exc}")
                cand.status = "parsed"
                self.say("parse_failed", f"{cand.cid}: {exc!r}")

            if cand.complete:
                self.say("parsed", f"{cand.cid} {cand.name}: {len(cand.skills)} skills, {cand.experience_years:g} yrs, {cand.education_label}")
            else:
                self.say("incomplete_profile", f"{cand.cid} {cand.name}: {'; '.join(cand.issues)} - marked incomplete, nothing guessed")
