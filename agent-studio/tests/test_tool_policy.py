from agent_studio.tool_manifests import DEFAULT_TOOL_NAMES, ToolManifestRegistry
from agent_studio.tool_policy import ToolPolicyContext, evaluate_tool_policy


def test_default_tool_manifests_cover_current_execution_surface() -> None:
    registry = ToolManifestRegistry()

    assert [manifest.tool_name for manifest in registry.list_manifests()] == DEFAULT_TOOL_NAMES
    for manifest in registry.list_manifests():
        assert manifest.provider
        assert manifest.skill_name
        assert manifest.mode in {"read", "write", "dry_run"}
        assert manifest.risk_level in {"low", "medium", "high"}
        assert manifest.allowed_agents
        assert isinstance(manifest.requires_approval, bool)
        assert isinstance(manifest.enabled, bool)
        assert isinstance(manifest.dry_run_default, bool)
        assert isinstance(manifest.input_schema, dict)
        assert manifest.description


def test_read_tool_allowed_for_allowed_agent_without_approval() -> None:
    decision = evaluate_tool_policy(
        "crm.lookup_contact",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="medium",
            approved=False,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=False,
        ),
    )

    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.dry_run is False
    assert decision.blocked_reason is None


def test_write_tool_requires_approval_before_execution() -> None:
    decision = evaluate_tool_policy(
        "crm.create_note",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="low",
            approved=False,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=True,
        ),
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "approval" in str(decision.blocked_reason).lower()


def test_high_risk_conversation_blocks_live_write_even_when_approved() -> None:
    decision = evaluate_tool_policy(
        "crm.update_lead_stage",
        ToolPolicyContext(
            selected_agent="Sales Agent",
            conversation_risk="high",
            approved=True,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=True,
        ),
    )

    assert decision.allowed is False
    assert decision.dry_run is True
    assert "high-risk" in str(decision.blocked_reason).lower()


def test_high_risk_conversation_blocks_live_autonomous_write_for_any_write_tool() -> None:
    decision = evaluate_tool_policy(
        "crm.create_note",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="high",
            approved=True,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=True,
            autonomous=True,
        ),
    )

    assert decision.allowed is False
    assert decision.dry_run is True
    assert "high-risk" in str(decision.blocked_reason).lower()
    assert "autonomous" in str(decision.blocked_reason).lower()


def test_supervised_high_risk_live_write_can_pass_when_approved() -> None:
    decision = evaluate_tool_policy(
        "crm.create_note",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="high",
            approved=True,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=True,
            autonomous=False,
        ),
    )

    assert decision.allowed is True
    assert decision.dry_run is False


def test_unconfigured_provider_forces_dry_run_decision() -> None:
    decision = evaluate_tool_policy(
        "chatwoot.messages.send_approved",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="medium",
            approved=True,
            provider_configured=False,
            provider_dry_run=False,
            provider_writes_enabled=False,
        ),
    )

    assert decision.allowed is True
    assert decision.dry_run is True
    assert any("unconfigured" in reason.lower() for reason in decision.policy_reasons)


def test_disabled_provider_blocks_decision() -> None:
    decision = evaluate_tool_policy(
        "crm.lookup_contact",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="medium",
            approved=False,
            provider_configured=True,
            provider_enabled=False,
            provider_dry_run=False,
            provider_writes_enabled=False,
        ),
    )

    assert decision.allowed is False
    assert decision.dry_run is True
    assert "disabled" in str(decision.blocked_reason).lower()


def test_agent_allowlist_is_enforced() -> None:
    decision = evaluate_tool_policy(
        "crm.update_lead_stage",
        ToolPolicyContext(
            selected_agent="Support Agent",
            conversation_risk="low",
            approved=True,
            provider_configured=True,
            provider_dry_run=False,
            provider_writes_enabled=True,
        ),
    )

    assert decision.allowed is False
    assert "not allowed" in str(decision.blocked_reason).lower()
