import pytest

from agent_studio.skill_registry import SkillRegistry


def test_default_registry_lists_support_skills() -> None:
    registry = SkillRegistry()
    skills = registry.list_for_agent("support")
    names = {skill.name for skill in skills}
    assert "retrieve_knowledge" in names
    assert "apply_guardrails" in names


def test_require_known_skill_for_agent() -> None:
    registry = SkillRegistry()
    skill = registry.require("draft_reply", agent="sales")
    assert skill.name == "draft_reply"


def test_unknown_skill_raises_key_error() -> None:
    registry = SkillRegistry()
    with pytest.raises(KeyError):
        registry.require("unknown_skill", agent="support")
