from __future__ import annotations

from harness.context import ThreadContextStore


def test_thread_context_store_persists_turn_and_skill_pinning(tmp_path):
    store = ThreadContextStore(
        base_dir=tmp_path,
        max_recent_messages=8,
        compact_threshold_chars=5000,
        skill_memory_max=4,
    )

    context = store.load("t1")
    assert context.thread_id == "t1"
    assert context.recent_messages == []

    store.update_after_turn(
        context,
        user_message="Please load the example skill and use it.",
        assistant_message="Loaded and applied.",
        incoming_messages=None,
        available_skill_names=["example", "other"],
    )

    reloaded = store.load("t1")
    assert reloaded.pinned_skills == ["example"]
    assert reloaded.recent_messages[-2]["role"] == "user"
    assert reloaded.recent_messages[-1]["role"] == "assistant"


def test_thread_context_store_compacts_when_threshold_exceeded(tmp_path):
    store = ThreadContextStore(
        base_dir=tmp_path,
        max_recent_messages=10,
        compact_threshold_chars=80,
        skill_memory_max=4,
    )

    context = store.load("t2")
    for index in range(4):
        store.update_after_turn(
            context,
            user_message=f"user message {index} with more content",
            assistant_message=f"assistant message {index} with more content",
            incoming_messages=None,
            available_skill_names=[],
        )

    reloaded = store.load("t2")
    assert reloaded.compact_summary
    assert len(reloaded.recent_messages) < 8


def test_thread_context_store_supports_explicit_context_path(tmp_path):
    store = ThreadContextStore(
        base_dir=tmp_path / "legacy",
        max_recent_messages=8,
        compact_threshold_chars=5000,
        skill_memory_max=4,
    )
    context_path = tmp_path / "threads" / "t1" / "context.json"

    context = store.load("thread-1", context_path=context_path)
    store.update_after_turn(
        context,
        user_message="Use example skill",
        assistant_message="Done",
        incoming_messages=None,
        available_skill_names=["example"],
        context_path=context_path,
    )

    reloaded = store.load("thread-1", context_path=context_path)
    assert context_path.exists()
    assert reloaded.thread_id == "thread-1"
    assert reloaded.recent_messages[-1]["content"] == "Done"
