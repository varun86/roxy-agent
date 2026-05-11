from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from harness.agents.loop import OpenAIChatCompletionsClient
from harness.config.settings import HarnessConfig
from harness.memory.prompt import MEMORY_UPDATE_PROMPT, _clean_summary, format_conversation_for_update
from harness.memory.storage import get_memory_storage

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_memory_data(config: HarnessConfig) -> dict[str, Any]:
    return get_memory_storage(config).load()


def reload_memory_data(config: HarnessConfig) -> dict[str, Any]:
    return get_memory_storage(config).reload()


def _fact_content_key(content: Any) -> str | None:
    if not isinstance(content, str):
        return None
    stripped = _clean_summary(content)
    return stripped or None


def _extract_json_payload(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty model response")

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", stripped, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    json_block = re.search(r"(\{[\s\S]*\})", stripped)
    if json_block:
        return json_block.group(1).strip()

    raise ValueError("no JSON object found in model response")


class MemoryUpdater:
    def __init__(self, config: HarnessConfig):
        self._config = config

    def _get_model_client(self) -> OpenAIChatCompletionsClient:
        selected_model = self._config.get_model(self._config.memory.model_name)
        return OpenAIChatCompletionsClient(
            api_key=selected_model.read_api_key(),
            base_url=selected_model.base_url,
        )

    def _invoke_model(self, prompt: str) -> str:
        selected_model = self._config.get_model(self._config.memory.model_name)
        client = self._get_model_client()

        async def run() -> str:
            text, _ = await client.create_response(
                model=selected_model.model,
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                temperature=0.1,
                max_tokens=min(selected_model.max_tokens, 1400),
            )
            return text

        return asyncio.run(run())

    def _apply_updates(
        self,
        current_memory: dict[str, Any],
        update_data: dict[str, Any],
        *,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        for section_name in ("workContext", "personalContext", "topOfMind"):
            section = update_data.get("user", {}).get(section_name, {})
            if section.get("shouldUpdate") and isinstance(section.get("summary"), str) and section["summary"].strip():
                cleaned = _clean_summary(section["summary"])
                if cleaned:
                    current_memory["user"][section_name] = {"summary": cleaned, "updatedAt": now}

        for section_name in ("recentMonths", "earlierContext", "longTermBackground"):
            section = update_data.get("history", {}).get(section_name, {})
            if section.get("shouldUpdate") and isinstance(section.get("summary"), str) and section["summary"].strip():
                cleaned = _clean_summary(section["summary"])
                if cleaned:
                    current_memory["history"][section_name] = {"summary": cleaned, "updatedAt": now}

        facts_to_remove = set(update_data.get("factsToRemove", []))
        if facts_to_remove:
            current_memory["facts"] = [
                item for item in current_memory.get("facts", []) if item.get("id") not in facts_to_remove
            ]

        existing_fact_keys = {
            key
            for key in (_fact_content_key(item.get("content")) for item in current_memory.get("facts", []))
            if key is not None
        }
        for item in update_data.get("newFacts", []):
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("confidence", 0.0))
            if confidence < self._config.memory.fact_confidence_threshold:
                continue
            content = item.get("content", "")
            fact_key = _fact_content_key(content)
            if fact_key is None or fact_key in existing_fact_keys:
                continue
            current_memory["facts"].append(
                {
                    "id": f"fact_{uuid.uuid4().hex[:8]}",
                    "content": fact_key,
                    "category": str(item.get("category", "context")).strip() or "context",
                    "confidence": confidence,
                    "createdAt": now,
                    "source": thread_id or "unknown",
                }
            )
            existing_fact_keys.add(fact_key)

        max_facts = self._config.memory.max_facts
        current_memory["facts"] = sorted(
            current_memory.get("facts", []),
            key=lambda fact: float(fact.get("confidence", 0.0)),
            reverse=True,
        )[:max_facts]
        return current_memory

    def update_memory(self, messages: list[dict[str, str]], *, thread_id: str | None = None) -> bool:
        if not self._config.memory.enabled or not messages:
            logger.debug("Skipping memory update: disabled or empty messages")
            return False
        current_memory = get_memory_data(self._config)
        conversation = format_conversation_for_update(messages)
        if not conversation.strip():
            logger.debug("Skipping memory update: no meaningful conversation content")
            return False
        prompt = MEMORY_UPDATE_PROMPT.format(
            current_memory=json.dumps(current_memory, ensure_ascii=False, indent=2),
            conversation=conversation,
        )
        try:
            response_text = self._invoke_model(prompt).strip()
            update_data = json.loads(_extract_json_payload(response_text))
        except Exception as exc:
            logger.warning("Memory update model response could not be parsed: %s", exc)
            return False
        updated = self._apply_updates(current_memory, update_data, thread_id=thread_id)
        saved = get_memory_storage(self._config).save(updated)
        if not saved:
            logger.warning("Memory update save failed: %s", self._config.memory.storage_path)
        return saved


def update_memory_from_conversation(
    config: HarnessConfig,
    messages: list[dict[str, str]],
    *,
    thread_id: str | None = None,
) -> bool:
    return MemoryUpdater(config).update_memory(messages, thread_id=thread_id)
