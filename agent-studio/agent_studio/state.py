from typing import Literal, TypedDict

from agent_studio.schemas import (
    ConversationMessageRecord,
    CrmContactContext,
    KnowledgeHit,
    MemoryHit,
    QaFinding,
    ToolPlan,
    ToolResult,
)


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
    selected_agent: str | None
    customer_driver: str | None
    conversation_history: list[ConversationMessageRecord]
    memory_context: list[MemoryHit]
    memory_diagnostic: dict[str, object]
    retrieved_knowledge: list[KnowledgeHit]
    retrieval_confidence: float | None
    missing_knowledge: bool
    retrieval_diagnostic: dict[str, object]
    crm_context: CrmContactContext | None
    tool_plans: list[ToolPlan]
    tool_results: list[ToolResult]
    draft_reply: str
    qa_findings: list[QaFinding]
    compliance_status: Literal["pass", "needs_review", "blocked"]
    approval_status: str
    trace_url: str | None
    eval_tags: list[str]
    trace_attributes: dict[str, object]
    diagnostic_payload: dict[str, object]
    decision_reason: str | None
    guardrail_findings: list[QaFinding]
    confidence_breakdown: dict[str, object]
    final_confidence_score: float | None
    quality_score: float | None
    quality_label: str | None
    quality_signals: dict[str, object]
    quality_notes: str | None
    routed_agent: str | None
    sub_agent_report: dict[str, object]
    supervisor_decision: dict[str, object]
    tool_requests: list[dict[str, object]]
    tool_outputs: list[dict[str, object]]
    # --- Supervisor/handoff orchestration (Phase 3) ---
    # `handoff_to` is set by the supervisor node to transfer control to another sub-agent; the
    # conditional edge `_supervisor_route` maps it back to the matching sub-agent node. Cleared
    # (None) when the supervisor finalizes to `supervisor_draft`.
    handoff_to: str | None
    # Ordered list of agent keys the supervisor has delegated to (e.g. ["refund_resolver"]).
    # Bounded by `MAX_DELEGATIONS` to prevent infinite agent->agent handoff loops.
    delegation_chain: list[str]
    # Per-agent transcript: each entry is {"agent": <key>, "report": <sub_agent_report>} recorded
    # by the supervisor as it inspects each sub-agent's report before finalizing or handing off.
    agent_messages: list[dict[str, object]]

