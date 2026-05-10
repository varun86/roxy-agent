from __future__ import annotations

import math
import re
from typing import Any

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


MEMORY_UPDATE_PROMPT = """You are a memory management system. Update the long-term user memory from a conversation.

Current memory JSON:
<current_memory>
{current_memory}
</current_memory>

Conversation:
<conversation>
{conversation}
</conversation>

Return ONLY valid JSON with this shape:
{{
  "user": {{
    "workContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "personalContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "topOfMind": {{ "summary": "...", "shouldUpdate": true/false }}
  }},
  "history": {{
    "recentMonths": {{ "summary": "...", "shouldUpdate": true/false }},
    "earlierContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "longTermBackground": {{ "summary": "...", "shouldUpdate": true/false }}
  }},
  "newFacts": [
    {{ "content": "...", "category": "preference|knowledge|context|behavior|goal", "confidence": 0.0-1.0 }}
  ],
  "factsToRemove": ["fact_id"]
}}

Rules:
- Keep stable profile summaries concise and useful across sessions.
- Prefer stable user preferences, working style, long-term stack, and recurring goals.
- topOfMind may be more recent but still should be reusable in future sessions.
- Only add facts that are explicit or strongly implied.
- Ignore temporary paths, upload bookkeeping, one-off file names, transient shell output, and session-only artifacts.
- If there is no meaningful update for a section, set shouldUpdate to false.
"""


_UPLOAD_SENTENCE_RE = re.compile(
    r"[^.!?\n]*\b(?:/mnt/|\.sandbox/|uploads?/|outputs?/|workspace/|temp(?:orary)? file|uploaded file)[^.!?\n]*[.!?]?\s*",
    re.IGNORECASE,
)


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    if not text:
        return 0
    if not TIKTOKEN_AVAILABLE:
        return max(1, len(text) // 4)
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _coerce_confidence(value: Any, default: float = 0.0) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return max(0.0, min(1.0, default))
    if not math.isfinite(confidence):
        return max(0.0, min(1.0, default))
    return max(0.0, min(1.0, confidence))


def _extract_terms(text: str) -> set[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_+-]{2,}", lowered)
    cjk = re.findall(r"[\u4e00-\u9fff]{1,4}", text)
    return {item for item in [*latin, *cjk] if item}


def _clean_summary(summary: str) -> str:
    cleaned = _UPLOAD_SENTENCE_RE.sub("", summary or "").strip()
    return re.sub(r"\s+", " ", cleaned)


def format_conversation_for_update(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        cleaned = _clean_summary(content)
        if not cleaned:
            continue
        if len(cleaned) > 1200:
            cleaned = cleaned[:1200].rstrip() + "..."
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {cleaned}")
    return "\n\n".join(lines)


def _stable_profile_lines(memory_data: dict[str, Any]) -> list[str]:
    user_data = memory_data.get("user", {}) if isinstance(memory_data, dict) else {}
    history_data = memory_data.get("history", {}) if isinstance(memory_data, dict) else {}
    candidates = [
        ("Work", user_data.get("workContext", {})),
        ("Personal", user_data.get("personalContext", {})),
        ("Focus", user_data.get("topOfMind", {})),
        ("Recent", history_data.get("recentMonths", {})),
        ("Background", history_data.get("longTermBackground", {})),
    ]
    lines: list[str] = []
    for label, section in candidates:
        if not isinstance(section, dict):
            continue
        summary = _clean_summary(str(section.get("summary", "")))
        if summary:
            lines.append(f"- {label}: {summary}")
    return lines


def _score_fact(fact: dict[str, Any], *, current_terms: set[str]) -> float:
    content = fact.get("content")
    if not isinstance(content, str) or not content.strip():
        return -1.0
    fact_terms = _extract_terms(content)
    confidence = _coerce_confidence(fact.get("confidence"), default=0.0)
    if not current_terms or not fact_terms:
        return confidence * 0.35
    overlap = len(current_terms & fact_terms)
    if overlap <= 0:
        return confidence * 0.15
    precision = overlap / len(fact_terms)
    recall = overlap / len(current_terms)
    similarity = (precision * 0.55) + (recall * 0.45)
    return (similarity * 0.75) + (confidence * 0.25)


def format_memory_for_injection(
    memory_data: dict[str, Any],
    current_user_message: str,
    *,
    max_tokens: int = 1200,
) -> str:
    if not isinstance(memory_data, dict):
        return ""

    sections: list[str] = []
    stable_lines = _stable_profile_lines(memory_data)
    if stable_lines:
        sections.append("Stable Profile:\n" + "\n".join(stable_lines))

    current_terms = _extract_terms(current_user_message or "")
    facts = memory_data.get("facts", [])
    ranked_facts: list[tuple[float, dict[str, Any]]] = []
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            score = _score_fact(fact, current_terms=current_terms)
            if score <= 0:
                continue
            if current_terms and score < 0.18:
                continue
            ranked_facts.append((score, fact))

    ranked_facts.sort(
        key=lambda item: (
            item[0],
            _coerce_confidence(item[1].get("confidence"), default=0.0),
        ),
        reverse=True,
    )

    fact_lines: list[str] = []
    max_fact_count = 8
    for _, fact in ranked_facts[:max_fact_count]:
        content = fact.get("content")
        if not isinstance(content, str):
            continue
        cleaned = _clean_summary(content)
        if not cleaned:
            continue
        category = str(fact.get("category", "context")).strip() or "context"
        confidence = _coerce_confidence(fact.get("confidence"), default=0.0)
        fact_lines.append(f"- [{category} | {confidence:.2f}] {cleaned}")

    if fact_lines:
        sections.append("Relevant Facts:\n" + "\n".join(fact_lines))

    if not sections:
        return ""

    result_sections: list[str] = []
    running = 0
    for section in sections:
        section_tokens = _count_tokens(section if not result_sections else "\n\n" + section)
        if result_sections and running + section_tokens > max_tokens:
            break
        if not result_sections and section_tokens > max_tokens:
            result_sections.append(section[: max(80, len(section) // 2)].rstrip() + "...")
            break
        result_sections.append(section)
        running += section_tokens

    result = "\n\n".join(result_sections)
    if _count_tokens(result) > max_tokens:
        approx_chars = max(120, int(len(result) * (max_tokens / max(_count_tokens(result), 1)) * 0.9))
        result = result[:approx_chars].rstrip() + "\n..."
    return result
