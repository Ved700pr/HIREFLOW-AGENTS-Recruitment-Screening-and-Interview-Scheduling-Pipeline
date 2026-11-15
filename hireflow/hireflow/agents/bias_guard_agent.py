"""Bias Guard Agent (group-of-3 add-on) - reviewer between Ranker and Scheduler.

Flags any rationale that mentions a protected attribute, flags any scoring row not
based on skills/experience/education, and replaces a flagged rationale with a fact-only one.
"""
from hireflow.agents.base import BaseAgent
from hireflow.tools.bias_tools import build_safe_rationale, check_rationale_for_protected, check_scoring_basis


class BiasGuardAgent(BaseAgent):
    name = "bias_guard_agent"
    role = "Check that ranking text and scoring use no protected attributes; flag and clean any that do."
    tools = [check_rationale_for_protected, check_scoring_basis, build_safe_rationale]

    def run(self, pool) -> None:
        self.log = pool.log
        for cand in pool.all():
            flags = list(self.call("check_rationale_for_protected", cand.cid, text=cand.rationale) or [])
            bad_rows = list(self.call("check_scoring_basis", cand.cid, breakdown=cand.breakdown) or [])
            flags += [f"scoring_basis:{row}" for row in bad_rows]
            if flags:
                original = cand.rationale
                cand.bias_flags = flags
                cand.rationale = self.call("build_safe_rationale", cand.cid, row=cand.to_row(pool.job))
                pool.bias_report.append({"cid": cand.cid, "flags": flags, "original": original, "replaced_with": cand.rationale})
                self.say("bias_flag", f"{cand.cid} {cand.name}: {flags} - rationale replaced with fact-only text")
            else:
                self.say("bias_clear", f"{cand.cid} {cand.name}: no protected attributes used")
