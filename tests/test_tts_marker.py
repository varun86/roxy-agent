from __future__ import annotations

from APP.plugins.builtin.roxy_realtime_tts import RoxyRealtimeTtsPlugin


def test_split_roxy_tts_marker_extracts_japanese_line_and_strips_visible_text():
    visible, tts = RoxyRealtimeTtsPlugin.parse_tts_marker(
        "整理好了。\n<roxy_tts_ja>はい、完了しました。</roxy_tts_ja>"
    )

    assert visible == "整理好了。"
    assert tts == "はい、完了しました。"


def test_split_roxy_tts_marker_returns_none_without_marker():
    visible, tts = RoxyRealtimeTtsPlugin.parse_tts_marker("普通回复")

    assert visible == "普通回复"
    assert tts is None


def test_split_roxy_tts_marker_rejects_multiple_markers_but_strips_them():
    visible, tts = RoxyRealtimeTtsPlugin.parse_tts_marker(
        "整理好了。<roxy_tts_ja>はい。</roxy_tts_ja><roxy_tts_ja>できました。</roxy_tts_ja>"
    )

    assert visible == "整理好了。"
    assert tts is None
