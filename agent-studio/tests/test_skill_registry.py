import importlib
import json

import pytest


REQUIRED_SKILL_NAMES = {
    "classify_message",
    "route_agent",
    "retrieve_knowledge",
    "summarize_thread",
    "plan_tools",
    "draft_reply",
    "score_confidence",
    "apply_guardrails",
    "create_approval_item",
}
SERIALIZED_FIELDS = {
    "name",
    "description",
    "category",
    "allowed_agents",
    "requires_model",
    "requires_tools",
    "risk_level",
}


def load_registry():
    try:
        return importlib.import_module("agent_studio.skill_registry")
    except ModuleNotFoundError as exc:
        pytest.fail(f"agent_studio.skill_registry is missing: {exc}")


def test_required_internal_skills_are_registered() -> None:
    registry = load_registry()

    definitions = registry.list_skill_definitions()
    by_name = {definition.name: definition for definition in definitions}

    assert set(by_name) == REQUIRED_SKILL_NAMES
    for skill_name in REQUIRED_SKILL_NAMES:
        assert registry.get_skill_definition(skill_name) == by_name[skill_name]


def test_skill_definitions_serialize_to_public_metadata_only() -> None:
    registry = load_registry()

    payload = [
        definition.model_dump(mode="json")
        for definition in registry.list_skill_definitions()
    ]

    assert payload
    for item in payload:
        assert set(item) == SERIALIZED_FIELDS
        assert item["name"] in REQUIRED_SKILL_NAMES
        assert isinstance(item["description"], str)
        assert item["description"]
        assert isinstance(item["category"], str)
        assert item["category"]
        assert isinstance(item["allowed_agents"], list)
        assert item["allowed_agents"]
        assert isinstance(item["requires_model"], bool)
        assert isinstance(item["requires_tools"], bool)
        assert item["risk_level"] in {"low", "medium", "high"}

    json.dumps(payload)


def test_allowed_agents_reference_known_internal_agents() -> None:
    registry = load_registry()

    known_agents = set(registry.list_internal_agent_names())

    assert {"agent_studio", "general_support", "sales_agent", "refund_resolver"}.issubset(
        known_agents
    )
    for definition in registry.list_skill_definitions():
        assert set(definition.allowed_agents).issubset(known_agents)


def test_unknown_skill_lookup_fails_closed() -> None:
    registry = load_registry()

    assert registry.get_skill_definition("chatwoot.conversations.resolve") is None
    assert registry.get_skill_definition("crm.lookup_contact") is None
    assert registry.get_skill_definition("missing_skill") is None

    diagnostic = registry.diagnose_skill_lookup("crm.lookup_contact")
    assert diagnostic["allowed"] is False
    assert diagnostic["reason"] == "unknown_skill"
    assert diagnostic["skill"] is None


def test_graph_stage_helpers_select_internal_skills_only() -> None:
    registry = load_registry()

    assert [skill.name for skill in registry.skills_for_graph_stage("classify")] == [
        "classify_message"
    ]
    assert [skill.name for skill in registry.skills_for_graph_stage("select_agent")] == [
        "route_agent"
    ]
    assert [skill.name for skill in registry.skills_for_graph_stage("qa_compliance")] == [
        "score_confidence",
        "apply_guardrails",
        "create_approval_item",
    ]

    diagnostic = registry.diagnose_graph_stage("provider_tool_execution")
    assert diagnostic["allowed"] is False
    assert diagnostic["reason"] == "unknown_stage"
    assert diagnostic["skills"] == []


def test_registry_does_not_expose_provider_credentials_or_tool_schemas() -> None:
    registry = load_registry()

    serialized = json.dumps(
        [
            definition.model_dump(mode="json")
            for definition in registry.list_skill_definitions()
        ],
    ).lower()

    blocked_markers = {
        "api_access_token",
        "api_key",
        "webhook_token",
        "base_url",
        "input_schema",
        "parameters",
        '"function"',
        "crm.lookup_contact",
        "chatwoot.",
        "twenty.",
        "litellm",
    }
    for marker in blocked_markers:
        assert marker not in serialized
