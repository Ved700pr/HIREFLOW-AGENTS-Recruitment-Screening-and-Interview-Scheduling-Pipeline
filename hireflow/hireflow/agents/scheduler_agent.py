"""Scheduler Agent - assigns interview slots to the top candidates."""
from hireflow import config
from hireflow.agents.base import BaseAgent
from hireflow.tools.scheduler_tools import book_slot, get_available_slots, select_shortlist


class SchedulerAgent(BaseAgent):
    name = "scheduler_agent"
    role = "Shortlist the top candidates and book an interview slot for each from the availability file."
    tools = [select_shortlist, get_available_slots, book_slot]

    def __init__(self, availability_path, top_n: int = config.TOP_N, min_score: float = config.MIN_SHORTLIST_SCORE):
        super().__init__()
        self.availability_path = str(availability_path)
        self.top_n = top_n
        self.min_score = min_score

    def run(self, pool) -> None:
        self.log = pool.log
        ranked = sorted([c for c in pool.all() if c.rank is not None], key=lambda c: c.rank)
        shortlist = list(
            self.call("select_shortlist", ranked_rows=[c.to_row(pool.job) for c in ranked], top_n=self.top_n, min_score=self.min_score)
        )
        free = list(self.call("get_available_slots", path=self.availability_path) or [])
        self.say("slots_loaded", f"{len(free)} free slots, shortlisting up to {self.top_n}")

        for cand in ranked:
            if cand.cid not in shortlist:
                cand.status = "not_shortlisted"
                self.say("not_shortlisted", f"{cand.cid} {cand.name} (rank {cand.rank}, score {cand.score:g})")
                continue
            booking = self.call("book_slot", cand.cid, free_slots=free, candidate_id=cand.cid)
            free = list(booking["remaining"] or [])
            if booking["slot"]:
                cand.slot, cand.status = booking["slot"], "scheduled"
                self.say("slot_booked", f"{cand.cid} {cand.name} -> {cand.slot}")
            else:
                cand.status = "waitlisted"
                self.say("waitlisted", f"{cand.cid} {cand.name}: shortlisted but no free slot left")
