from __future__ import annotations

import asyncio
import html
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable

from APP.plugins.base import PluginHostContext, PluginStatus
from APP.plugins.registry import AssistantMessageContext, PluginCapabilityRegistry, RealtimePromptContract


class RoxyRealtimeTtsPlugin:
    plugin_id = "roxy_realtime_tts"
    plugin_name = "Roxy Realtime TTS"
    plugin_version = "0.1.0"
    priority = 100
    static_fallback_text = "はい、整いました。"

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        enabled: bool = False,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = project_root or Path.cwd()
        self.config_path = self.project_root / "extensions_config.json"
        self.enabled = enabled
        self.config = config or {}
        self.last_error: str | None = None
        self.last_tts_text: str | None = None
        self.last_source: str | None = None
        self.last_output_path: str | None = None
        self.last_playback_ok: bool | None = None
        self.fallback_tts_line_generator: Callable[[str], Awaitable[str]] | None = None
        self._process: subprocess.Popen[bytes] | None = None

    def initialize(self, register: PluginCapabilityRegistry, host: PluginHostContext) -> None:
        self.project_root = host.project_root
        self.config_path = host.config_path
        self.enabled = host.enabled
        self.config = dict(host.config)
        self.fallback_tts_line_generator = host.fallback_tts_line_generator
        register.register_realtime_prompt_contract(
            RealtimePromptContract(
                plugin_id=self.plugin_id,
                prompt_text=self.assistant_reply_tts_contract(),
                parse_payload=self.parse_tts_marker,
                is_enabled=lambda: self.enabled,
            )
        )
        register.register_assistant_message_hook(self.plugin_id, self.handle_assistant_message)
        register.register_management(self.plugin_id, self)

    def shutdown(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    @property
    def tts_base_url(self) -> str:
        configured = str(self.config.get("tts_base_url") or "").strip()
        if configured:
            return configured.rstrip("/")
        host = os.environ.get("ROXY_GSV_HOST", "127.0.0.1")
        port = os.environ.get("ROXY_GSV_PORT", "9881")
        return f"http://{host}:{port}"

    @property
    def pet_play_url(self) -> str:
        return str(self.config.get("pet_play_url") or "http://127.0.0.1:23333/play-tts")

    @property
    def text_lang(self) -> str:
        return str(self.config.get("text_lang") or os.environ.get("ROXY_GSV_TEXT_LANG", "ja"))

    @property
    def ref_audio_path(self) -> str:
        return str(self.config.get("ref_audio_path") or os.environ.get("ROXY_GSV_REF_AUDIO", ""))

    @property
    def startup_timeout_seconds(self) -> float:
        raw = self.config.get("startup_timeout_seconds", 20)
        try:
            return max(1.0, float(raw))
        except (TypeError, ValueError):
            return 20.0

    def status(self) -> PluginStatus:
        running = self._health_check(timeout=0.6)
        return PluginStatus(
            plugin_id=self.plugin_id,
            enabled=self.enabled,
            service_running=running,
            last_error=self.last_error,
            details={
                "last_tts_text": self.last_tts_text,
                "last_source": self.last_source,
                "last_output_path": self.last_output_path,
                "last_playback_ok": self.last_playback_ok,
            },
        )

    async def enable(self) -> PluginStatus:
        self.enabled = True
        try:
            await self.ensure_service_running()
        except Exception:
            self.enabled = False
            raise
        return self.status()

    def disable(self) -> PluginStatus:
        self.enabled = False
        self.last_error = None
        return self.status()

    async def test(self, payload: dict[str, Any] | str | None = None) -> PluginStatus:
        self.enabled = True
        text = payload if isinstance(payload, str) else payload.get("text") if payload else None
        tts_text = text or str(self.config.get("test_text") or "はい、音声の準備ができました。")
        self.last_tts_text = self.normalize_tts_text(tts_text)
        self.last_source = "test"
        self.last_output_path = None
        self.last_playback_ok = None
        await self.synthesize_and_play(self.last_tts_text)
        return self.status()

    async def handle_assistant_message(self, context: AssistantMessageContext) -> None:
        await self.after_assistant_message(
            visible_text=context.visible_text,
            tts_text=context.control_payload if isinstance(context.control_payload, str) else None,
            thread_id=context.thread_id,
            trace=context.trace,
        )

    @staticmethod
    def assistant_reply_tts_contract() -> str:
        return (
            "<realtime_tts>\n"
            "Realtime desktop-pet TTS is enabled for this run. At the very end of every final assistant reply, "
            "append exactly one hidden host-control line in this format:\n"
            "<roxy_tts_ja>短い日本語の台詞</roxy_tts_ja>\n"
            "The Japanese line must be one short, natural, roleplay-friendly Roxy-style utterance for speaking aloud. "
            "Use Japanese only inside the tag, keep it under 45 Japanese characters, and do not put task details, "
            "file paths, code, markdown, XML, or Chinese inside the tag. Keep the normal user-visible answer in the "
            "user's language outside the tag.\n"
            "</realtime_tts>"
        )

    @classmethod
    def parse_tts_marker(cls, text: str) -> tuple[str, str | None]:
        pattern = re.compile(r"\s*<roxy_tts_ja>(.*?)</roxy_tts_ja>\s*", re.DOTALL | re.IGNORECASE)
        matches = list(pattern.finditer(text))
        if not matches:
            return text, None
        visible_text = pattern.sub("", text).strip()
        if len(matches) != 1:
            return visible_text or text.strip(), None
        tts_text = re.sub(r"\s+", " ", matches[0].group(1)).strip()
        return visible_text or text.strip(), tts_text or None

    async def after_assistant_message(
        self,
        *,
        visible_text: str,
        tts_text: str | None,
        thread_id: str,
        trace: dict[str, Any],
    ) -> None:
        _ = thread_id, trace
        if not self.enabled:
            return
        clean_text, source = await self.resolve_tts_text(visible_text=visible_text, tts_text=tts_text)
        try:
            self.last_tts_text = clean_text
            self.last_source = source
            self.last_output_path = None
            self.last_playback_ok = None
            await self.synthesize_and_play(clean_text)
        except Exception as exc:
            self.last_error = str(exc)

    async def resolve_tts_text(self, *, visible_text: str, tts_text: str | None) -> tuple[str, str]:
        candidate = self.normalize_tts_text(tts_text or "")
        if self.is_valid_japanese_tts(candidate):
            return candidate, "marker"

        visible_clean = self.clean_visible_text(visible_text)
        if visible_clean and self.fallback_tts_line_generator is not None:
            try:
                generated = self.normalize_tts_text(await self.fallback_tts_line_generator(visible_clean))
                if self.is_valid_japanese_tts(generated):
                    return generated, "llm_fallback"
            except Exception as exc:
                self.last_error = f"TTS line generation failed: {exc}"

        return str(self.config.get("static_fallback_text") or self.static_fallback_text), "static_fallback"

    async def ensure_service_running(self) -> None:
        await asyncio.to_thread(self._ensure_service_running_sync)

    async def synthesize_and_play(self, text: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._synthesize_and_play_sync, text)

    def _ensure_service_running_sync(self) -> None:
        if self._health_check(timeout=1.0):
            self.last_error = None
            return
        if not self.ref_audio_path:
            self.last_error = "ROXY_GSV_REF_AUDIO is not set"
            raise RuntimeError(self.last_error)

        required = ["ROXY_GSV_DEPLOY_ROOT", "ROXY_GSV_T2S_WEIGHTS", "ROXY_GSV_VITS_WEIGHTS", "ROXY_GSV_REF_AUDIO"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            self.last_error = f"Missing required TTS env vars: {', '.join(missing)}"
            raise RuntimeError(self.last_error)

        if self._process is None or self._process.poll() is not None:
            script = self.project_root / "scripts" / "tts" / "run_roxy_gsv_service.sh"
            if not script.exists():
                self.last_error = f"TTS startup script not found: {script}"
                raise RuntimeError(self.last_error)
            log_path = self.project_root / ".sandbox" / "roxy-gsv-service.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("ab")
            self._process = subprocess.Popen(
                [str(script)],
                cwd=str(self.project_root),
                env=os.environ.copy(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            if self._health_check(timeout=1.0):
                self.last_error = None
                return
            if self._process is not None and self._process.poll() is not None:
                self.last_error = f"TTS service exited with code {self._process.returncode}"
                raise RuntimeError(self.last_error)
            time.sleep(0.5)
        self.last_error = f"TTS service did not become ready within {self.startup_timeout_seconds:.0f}s"
        raise RuntimeError(self.last_error)

    def _health_check(self, *, timeout: float) -> bool:
        try:
            with urllib.request.urlopen(f"{self.tts_base_url}/health", timeout=timeout) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

    def _synthesize_and_play_sync(self, text: str) -> dict[str, Any]:
        self._ensure_service_running_sync()
        ref_audio_path = self.ref_audio_path
        if not ref_audio_path:
            raise RuntimeError("ROXY_GSV_REF_AUDIO is not set")

        payload = {
            "text": text,
            "text_lang": self.text_lang,
            "ref_audio_path": ref_audio_path,
        }
        result = self._post_json(f"{self.tts_base_url}/tts/file", payload, timeout=120)
        output_path = str(result.get("output_path") or "")
        if not output_path:
            raise RuntimeError("TTS response did not include output_path")
        self.last_output_path = output_path
        asset_url = Path(output_path).expanduser().resolve().as_uri()
        try:
            self._post_json(self.pet_play_url, {"assetUrl": asset_url}, timeout=3, allow_empty=True)
        except Exception:
            self.last_playback_ok = False
            raise
        self.last_playback_ok = True
        self.last_error = None
        return result

    @staticmethod
    def normalize_tts_text(text: str) -> str:
        cleaned = html.unescape(str(text or ""))
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = re.sub(r"[`*_#>\[\]{}]", "", cleaned)
        cleaned = re.sub(r"https?://\S+|\S+/\S+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def clean_visible_text(cls, text: str) -> str:
        cleaned = html.unescape(str(text or ""))
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\([^()]*\)|（[^（）]*）|\*[^*]*\*", " ", cleaned)
        cleaned = re.sub(r"```[\s\S]*?```|`[^`]*`", " ", cleaned)
        cleaned = re.sub(r"https?://\S+|\S+/\S+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:500]

    @staticmethod
    def is_valid_japanese_tts(text: str) -> bool:
        if not text:
            return False
        if len(text) > 45:
            return False
        if "\n" in text or "\r" in text:
            return False
        if re.search(r"[\u3040-\u30ff]", text) is None:
            return False
        if re.search(r"[\u4e00-\u9fff]{5,}", text):
            return False
        if re.search(r"[#*_`<>{}\[\]|/\\]", text):
            return False
        if re.search(r"https?://", text):
            return False
        return True

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any], *, timeout: float, allow_empty: bool = False) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if not raw and allow_empty:
                    return {}
                if not raw:
                    raise RuntimeError(f"Empty response from {url}")
                decoded = json.loads(raw.decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise RuntimeError(f"Unexpected response from {url}")
                return decoded
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
