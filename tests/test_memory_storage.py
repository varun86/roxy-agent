from __future__ import annotations

from pathlib import Path

from harness.config.settings import HarnessConfig, MemoryConfig, RegisteredModel, RuntimeConfig, SandboxConfig
from harness.memory.storage import create_empty_memory, get_memory_storage, reset_memory_storage
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


def test_create_empty_memory_returns_expected_shape():
    memory = create_empty_memory()

    assert memory["version"] == "1.0"
    assert "user" in memory
    assert "history" in memory
    assert isinstance(memory["facts"], list)


def test_file_memory_storage_loads_empty_when_missing(tmp_path):
    reset_memory_storage()
    config = _make_config(tmp_path)

    memory = get_memory_storage(config).load()

    assert memory["version"] == "1.0"
    assert memory["facts"] == []


def test_file_memory_storage_save_and_reload(tmp_path):
    reset_memory_storage()
    config = _make_config(tmp_path)
    storage = get_memory_storage(config)

    payload = create_empty_memory()
    payload["facts"].append({"content": "User prefers Python"})

    assert storage.save(payload) is True
    reloaded = storage.reload()
    assert reloaded["facts"][0]["content"] == "User prefers Python"
