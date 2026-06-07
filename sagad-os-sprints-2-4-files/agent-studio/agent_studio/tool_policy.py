"""Server-side tool policy primitives for Sagad OS Sprint 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ToolMode = Literal["read", "write", "dry_run"]
ToolRiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ToolCapabilityManifest:
    tool_name: str
    provider: str
    skill_name: str
    mode: ToolMode
    risk_level: ToolRiskLevel
    allowed_agents: list[str]
    requires_approval: bool = False
    enabled: bool = True
    dry_run_default: bool = True
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallRequest:
    tool_name: str
    selected_agent: str
    conversation_risk_level: ToolRiskLevel
    approved: bool = False
    live_writes_enabled: bool = False
    workspace_enabled: bool = True


@dataclass(frozen=True)
class ToolPolicyDecision:
    tool_name: str
    allowed: bool
    requires_approval: bool
    dry_run: bool
    blocked_reason: str | None = None
    policy_reasons: list[str] = field(default_factory=list)


DEFAULT_TOOL_MANIFESTS: dict[str, ToolCapabilityManifest] = {
    "knowledge.search": ToolCapabilityManifest(
        tool_name="knowledge.search",
        provider="Sagad Knowledge",
        skill_name="retrieve_knowledge",
        mode="read",
        risk_level="low",
        allowed_agents=["sales", "support"],
        requires_approval=False,
        dry_run_default=False,
        description="Search approved knowledge sources.",
    ),
    "crm.lookup_contact": ToolCapabilityManifest(
        tool_name="crm.lookup_contact",
        provider="Twenty CRM",
        skill_name="lookup_customer_context",
        mode="read",
        risk_level="medium",
        allowed_agents=["sales", "support"],
        requires_approval=False,
        dry_run_default=True,
        description="Look up masked customer context from CRM.",
    ),
    "crm.create_note": ToolCapabilityManifest(
        tool_name="crm.create_note",
        provider="Twenty CRM",
        skill_name="write_customer_note",
        mode="write",
        risk_level="medium",
        allowed_agents=["sales", "support"],
        requires_approval=True,
        dry_run_default=True,
        description="Create a CRM note after supervisor approval.",
    ),
    "crm.create_task": ToolCapabilityManifest(
        tool_name="crm.create_task",
        provider="Twenty CRM",
        skill_name="create_followup_task",
        mode="write",
        risk_level="medium",
        allowed_agents=["sales", "support"],
        requires_approval=True,
        dry_run_default=True,
        description="Create a CRM task after supervisor approval.",
    ),
    "crm.update_lead_stage": ToolCapabilityManifest(
        tool_name="crm.update_lead_stage",
        provider="Twenty CRM",
        skill_name="update_pipeline_stage",
        mode="write",
        risk_level="high",
        allowed_agents=["sales"],
        requires_approval=True,
        dry_run_default=True,
        description="Update lead stage after explicit approval.",
    ),
    "chatwoot.send_approved_reply": ToolCapabilityManifest(
        tool_name="chatwoot.send_approved_reply",
        provider="Chatwoot",
        skill_name="send_approved_reply",
        mode="write",
        risk_level="medium",
        allowed_agents=["sales", "support"],
        requires_approval=True,
        dry_run_default=True,
        description="Send supervisor-approved reply to Chatwoot.",
    ),
}


def evaluate_tool_call(
    request: ToolCallRequest,
    manifests: dict[str, ToolCapabilityManifest] | None = None,
) -> ToolPolicyDecision:
    registry = manifests or DEFAULT_TOOL_MANIFESTS
    manifest = registry.get(request.tool_name)
    reasons: list[str] = []
    if manifest is None:
        return ToolPolicyDecision(
            tool_name=request.tool_name,
            allowed=False,
            requires_approval=False,
            dry_run=True,
            blocked_reason="tool is not registered",
            policy_reasons=["unknown tool blocked"],
        )
    if not manifest.enabled:
        return ToolPolicyDecision(
            tool_name=request.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason="tool is disabled",
            policy_reasons=["disabled manifest"],
        )
    if not request.workspace_enabled:
        return ToolPolicyDecision(
            tool_name=request.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason="tool is disabled for workspace",
            policy_reasons=["workspace disabled"],
        )
    if request.selected_agent not in manifest.allowed_agents:
        return ToolPolicyDecision(
            tool_name=request.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason="selected agent is not allowed to use this tool",
            policy_reasons=[f"allowed agents: {', '.join(manifest.allowed_agents)}"],
        )

    requires_approval = manifest.requires_approval or manifest.mode == "write"
    if requires_approval and not request.approved:
        reasons.append("approval required before live execution")

    high_risk_write = manifest.mode == "write" and request.conversation_risk_level == "high"
    if high_risk_write and not request.approved:
        reasons.append("high-risk conversation blocks unapproved write")

    dry_run = manifest.dry_run_default or manifest.mode == "dry_run"
    if manifest.mode == "write" and request.live_writes_enabled and request.approved and not high_risk_write:
        dry_run = False
    if manifest.mode == "read" and not manifest.dry_run_default:
        dry_run = False

    allowed = True
    blocked_reason = None
    if high_risk_write and not request.approved:
        allowed = False
        blocked_reason = "high-risk write requires explicit approval"
    elif requires_approval and not request.approved:
        allowed = True
        dry_run = True

    if manifest.mode == "read":
        reasons.append("read tool allowed through server-side policy")
    elif dry_run:
        reasons.append("tool execution is dry-run until approval/live writes are enabled")
    else:
        reasons.append("approved live write allowed")

    return ToolPolicyDecision(
        tool_name=request.tool_name,
        allowed=allowed,
        requires_approval=requires_approval,
        dry_run=dry_run,
        blocked_reason=blocked_reason,
        policy_reasons=reasons,
    )
