from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ConversationStatus = Literal[
    "needs_approval",
    "approved",
    "rejected",
    "sent",
    "send_failed",
]
IntegrationKind = Literal[
    "channel",
    "crm",
    "knowledge",
    "observability",
    "automation",
    "webhook",
    "tool_layer",
]
IntegrationStatus = Literal[
    "ready",
    "disabled",
    "unconfigured",
    "dry_run",
    "planned",
    "error",
    "blocked",
]

ToolExecutionStatus = Literal["planned", "dry_run", "blocked", "succeeded", "failed"]
ToolRiskLevel = Literal["low", "medium", "high"]
IntegrationProvider = Literal["chatwoot", "twenty"] # TODO: Fetch from Agent Studio when API is available, and remove from the integration provider list. or should we create a new model for integration provider info that includes display name and other metadata?


class KnowledgeHit(BaseModel):
    id: str
    title: str
    category: str
    source_path: str
    score: float
    excerpt: str


class QaFinding(BaseModel):
    label: str
    status: Literal["pass", "watch", "fail"]
    detail: str


class ExternalIntegrationStatus(BaseModel):
    provider: str
    kind: IntegrationKind
    status: IntegrationStatus
    external: bool = True
    base_url: str | None = None
    mode: str | None = None
    dry_run: bool = True
    writes_enabled: bool = False
    detail: str


class CrmProviderStatus(ExternalIntegrationStatus):
    provider: str = "Twenty CRM"
    kind: IntegrationKind = "crm"

class CrmContactContext(BaseModel):
    provider: str = "Twenty CRM"
    status: IntegrationStatus = "unconfigured"
    contact_id: str | None = None
    display_name: str | None = None
    company_name: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None
    phone_masked: str | None = None
    email_masked: str | None = None
    lead_stage: str | None = None
    last_contacted_at: datetime | None = None
    social_profiles: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    service_history: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, object] = Field(default_factory=dict)

# todo: Consider adding a ToolPlanResult model that combines the plan and result for easier correlation, and includes additional metadata such as execution timestamps and error details if applicable. This could simplify the tracking of tool executions and their outcomes in the conversation record.
class ToolPlan(BaseModel):
    id: str = Field(default_factory=lambda: f"toolplan_{uuid4().hex[:12]}")
    provider: str = "Twenty CRM"
    tool_name: str
    action: str
    risk_level: ToolRiskLevel = "medium"
    requires_approval: bool = True
    approved: bool = False
    dry_run: bool = True
    args: dict[str, object] = Field(default_factory=dict)


class ToolResult(BaseModel):
    id: str = Field(default_factory=lambda: f"toolresult_{uuid4().hex[:12]}")
    plan_id: str
    provider: str = "Twenty CRM"
    tool_name: str
    status: ToolExecutionStatus
    detail: str
    external_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class DiagnosticEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"event_{uuid4().hex[:12]}")
    organization_id: str | None = None
    conversation_id: str | None = None
    event_type: str
    actor_type: str = "system"
    actor_id: str | None = None
    status: Literal["info", "success", "warning", "error"] = "info"
    summary: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatwootWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str | None = None
    content: str | None = None
    message_type: str | None = None
    private: bool | None = None
    id: int | str | None = None
    conversation: dict[str, object] | None = None
    sender: dict[str, object] | None = None
    inbox: dict[str, object] | None = None


class IgnoredWebhookResponse(BaseModel):
    status: Literal["ignored"] = "ignored"
    reason: str


class ConversationMessageRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    sender_type: Literal["customer", "ai_agent", "human_agent", "system", "tool"] = "customer"
    body: str
    external_message_id: str | None = None
    provider: str | None = "chatwoot"
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"conv_{uuid4().hex[:12]}")
    chatwoot_conversation_id: str | None = None
    chatwoot_message_id: str | None = None
    customer_name: str = "Unknown customer"
    channel: str = "chatwoot"
    incoming_message: str
    normalized_message: str = ""
    intent: str = "unknown"
    risk_level: Literal["low", "medium", "high"] = "medium"
    retrieved_knowledge: list[KnowledgeHit] = Field(default_factory=list)
    crm_context: CrmContactContext | None = None
    tool_plans: list[ToolPlan] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    draft_reply: str = ""
    qa_findings: list[QaFinding] = Field(default_factory=list)
    compliance_status: Literal["pass", "needs_review", "blocked"] = "needs_review"
    approval_status: ConversationStatus = "needs_approval"
    send_status: str = "not_sent"
    trace_url: str | None = None
    messages: list[ConversationMessageRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationListResponse(BaseModel):
    conversations: list[ConversationRecord]


class DiagnosticEventListResponse(BaseModel):
    events: list[DiagnosticEvent]


class IntegrationListResponse(BaseModel):
    integrations: list[ExternalIntegrationStatus]


class IntegrationConnection(BaseModel):
    provider: IntegrationProvider
    name: str
    kind: IntegrationKind
    status: IntegrationStatus
    configured: bool = False
    enabled: bool = False
    external: bool = True
    base_url: str | None = None
    account_id: str | None = None
    inbox_id: str | None = None
    api_mode: str | None = None
    dry_run: bool = True
    writes_enabled: bool = False
    has_api_access_token: bool = False
    has_webhook_token: bool = False
    has_api_key: bool = False
    missing: list[str] = Field(default_factory=list)
    detail: str
    updated_at: datetime | None = None


class IntegrationConnectionListResponse(BaseModel):
    connections: list[IntegrationConnection]


class IntegrationConnectionUpsertRequest(BaseModel):
    base_url: str | None = None
    account_id: str | None = None
    inbox_id: str | None = None
    api_access_token: str | None = None
    webhook_token: str | None = None
    api_key: str | None = None
    api_mode: str | None = "graphql"
    enabled: bool = True
    dry_run: bool = True
    allow_writes: bool = False


class IntegrationConnectionTestResponse(BaseModel):
    provider: IntegrationProvider
    status: IntegrationStatus
    detail: str
    connection: IntegrationConnection


class ApprovalRequest(BaseModel):
    approved: bool = True
    supervisor_id: str = "dev-supervisor"
    edited_reply: str | None = None


class CrmLookupContactRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    approved: bool = True
    supervisor_id: str | None = None


class CrmCreateNoteRequest(BaseModel):
    contact_id: str
    note: str
    conversation_id: str | None = None
    approved: bool = False
    supervisor_id: str | None = None


class CrmCreateTaskRequest(BaseModel):
    contact_id: str
    title: str
    due_at: datetime | None = None
    owner_id: str | None = None
    conversation_id: str | None = None
    approved: bool = False
    supervisor_id: str | None = None


class CrmUpdateLeadStageRequest(BaseModel):
    contact_id: str
    lead_stage: str
    conversation_id: str | None = None
    approved: bool = False
    supervisor_id: str | None = None


class CrmToolResponse(BaseModel):
    plan: ToolPlan
    result: ToolResult
    crm_context: CrmContactContext | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str
    knowledge_records: int
    chatwoot_send_enabled: bool
    twenty_status: CrmProviderStatus
