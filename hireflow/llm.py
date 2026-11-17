"""LLM helper with a safety net.

Order tried: Gemini -> Groq -> Ollama (local) -> template sentence.
The model is used ONLY to polish one short sentence. Every decision, score and
number comes from deterministic Python tools, so a model failure never breaks a run.

Calls go through Semantic Kernel's OpenAIChatCompletion connector (Gemini, Groq and
Ollama all expose an OpenAI-compatible endpoint).
"""
from __future__ import annotations

import json
import os
import re

from hireflow import config
from hireflow.runtime import run_sync

SYSTEM_PROMPT = (
    "You write one short, neutral sentence for a recruiter. Use ONLY the facts given. "
    "Never mention or infer age, gender, marital status, religion, nationality or health. "
    "Reply with the sentence only."
)


def active_providers() -> list[dict]:
    """Providers that are configured right now (read at call time so tests can change env)."""
    if os.getenv("HIREFLOW_LLM", "auto").lower() == "off":
        return []
    found = []
    for p in config.LLM_PROVIDERS:
        if p["name"] == "ollama":
            if os.getenv("OLLAMA_ENABLED", "0") != "1":
                continue
            api_key = "ollama"
        else:
            api_key = os.getenv(p["key_env"], "")
            if not api_key:
                continue
        found.append({**p, "api_key": api_key, "model": os.getenv(p["model_env"], p["default_model"])})
    return found


async def _call_provider(provider: dict, prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 100) -> str:
    from openai import AsyncOpenAI
    from semantic_kernel.connectors.ai.open_ai import (
        OpenAIChatCompletion,
        OpenAIChatPromptExecutionSettings,
    )
    from semantic_kernel.contents import ChatHistory

    client = AsyncOpenAI(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
    service = OpenAIChatCompletion(ai_model_id=provider["model"], async_client=client)
    history = ChatHistory(system_message=system)
    history.add_user_message(prompt)
    settings = OpenAIChatPromptExecutionSettings(temperature=0, max_tokens=max_tokens)
    reply = await service.get_chat_message_content(chat_history=history, settings=settings)
    return str(reply).strip()


def _is_valid(text: str, must_contain: tuple[str, ...]) -> bool:
    if not text or len(text) > 300:
        return False
    low = text.lower()
    return all(token.lower() in low for token in must_contain)


def generate_text(prompt: str, fallback: str, must_contain: tuple[str, ...] = ()) -> tuple[str, str]:
    """Return (text, source). source is the provider name or 'template'."""
    for provider in active_providers():
        for _attempt in range(2):  # one retry per provider
            try:
                text = run_sync(_call_provider(provider, prompt))
                text = re.sub(r"\s+", " ", text).strip()
                if _is_valid(text, must_contain):
                    return text, provider["name"]
            except Exception:  # timeout, rate limit, bad key, server down ...
                continue
    return fallback, "template"


JSON_SYSTEM_PROMPT = (
    "You extract facts from a resume into JSON. Use ONLY text that is written in the resume. "
    "Never infer or invent anything and never output age, gender, marital status, religion or nationality. "
    "Reply with one JSON object and nothing else."
)


def generate_json(prompt: str) -> tuple[dict | None, str]:
    """Return (parsed JSON object or None, provider name or ''). Same Gemini -> Groq -> Ollama chain; None when no model gives valid JSON."""
    for provider in active_providers():
        for _attempt in range(2):
            try:
                text = run_sync(_call_provider(provider, prompt, system=JSON_SYSTEM_PROMPT, max_tokens=1500))
                match = re.search(r"\{.*\}", text, re.S)
                data = json.loads(match.group(0)) if match else None
                if isinstance(data, dict):
                    return data, provider["name"]
            except Exception:
                continue
    return None, ""
