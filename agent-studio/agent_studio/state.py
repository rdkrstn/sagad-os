from typing import Literal, TypedDict

from agent_studio.schemas import CrmContactContext, KnowledgeHit, QaFinding, ToolPlan, ToolResult


class AgentStudioState(TypedDict, total=False):
    conversation_id: str
    chatwoot_conversation_id: str | None
    chatwoot_message_id: str | None
    customer_name: str
    channel: str
    incoming_message: str
    normalized_message: str
    intent: str
    risk_level: Literal["low", "medium", "high"]
    retrieved_knowledge: list[KnowledgeHit]
    crm_context: CrmContactContext | None
    tool_plans: list[ToolPlan]
    tool_results: list[ToolResult]
    draft_reply: str
    qa_findings: list[QaFinding]
    compliance_status: Literal["pass", "needs_review", "blocked"]
    approval_status: str
    trace_url: str | None
