from pydantic import BaseModel, Field

from agent_studio.schemas import ToolRiskLevel
from agent_studio.tool_manifests import ToolManifest, ToolManifestRegistry


class ToolPolicyContext(BaseModel):
    selected_agent: str
    conversation_risk: ToolRiskLevel = "medium"
    approved: bool = False
    autonomous: bool = True
    provider_enabled: bool = True
    provider_configured: bool = False
    provider_dry_run: bool = True
    provider_writes_enabled: bool = False


class ToolPolicyDecision(BaseModel):
    tool_name: str
    allowed: bool
    requires_approval: bool
    dry_run: bool
    blocked_reason: str | None = None
    policy_reasons: list[str] = Field(default_factory=list)


def evaluate_tool_policy(
    tool_name: str,
    context: ToolPolicyContext,
    *,
    registry: ToolManifestRegistry | None = None,
) -> ToolPolicyDecision:
    manifest = (registry or ToolManifestRegistry()).get_manifest(tool_name)
    return evaluate_manifest_policy(manifest, context)


def evaluate_manifest_policy(
    manifest: ToolManifest,
    context: ToolPolicyContext,
) -> ToolPolicyDecision:
    reasons: list[str] = []
    dry_run = bool(manifest.dry_run_default)

    if not manifest.enabled:
        return ToolPolicyDecision(
            tool_name=manifest.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason="Tool is disabled by manifest.",
            policy_reasons=["Manifest disabled."],
        )

    if context.selected_agent not in manifest.allowed_agents:
        return ToolPolicyDecision(
            tool_name=manifest.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason=(
                f"{context.selected_agent} is not allowed to use {manifest.tool_name}."
            ),
            policy_reasons=["Selected agent is outside the tool allowlist."],
        )

    if not context.provider_enabled:
        return ToolPolicyDecision(
            tool_name=manifest.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason=f"{manifest.provider} is disabled for {manifest.tool_name}.",
            policy_reasons=["Provider disabled."],
        )

    if manifest.requires_approval and not context.approved:
        return ToolPolicyDecision(
            tool_name=manifest.tool_name,
            allowed=False,
            requires_approval=True,
            dry_run=True,
            blocked_reason="Supervisor approval is required before this tool can run.",
            policy_reasons=["Write tools require explicit approval."],
        )

    if not context.provider_configured:
        reasons.append("Provider unconfigured; tool may only produce a dry-run result.")
        dry_run = True
    elif manifest.mode == "write":
        if context.provider_dry_run:
            reasons.append("Provider dry-run is enabled.")
            dry_run = True
        elif not context.provider_writes_enabled:
            reasons.append("Provider live writes are disabled.")
            dry_run = True
        else:
            dry_run = False
    else:
        dry_run = False

    if (
        manifest.mode == "write"
        and context.conversation_risk == "high"
        and context.autonomous
        and not dry_run
    ):
        return ToolPolicyDecision(
            tool_name=manifest.tool_name,
            allowed=False,
            requires_approval=manifest.requires_approval,
            dry_run=True,
            blocked_reason="High-risk conversations cannot execute autonomous live writes.",
            policy_reasons=[
                "High-risk conversation.",
                "Autonomous live write blocked.",
                "Use human handling or dry-run.",
            ],
        )

    if not reasons:
        reasons.append("Policy allowed this tool for the selected agent and risk context.")

    return ToolPolicyDecision(
        tool_name=manifest.tool_name,
        allowed=True,
        requires_approval=manifest.requires_approval,
        dry_run=dry_run,
        policy_reasons=reasons,
    )
