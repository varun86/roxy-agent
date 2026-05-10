from __future__ import annotations

from harness.memory.prompt import format_memory_for_injection


def test_format_memory_injection_includes_stable_profile():
    memory = {
        "user": {
            "workContext": {"summary": "Uses Python and FastAPI", "updatedAt": ""},
            "personalContext": {"summary": "Prefers concise answers", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "Maintains agent systems", "updatedAt": ""},
        },
        "facts": [],
    }

    result = format_memory_for_injection(memory, "How should I structure this FastAPI app?", max_tokens=800)

    assert "Stable Profile:" in result
    assert "Uses Python and FastAPI" in result
    assert "Prefers concise answers" in result


def test_format_memory_injection_prefers_relevant_facts():
    memory = {
        "user": {},
        "history": {},
        "facts": [
            {"content": "User prefers uv for Python dependency management", "category": "preference", "confidence": 0.9},
            {"content": "User likes watercolor painting on weekends", "category": "context", "confidence": 0.95},
        ],
    }

    result = format_memory_for_injection(memory, "How should I manage Python dependencies with uv?", max_tokens=800)

    assert "Relevant Facts:" in result
    assert "uv for Python dependency management" in result
    assert "watercolor painting" not in result


def test_format_memory_injection_omits_irrelevant_facts_when_no_match():
    memory = {
        "user": {
            "workContext": {"summary": "Works mainly with Python services", "updatedAt": ""},
        },
        "history": {},
        "facts": [
            {"content": "User prefers uv for Python dependency management", "category": "preference", "confidence": 0.9},
        ],
    }

    result = format_memory_for_injection(memory, "Write a product announcement email", max_tokens=800)

    assert "Stable Profile:" in result
    assert "Relevant Facts:" not in result


def test_format_memory_injection_respects_token_budget(monkeypatch):
    monkeypatch.setattr("harness.memory.prompt._count_tokens", lambda text, encoding_name="cl100k_base": len(text))
    memory = {
        "user": {"workContext": {"summary": "Uses Python", "updatedAt": ""}},
        "history": {},
        "facts": [
            {"content": "First relevant fact", "category": "knowledge", "confidence": 0.95},
            {"content": "Second relevant fact with extra details", "category": "knowledge", "confidence": 0.9},
        ],
    }

    result = format_memory_for_injection(memory, "Tell me about Python fact", max_tokens=90)

    assert "Uses Python" in result
    assert len(result) <= 110
