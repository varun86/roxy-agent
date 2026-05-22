from __future__ import annotations

import pytest

from APP.plugins.roxy_realtime_tts import RoxyRealtimeTtsPlugin


@pytest.mark.asyncio
async def test_roxy_realtime_tts_start_failure_records_error_without_disabling(tmp_path, monkeypatch):
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={})
    monkeypatch.delenv("ROXY_GSV_REF_AUDIO", raising=False)
    plugin._health_check = lambda timeout: False

    with pytest.raises(RuntimeError):
        await plugin.ensure_service_running()

    assert plugin.enabled is True
    assert plugin.last_error == "ROXY_GSV_REF_AUDIO is not set"


@pytest.mark.asyncio
async def test_roxy_realtime_tts_after_message_swallows_synthesis_failure(tmp_path):
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={})

    async def fail(_: str) -> dict[str, object]:
        raise RuntimeError("tts failed")

    plugin.synthesize_and_play = fail

    await plugin.after_assistant_message(visible_text="visible", tts_text="はい、完了です。", thread_id="thread-a", trace={})

    assert plugin.last_error == "tts failed"
    assert plugin.last_tts_text == "はい、完了です。"
    assert plugin.last_source == "marker"


@pytest.mark.asyncio
async def test_roxy_realtime_tts_uses_llm_fallback_when_marker_missing(tmp_path):
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={})

    async def generate(_: str) -> str:
        return "はい、確認しました。"

    plugin.fallback_tts_line_generator = generate

    text, source = await plugin.resolve_tts_text(visible_text="处理完成了。", tts_text=None)

    assert text == "はい、確認しました。"
    assert source == "llm_fallback"


@pytest.mark.asyncio
async def test_roxy_realtime_tts_rejects_chinese_or_long_marker_and_uses_static_fallback(tmp_path):
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={})

    text, source = await plugin.resolve_tts_text(
        visible_text="处理完成了。",
        tts_text="这是中文标签，不能朗读。",
    )

    assert text == "はい、整いました。"
    assert source == "static_fallback"

    too_long = "はい、" + "とても" * 20
    text, source = await plugin.resolve_tts_text(visible_text="处理完成了。", tts_text=too_long)

    assert text == "はい、整いました。"
    assert source == "static_fallback"


@pytest.mark.asyncio
async def test_roxy_realtime_tts_uses_static_fallback_when_llm_fallback_fails(tmp_path):
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={})

    async def fail(_: str) -> str:
        raise RuntimeError("model failed")

    plugin.fallback_tts_line_generator = fail

    text, source = await plugin.resolve_tts_text(visible_text="处理完成了。", tts_text=None)

    assert text == "はい、整いました。"
    assert source == "static_fallback"
    assert plugin.last_error == "TTS line generation failed: model failed"


def test_roxy_realtime_tts_synthesizes_file_and_forwards_to_pet(tmp_path, monkeypatch):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"fake")
    output_audio = tmp_path / "out.wav"
    output_audio.write_bytes(b"fake")
    monkeypatch.setenv("ROXY_GSV_REF_AUDIO", str(ref_audio))
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=True, config={"tts_base_url": "http://tts.local"})
    plugin._health_check = lambda timeout: True
    calls: list[tuple[str, dict[str, object]]] = []

    def post_json(url: str, payload: dict[str, object], **_: object) -> dict[str, object]:
        calls.append((url, payload))
        if url.endswith("/tts/file"):
            return {"output_path": str(output_audio)}
        return {}

    plugin._post_json = post_json

    result = plugin._synthesize_and_play_sync("hello")

    assert result["output_path"] == str(output_audio)
    assert calls[0][0] == "http://tts.local/tts/file"
    assert calls[0][1]["text"] == "hello"
    assert calls[0][1]["ref_audio_path"] == str(ref_audio)
    assert calls[1][0] == "http://127.0.0.1:23333/play-tts"
    assert calls[1][1]["assetUrl"] == output_audio.resolve().as_uri()
    assert plugin.last_output_path == str(output_audio)
    assert plugin.last_playback_ok is True


@pytest.mark.asyncio
async def test_roxy_realtime_tts_enable_failure_rolls_back_enabled_state(tmp_path, monkeypatch):
    (tmp_path / "extensions_config.json").write_text(
        '{"plugins":{"roxy_realtime_tts":{"enabled":false,"config":{}}}}',
        encoding="utf-8",
    )
    plugin = RoxyRealtimeTtsPlugin(project_root=tmp_path, enabled=False, config={})
    monkeypatch.delenv("ROXY_GSV_REF_AUDIO", raising=False)
    plugin._health_check = lambda timeout: False

    with pytest.raises(RuntimeError):
        await plugin.enable()

    assert plugin.enabled is False
