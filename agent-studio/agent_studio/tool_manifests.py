from typing import Literal

from pydantic import BaseModel, Field

from agent_studio.schemas import ToolRiskLevel


ToolMode = Literal["read", "write", "dry_run"]

DEFAULT_TOOL_NAMES = [
    "knowledge.search",
    "crm.lookup_contact",
    "crm.create_note",
    "crm.create_task",
    "crm.update_lead_stage",
    "chatwoot.messages.send_approved",
    "chatwoot.conversations.resolve",
]


class ToolManifest(BaseModel):
    tool_name: str
    provider: str
    skill_name: str
    mode: ToolMode
    risk_level: ToolRiskLevel
    allowed_agents: list[str]
    requires_approval: bool
    enabled: bool = True
    dry_run_default: bool = True
    input_schema: dict[str, object] = Field(default_factory=dict)
    description: str


def _schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _default_manifests() -> list[ToolManifest]:
    support_sales = [
        "Support Agent",
        "Sales Agent",
        "Refund Resolver",
        "general_support",
        "sales_agent",
        "refund_resolver",
    ]
    return [
        ToolManifest(
            tool_name="knowledge.search",
            provider="Sagad Knowledge",
            skill_name="retrieve_knowledge",
            mode="read",
            risk_level="low",
            allowed_agents=support_sales,
            requires_approval=False,
            dry_run_default=False,
            description="Search approved Sagad knowledge and SOP sources.",
            input_schema=_schema(
                {
                    "query": {"type": "string"},
                    "intent": {"type": "string"},
                    "risk_level": {"type": "string"},
                },
                ["query"],
            ),
        ),
        ToolManifest(
            tool_name="crm.lookup_contact",
            provider="Twenty CRM",
            skill_name="plan_tools",
            mode="read",
            risk_level="low",
            allowed_agents=support_sales,
            requires_approval=False,
            dry_run_default=False,
            description="Look up a customer contact in Twenty CRM.",
            input_schema=_schema({"query": {"type": "string"}}, ["query"]),
        ),
        ToolManifest(
            tool_name="crm.create_note",
            provider="Twenty CRM",
            skill_name="plan_tools",
            mode="write",
            risk_level="medium",
            allowed_agents=support_sales,
            requires_approval=True,
            description="Create a supervisor-approved note in Twenty CRM.",
            input_schema=_schema(
                {
                    "contact_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                ["contact_id", "note"],
            ),
        ),
        ToolManifest(
            tool_name="crm.create_task",
            provider="Twenty CRM",
            skill_name="plan_tools",
            mode="write",
            risk_level="medium",
            allowed_agents=support_sales,
            requires_approval=True,
            description="Create a supervisor-approved follow-up task in Twenty CRM.",
            input_schema=_schema(
                {
                    "contact_id": {"type": "string"},
                    "title": {"type": "string"},
                },
                ["contact_id", "title"],
            ),
        ),
        ToolManifest(
            tool_name="crm.update_lead_stage",
            provider="Twenty CRM",
            skill_name="plan_tools",
            mode="write",
            risk_level="high",
            allowed_agents=["Sales Agent", "sales_agent"],
            requires_approval=True,
            description="Update a sales lead stage in Twenty CRM after approval.",
            input_schema=_schema(
                {
                    "contact_id": {"type": "string"},
                    "lead_stage": {"type": "string"},
                },
                ["contact_id", "lead_stage"],
            ),
        ),
        ToolManifest(
            tool_name="chatwoot.messages.send_approved",
            provider="Chatwoot",
            skill_name="create_approval_item",
            mode="write",
            risk_level="medium",
            allowed_agents=support_sales,
            requires_approval=True,
            description="Send the supervisor-approved reply to Chatwoot.",
            input_schema=_schema(
                {
                    "conversation_id": {"type": "string"},
                    "edited_reply": {"type": "string"},
                },
                ["conversation_id"],
            ),
        ),
        ToolManifest(
            tool_name="chatwoot.conversations.resolve",
            provider="Chatwoot",
            skill_name="create_approval_item",
            mode="write",
            risk_level="medium",
            allowed_agents=support_sales,
            requires_approval=True,
            description="Resolve a Chatwoot conversation after supervisor action.",
            input_schema=_schema({"conversation_id": {"type": "string"}}, ["conversation_id"]),
        ),
    ]


class ToolManifestRegistry:
    def __init__(self, manifests: list[ToolManifest] | None = None) -> None:
        self._manifests = {
            manifest.tool_name: manifest for manifest in (manifests or _default_manifests())
        }

    def list_manifests(self) -> list[ToolManifest]:
        return [
            self._manifests[name]
            for name in DEFAULT_TOOL_NAMES
            if name in self._manifests
        ]

    def get_manifest(self, tool_name: str) -> ToolManifest:
        if tool_name not in self._manifests:
            raise KeyError(tool_name)
        return self._manifests[tool_name]
