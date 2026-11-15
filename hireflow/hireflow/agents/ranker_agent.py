"""Ranker Agent - orders candidates and writes a one-line rationale for each.

The ORDER is deterministic (tool). The model only polishes the sentence, and
a fact-only template is used whenever the model is unavailable or returns bad text.
"""
from hireflow import llm
from hireflow.agents.base import BaseAgent
from hireflow.tools.ranker_tools import build_rationale_prompt, format_rationale, sort_candidates


class RankerAgent(BaseAgent):
    name = "ranker_agent"
    role = "Rank complete candidates by score and write a one-line rationale per candidate."
    tools = [sort_candidates, format_rationale, build_rationale_prompt]

    def run(self, pool) -> None:
        self.log = pool.log
        order = self.call("sort_candidates", rows=pool.rows())
        ranked_ids, review_ids = list(order["ranked"]), list(order["needs_review"])

        for position, cid in enumerate(ranked_ids, start=1):
            cand = pool.candidates[cid]
            row = cand.to_row(pool.job)
            template = self.call("format_rationale", cid, row=row)
            prompt = self.call("build_rationale_prompt", cid, row=row)
            text, source = llm.generate_text(prompt, fallback=template, must_contain=(cand.name.split()[0],))
            cand.rank, cand.rationale, cand.rationale_source, cand.status = position, text, source, "ranked"
            self.say("ranked", f"#{position} {cand.name} ({cand.score:g}) rationale via {source}")
            if source == "template":
                self.say("llm_fallback", f"{cid}: no usable model reply, fact-only template used")

        for cid in review_ids:
            cand = pool.candidates[cid]
            cand.rationale = self.call("format_rationale", cid, row=cand.to_row(pool.job))
            cand.rationale_source, cand.status = "template", "needs_review"
            self.say("needs_review", f"{cid} {cand.name}: left unranked ({'; '.join(cand.issues)})")
