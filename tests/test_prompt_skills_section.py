from __future__ import annotations

from pathlib import Path

from harness.agents.prompt import build_system_instructions, get_skills_prompt_section
from harness.skills.types import Skill


def test_get_skills_prompt_section_contains_skill_locations():
    skill = Skill(
        name="example",
        description="Example skill",
        license=None,
        skill_dir=Path("/tmp/skills/public/example"),
        skill_file=Path("/tmp/skills/public/example/SKILL.md"),
        relative_path=Path("example"),
        category="public",
        enabled=True,
    )

    section = get_skills_prompt_section([skill], container_base_path="skills")

    assert "<skill_system>" in section
    assert "<name>example</name>" in section
    assert "<location>skills/public/example/SKILL.md</location>" in section
    assert "references or scripts in the same folder" in section


def test_build_system_instructions_includes_skills_section_when_present():
    skill = Skill(
        name="example",
        description="Example skill",
        license=None,
        skill_dir=Path("/tmp/skills/public/example"),
        skill_file=Path("/tmp/skills/public/example/SKILL.md"),
        relative_path=Path("example"),
        category="public",
        enabled=True,
    )

    instructions = build_system_instructions([skill])
    assert "You are a local desktop assistant embodied as a living character companion" in instructions
    assert "<available_skills>" in instructions


def test_build_system_instructions_includes_long_term_memory_when_present():
    instructions = build_system_instructions([], memory_text="Stable Profile:\n- Personal: Prefers concise replies")

    assert "<long_term_memory>" in instructions
    assert "Prefers concise replies" in instructions


def test_build_system_instructions_includes_browser_tool_governance():
    instructions = build_system_instructions([])

    assert "Some runs expose local browser-opening tools such as browser_search and browser_open." in instructions
    assert "Local browser-opening tools only perform host browser actions" in instructions
    assert "Do not say that a browser page was opened unless the corresponding browser tool call actually succeeded." in instructions


def test_build_system_instructions_switches_to_playwright_browser_governance():
    instructions = build_system_instructions([], local_browser_enabled=False, playwright_mcp_enabled=True)

    assert "Playwright MCP browser tools are available in this run." in instructions
    assert "browser_search and browser_open are intentionally not registered" in instructions
    assert "prefer the visible Playwright-prefixed tools instead" in instructions


def test_build_system_instructions_includes_reminder_tool_governance():
    instructions = build_system_instructions([])

    assert "<runtime_clock>" in instructions
    assert "When the user asks for a reminder, timer, alarm, countdown, wake-up, or later notification" in instructions
    assert "Never claim that a reminder has been scheduled unless create_reminder actually succeeded." in instructions


def test_build_system_instructions_discourages_stage_directions_for_task_completion():
    instructions = build_system_instructions([])

    assert "Prefer no stage directions at all for routine task completion" in instructions
    assert "When a task is finished, prefer a short in-character confirmation over a narrated scene." in instructions


def test_build_system_instructions_preserves_pinned_skill_priority():
    instructions = build_system_instructions([], pinned_skills=["roxy-skill"])

    assert "Previously selected skills in this session: roxy-skill." in instructions
    assert "Do not let the base assistant tone override the pinned skill's persona." in instructions
