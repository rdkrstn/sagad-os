from agent_studio.tool_policy import ToolCallRequest, evaluate_tool_call


def test_read_tool_allowed_without_approval() -> None:
    decision = evaluate_tool_call(
        ToolCallRequest(
            tool_name="knowledge.search",
            selected_agent="support",
            conversation_risk_level="low",
        ),
    )
    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.dry_run is False


def test_unknown_tool_blocked() -> None:
    decision = evaluate_tool_call(
        ToolCallRequest(
            tool_name="shell.exec",
            selected_agent="support",
            conversation_risk_level="high",
        ),
    )
    assert decision.allowed is False
    assert decision.blocked_reason == "tool is not registered"


def test_write_tool_requires_approval_and_dry_runs() -> None:
    decision = evaluate_tool_call(
        ToolCallRequest(
            tool_name="crm.create_note",
            selected_agent="support",
            conversation_risk_level="medium",
            approved=False,
            live_writes_enabled=True,
        ),
    )
    assert decision.allowed is True
    assert decision.requires_approval is True
    assert decision.dry_run is True


def test_high_risk_unapproved_write_blocked() -> None:
    decision = evaluate_tool_call(
        ToolCallRequest(
            tool_name="crm.update_lead_stage",
            selected_agent="sales",
            conversation_risk_level="high",
            approved=False,
            live_writes_enabled=True,
        ),
    )
    assert decision.allowed is False
    assert decision.blocked_reason == "high-risk write requires explicit approval"


def test_agent_scope_enforced() -> None:
    decision = evaluate_tool_call(
        ToolCallRequest(
            tool_name="crm.update_lead_stage",
            selected_agent="support",
            conversation_risk_level="medium",
            approved=True,
            live_writes_enabled=True,
        ),
    )
    assert decision.allowed is False
    assert "selected agent" in str(decision.blocked_reason)
