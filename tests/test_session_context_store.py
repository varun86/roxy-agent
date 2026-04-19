from __future__ import annotations

from harness.context import SessionContextStore


def test_context_store_persists_turn_and_skill_pinning(tmp_path):
    store = SessionContextStore(
        base_dir=tmp_path,
        max_recent_messages=8,
        compact_threshold_chars=5000,
        skill_memory_max=4,
    )

    context = store.load("s1")
    assert context.session_id == "s1"
    assert context.recent_messages == []

    store.update_after_turn(
        context,
        user_message="Please load the example skill and use it.",
        assistant_message="Loaded and applied.",
        incoming_messages=None,
        available_skill_names=["example", "other"],
    )

    reloaded = store.load("s1")
    assert reloaded.pinned_skills == ["example"]
    assert reloaded.recent_messages[-2]["role"] == "user"
    assert reloaded.recent_messages[-1]["role"] == "assistant"


def test_context_store_compacts_when_threshold_exceeded(tmp_path):
    store = SessionContextStore(
        base_dir=tmp_path,
        max_recent_messages=10,
        compact_threshold_chars=80,
        skill_memory_max=4,
    )

    context = store.load("s2")
    for index in range(4):
        store.update_after_turn(
            context,
            user_message=f"user message {index} with more content",
            assistant_message=f"assistant message {index} with more content",
            incoming_messages=None,
            available_skill_names=[],
        )

    reloaded = store.load("s2")
    assert reloaded.compact_summary
    assert len(reloaded.recent_messages) < 8