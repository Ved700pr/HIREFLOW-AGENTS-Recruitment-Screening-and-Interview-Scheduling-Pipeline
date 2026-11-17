"""Scheduler Agent tools: shortlist selection and interview slot booking."""
import json
from pathlib import Path


def select_shortlist(ranked_rows: list[dict], top_n: int, min_score: float) -> list[str]:
    """Pick the ids of the top-N ranked candidates whose score is at least min_score."""
    chosen = [r["cid"] for r in ranked_rows if r["score"] >= min_score]
    return chosen[: max(top_n, 0)]


def get_available_slots(path: str) -> list[str]:
    """Read the free interview slots from the availability file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(data.get("slots", []))


def book_slot(free_slots: list[str], candidate_id: str) -> dict:
    """Book the earliest free slot. Returns {'candidate': id, 'slot': slot or '', 'remaining': [...]}."""
    if not free_slots:
        return {"candidate": candidate_id, "slot": "", "remaining": []}
    return {"candidate": candidate_id, "slot": free_slots[0], "remaining": free_slots[1:]}
