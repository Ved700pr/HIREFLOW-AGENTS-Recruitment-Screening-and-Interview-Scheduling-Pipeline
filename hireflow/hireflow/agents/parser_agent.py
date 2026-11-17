"""Parser Agent - turns each raw resume into a structured candidate profile in the shared pool.

Extracts contact details, education, skills (by category), projects, certifications, achievements and
employment / internships separately. Rules first; an optional LLM pass fills sections the rules missed,
and an item is kept only if it appears verbatim in the resume. Never guesses a missing field.
"""
from hireflow import config
from hireflow.agents.base import BaseAgent
from hireflow.tools.parser_tools import extract_name
from hireflow.tools.profile_tools import enrich_missing_sections, extract_profile


class ParserAgent(BaseAgent):
    name = "parser_agent"
    role = "Convert each resume into a structured profile: contact, education, skills, projects, certificates, achievements, experience."
    tools = [extract_name, extract_profile, enrich_missing_sections]

    def run(self, pool) -> None:
        self.log = pool.log
        for cand in pool.all():
            try:
                cand.name = self.call("extract_name", cand.cid, text=cand.raw_text)
                profile = self.call("extract_profile", cand.cid, text=cand.raw_text)
                self._apply(cand, profile)
                if not (cand.projects and cand.certifications and cand.achievements):
                    self._enrich(cand)
                self._check_gaps(cand)
                cand.status = "parsed"
            except Exception as exc:  # one bad resume must not stop the batch
                cand.complete = False
                cand.issues.append(f"parse error: {exc}")
                cand.status = "parsed"
                self.say("parse_failed", f"{cand.cid}: {exc!r}")

            if cand.complete:
                self.say("parsed", f"{cand.cid} {cand.name}: {len(cand.skills)} skills, {len(cand.projects)} projects, {len(cand.certifications)} certs, "
                                   f"{'exp not stated' if cand.employment_years is None else f'{cand.employment_years:g} yrs'}, {cand.education_label}")
            else:
                self.say("incomplete_profile", f"{cand.cid} {cand.name}: {'; '.join(cand.issues)} - marked incomplete, nothing guessed")

    @staticmethod
    def _apply(cand, p: dict) -> None:
        cand.contact = p["contact"]
        cand.degree, cand.university, cand.cgpa, cand.graduation_year = p["degree"], p["university"], p["cgpa"], p["grad_year"]
        cand.education_label, cand.education_level = p["education_label"], int(p["education_level"])
        cand.skills, cand.skill_categories, cand.skills_from_projects = list(p["skills"]), p["skill_categories"], list(p["context_skills"])
        cand.projects, cand.certifications, cand.achievements = p["projects"], p["certifications"], p["achievements"]
        cand.employment, cand.internships = p["employment"], p["internships"]
        cand.internship_months, cand.experience_basis = int(p["internship_months"]), p["experience_basis"]
        years = p["employment_years"]
        cand.employment_years = None if years == config.NOT_STATED else float(years)
        cand.experience_years = config.NOT_STATED if cand.employment_years is None else cand.employment_years

    def _enrich(self, cand) -> None:
        """Optional AI pass for sections the rules could not find (verbatim-checked, so it cannot invent evidence)."""
        found = self.call("enrich_missing_sections", cand.cid, text=cand.raw_text)
        if not found or not found.get("source"):
            return
        names = {p["name"].lower() for p in cand.projects}
        added = 0
        for proj in found["projects"]:
            if proj["name"].lower() not in names:
                cand.projects.append(proj)
                added += 1
        for key in ("certifications", "achievements"):
            current = getattr(cand, key)
            for item in found[key]:
                if item not in current:
                    current.append(item)
                    added += 1
        if added:
            cand.enrichment_source = found["source"]
            cand.notes.append(f"{added} item(s) filled by AI ({found['source']}) and verified verbatim against the resume")
            self.say("ai_enriched", f"{cand.cid}: {added} item(s) via {found['source']}")

    @staticmethod
    def _check_gaps(cand) -> None:
        """Blocking gaps go to `issues` (candidate is left for manual review); other gaps are `notes` for human verification."""
        cand.issues, cand.notes = [], list(cand.notes)
        if not cand.skills:
            cand.issues.append("no Skills section found")
        if cand.employment_years is None and not cand.internship_months:
            cand.notes.append("no formal employment or internship stated (projects and training are scored separately)")
        if cand.education_level == 0:
            cand.notes.append("education not stated")
        if not cand.contact.get("email") and not cand.contact.get("phone"):
            cand.notes.append("no email or phone found")
        cand.complete = not cand.issues
