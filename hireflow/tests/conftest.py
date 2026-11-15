import pytest


@pytest.fixture(autouse=True)
def no_real_model_calls(monkeypatch):
    """Tests never call a real model: the template fallback is used unless a test overrides it."""
    monkeypatch.setenv("HIREFLOW_LLM", "off")
