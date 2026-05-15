from __future__ import annotations

from APP.dto import (
    ChatRequest,
    ConversationDetail,
    McpConfigResponse,
    ModelInfo,
    ReminderDetail,
    TraceInfo,
)


def test_dto_init_reexports_split_modules():
    assert ChatRequest.__name__ == "ChatRequest"
    assert TraceInfo.__name__ == "TraceInfo"
    assert ConversationDetail.__name__ == "ConversationDetail"
    assert McpConfigResponse.__name__ == "McpConfigResponse"
    assert ModelInfo.__name__ == "ModelInfo"
    assert ReminderDetail.__name__ == "ReminderDetail"
