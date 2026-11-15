"""Bias Guard tools: check that ranking text and scoring use no protected attributes."""
import re

from hireflow.tools.ranker_tools import format_rationale

PROTECTED_PATTERNS = {
    "gender": r"\b(male|female|man|woman|men|women|he|she|his|hers?|him|gentleman|lady|boy|girl|mother|father|husband|wife)\b",
    "age": r"\b(age|aged|young|younger|youthful|old|older|elderly|\d{1,2}\s*(?:years?|yrs?)[\s-]*old)\b",
    "marital_or_family": r"\b(married|unmarried|marital|divorced|widowed|pregnan\w*|maternity|children|kids)\b",
    "religion": r"\b(hindu|muslim|christian|sikh|buddhist|jain|jewish|religion|religious)\b",
    "caste_or_ethnicity": r"\b(caste|ethnicity|race|racial|nationality)\b",
    "disability": r"\b(disabled|disability|handicapped)\b",
}

ALLOWED_REQUIREMENT_PREFIXES = ("Required skill:", "Preferred skill:", "Experience:", "Education:")


def check_rationale_for_protected(text: str) -> list[str]:
    """Return 'category:word' for every protected-attribute word found in the text."""
    found = []
    for category, pattern in PROTECTED_PATTERNS.items():
        for match in re.finditer(pattern, text, re.I):
            found.append(f"{category}:{match.group(0).lower()}")
    return found


def check_scoring_basis(breakdown: list[dict]) -> list[str]:
    """Return any scoring rows that are not based on skills, experience or education."""
    return [row["requirement"] for row in breakdown if not row["requirement"].startswith(ALLOWED_REQUIREMENT_PREFIXES)]


def build_safe_rationale(row: dict) -> str:
    """Rebuild a candidate's rationale from facts only (used when a rationale is flagged)."""
    return format_rationale(row)
