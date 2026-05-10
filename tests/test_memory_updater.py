from __future__ import annotations

import json
from pathlib import Path

from harness.config.settings import HarnessConfig, MemoryConfig, RegisteredModel, RuntimeConfig, SandboxConfig
from harness.memory.storage import create_empty_memory, reset_memory_storage
from harness.memory.updater import MemoryUpdater, _extract_json_payload, get_memory_data
from harness.rag.config import RagConfig


def _make_config(tmp_path: Path) -> HarnessConfig:
    return HarnessConfig(
        models=[
            RegisteredModel(
                name="fake",
                display_name="fake",
                provider="openai-compatible",
                model="fake-model",
            )
        ],
        default_model="fake",
        sandbox=SandboxConfig(root_dir=tmp_path / ".sandbox"),
        runtime=RuntimeConfig(),
        memory=MemoryConfig(storage_path=tmp_path / ".sandbox" / "memory.json"),
        rag=RagConfig(qdrant_url=":memory:"),
    )


def test_apply_updates_skips_duplicates_and_low_confidence(tmp_path):
    config = _make_config(tmp_path)
    updater = MemoryUpdater(config)
    current = create_empty_memory()
    current["facts"] = [
        {
            "id": "fact_existing",
            "content": "User prefers concise answers",
            "category": "preference",
            "confidence": 0.9,
            "createdAt": "",
            "source": "thread-a",
        }
    ]
    update_data = {
        "user": {},
        "history": {},
        "factsToRemove": [],
        "newFacts": [
            {"content": "User prefers concise answers", "category": "preference", "confidence": 0.95},
            {"content": "User mainly writes Python services", "category": "context", "confidence": 0.91},
            {"content": "User likes noisy logs", "category": "behavior", "confidence": 0.4},
        ],
    }

    result = updater._apply_updates(current, update_data, thread_id="thread-b")

    assert [fact["content"] for fact in result["facts"]] == [
        "User mainly writes Python services",
        "User prefers concise answers",
    ]
    assert any(fact["source"] == "thread-b" for fact in result["facts"])


def test_update_memory_persists_model_output(tmp_path):
    reset_memory_storage()
    config = _make_config(tmp_path)

    class FakeMemoryUpdater(MemoryUpdater):
        def _invoke_model(self, prompt: str) -> str:
            payload = {
                "user": {
                    "workContext": {"summary": "Works on Python agent tooling", "shouldUpdate": True},
                    "personalContext": {"summary": "Prefers concise replies", "shouldUpdate": True},
                    "topOfMind": {"summary": "Implementing long-term memory", "shouldUpdate": True},
                },
                "history": {
                    "recentMonths": {"summary": "Recent work focused on agent UX", "shouldUpdate": True},
                    "earlierContext": {"summary": "", "shouldUpdate": False},
                    "longTermBackground": {"summary": "Builds local developer tools", "shouldUpdate": True},
                },
                "newFacts": [
                    {"content": "User prefers concise replies", "category": "preference", "confidence": 0.92},
                    {"content": "User uses Python for agent tooling", "category": "knowledge", "confidence": 0.88},
                    {"content": "Temporary upload path is /mnt/user-data/uploads/demo.txt", "category": "context", "confidence": 0.95},
                ],
                "factsToRemove": [],
            }
            return json.dumps(payload, ensure_ascii=False)

    updater = FakeMemoryUpdater(config)
    success = updater.update_memory(
        [
            {"role": "user", "content": "我主要做 Python agent tooling，回答尽量简洁。"},
            {"role": "assistant", "content": "好的，我会保持简洁。"},
        ],
        thread_id="thread-a",
    )

    assert success is True
    memory = get_memory_data(config)
    assert memory["user"]["workContext"]["summary"] == "Works on Python agent tooling"
    facts = [item["content"] for item in memory["facts"]]
    assert "User prefers concise replies" in facts
    assert all("/mnt/user-data/uploads/" not in item for item in facts)


def test_extract_json_payload_supports_think_wrapped_fenced_json():
    response = """<think>analysis</think>

```json
{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}
```"""

    payload = _extract_json_payload(response)

    assert payload == '{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}'
