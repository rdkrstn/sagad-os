"""Future MCP gateway helpers for Sagad OS Sprint 3.

This file intentionally does not start an MCP server. It defines the safe mapping
from Agent Studio tool manifests to MCP-style descriptors.

Design rule: MCP is a facade behind Agent Studio policy, not a bypass around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_studio.tool_policy import ToolCapabilityManifest


@dataclass(frozen=True)
class McpToolDescriptor:
    name: str
    title: str
    description: str
    input_schema: dict[str, object] = field(default_factory=dict)
    annotations: dict[str, object] = field(default_factory=dict)


def to_mcp_tool_descriptor(manifest: ToolCapabilityManifest) -> McpToolDescriptor:
    """Convert an approved Sagad tool manifest into an MCP-style descriptor."""
    annotations = {
        "provider": manifest.provider,
        "skill": manifest.skill_name,
        "mode": manifest.mode,
        "risk_level": manifest.risk_level,
        "requires_approval": manifest.requires_approval,
        "dry_run_default": manifest.dry_run_default,
        "sagad_policy_wrapped": True,
    }
    return McpToolDescriptor(
        name=manifest.tool_name,
        title=manifest.tool_name.replace(".", " ").title(),
        description=manifest.description or f"Policy-wrapped Sagad tool: {manifest.tool_name}",
        input_schema=manifest.input_schema or {"type": "object", "properties": {}},
        annotations=annotations,
    )


def list_exposable_mcp_tools(manifests: dict[str, ToolCapabilityManifest]) -> list[McpToolDescriptor]:
    """List tools that are safe to expose through a future MCP facade.

    Write tools may be listed only when their manifest declares an approval path.
    This prevents accidental exposure of unreviewed live actions.
    """
    descriptors: list[McpToolDescriptor] = []
    for manifest in manifests.values():
        if not manifest.enabled:
            continue
        if manifest.mode == "write" and not manifest.requires_approval:
            continue
        descriptors.append(to_mcp_tool_descriptor(manifest))
    return sorted(descriptors, key=lambda item: item.name)
