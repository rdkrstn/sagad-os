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
# RevOps ticket lifecycle. A conversation IS a ticket; these stage the supervisor queue.
TicketStatus = Literal["open", "in_progress", "waiting", "resolved"]
TicketPriority = Literal["low", "medium", "high", "urgent"]
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
IntegrationProvider = Literal["chatwoot", "twenty", "ghl"] # TODO: Fetch from Agent Studio when API is available, and remove from the integration provider list. or should we create a new model for integration provider info that includes display name and other metadata?
KnowledgeSourceType = Literal[
    "manual_upload",
    "local_markdown_pack",
    "transcript_upload",
    "google_drive",
    "website",
    "external_kb",
]
KnowledgeIngestionStatus = Literal[
    "queued",
    "extracting",
    "needs_review",
    "embedding",
    "ready",
    "failed",
    "stale",
]
KnowledgeApprovalStatus = Literal["needs_review", "approved", "archived"]
KnowledgeFileEncoding = Literal["text", "base64"]


class KnowledgeHit(BaseModel):
    id: str
    title: str
    category: str
    source_path: str
    score: float
    excerpt: str


class MemoryHit(BaseModel):
    id: str = Field(default_factory=lambda: f"mem_{uuid4().hex[:12]}")
    memory_type: str
    content: str
    source: str = "conversation"
    score: float = 0.0
    conversation_id: str | None = None
    chatwoot_conversation_id: str | None = None
    source_message_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeIngestionFile(BaseModel):
    filename: str
    content: str
    encoding: KnowledgeFileEncoding = "text"
    category: str | None = None
    source_path: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class KnowledgeIngestionJobCreateRequest(BaseModel):
    source_name: str = "Manual Upload"
    source_type: KnowledgeSourceType = "manual_upload"
    files: list[KnowledgeIngestionFile]
    metadata: dict[str, object] = Field(default_factory=dict)


class KnowledgeSourceRecord(BaseModel):
    id: str
    source_type: KnowledgeSourceType
    name: str
    status: IntegrationStatus = "ready"
    sync_policy: str = "manual"
    last_synced_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeDocumentRecord(BaseModel):
    id: str
    source_id: str | None = None
    job_id: str | None = None
    pack_slug: str
    category: str
    source_path: str
    title: str
    content: str
    content_hash: str
    version: int = 1
    approval_status: KnowledgeApprovalStatus = "needs_review"
    chunk_count: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeIngestionErrorRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"kerr_{uuid4().hex[:12]}")
    job_id: str
    source_path: str
    error_code: str
    message: str
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeIngestionJobRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"kjob_{uuid4().hex[:12]}")
    source_id: str
    source_name: str
    source_type: KnowledgeSourceType
    status: KnowledgeIngestionStatus = "queued"
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    summary: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)
    errors: list[KnowledgeIngestionErrorRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeIngestionJobResponse(BaseModel):
    job: KnowledgeIngestionJobRecord
    documents: list[KnowledgeDocumentRecord] = Field(default_factory=list)
    errors: list[KnowledgeIngestionErrorRecord] = Field(default_factory=list)


class KnowledgeIngestionJobListResponse(BaseModel):
    jobs: list[KnowledgeIngestionJobRecord]


class KnowledgeSourceListResponse(BaseModel):
    sources: list[KnowledgeSourceRecord]


class KnowledgeDocumentListResponse(BaseModel):
    documents: list[KnowledgeDocumentRecord]


class KnowledgeSearchTestRequest(BaseModel):
    query: str
    intent: str = "general_support"
    risk_level: Literal["low", "medium", "high"] = "medium"
    limit: int = 4


class KnowledgeSearchTestResponse(BaseModel):
    hits: list[KnowledgeHit]


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
    deal_stage: str | None = None
    deal_value: str | None = None
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


class ChatwootInboxContext(BaseModel):
    id: str | None = None
    name: str | None = None
    channel_type: str | None = None
    provider: str | None = None


class ChatwootConversationContext(BaseModel):
    normalized_channel: str | None = None
    contact_last_seen_at: datetime | None = None
    agent_last_seen_at: datetime | None = None
    assignee_last_seen_at: datetime | None = None
    last_activity_at: datetime | None = None
    unread_count: int | None = None
    can_reply: bool | None = None
    source_id: str | None = None
    inbox: ChatwootInboxContext | None = None
    status: str | None = None
    priority: str | None = None
    labels: list[str] = Field(default_factory=list)
    waiting_since: datetime | None = None
    fetch_status: Literal["not_fetched", "ready", "failed", "unconfigured"] = "not_fetched"
    fetch_error: str | None = None
    fetched_at: datetime | None = None


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
    # Provider-native conversation id (GHL conversationId, etc.). Set by the universal inbound
    # pipeline so GHL approve-send + the poller can route back without Chatwoot-specific fields.
    provider_conversation_id: str | None = None
    customer_name: str = "Unknown customer"
    channel: str = "chatwoot"
    incoming_message: str
    normalized_message: str = ""
    intent: str = "unknown"
    risk_level: Literal["low", "medium", "high"] = "medium"
    selected_agent: str | None = None
    customer_driver: str | None = None
    retrieved_knowledge: list[KnowledgeHit] = Field(default_factory=list)
    retrieval_confidence: float | None = None
    missing_knowledge: bool = False
    retrieval_diagnostic: dict[str, object] = Field(default_factory=dict)
    memory_context: list[MemoryHit] = Field(default_factory=list)
    memory_diagnostic: dict[str, object] = Field(default_factory=dict)
    crm_context: CrmContactContext | None = None
    chatwoot_context: ChatwootConversationContext | None = None
    tool_plans: list[ToolPlan] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    draft_reply: str = ""
    qa_findings: list[QaFinding] = Field(default_factory=list)
    compliance_status: Literal["pass", "needs_review", "blocked"] = "needs_review"
    approval_status: ConversationStatus = "needs_approval"
    send_status: str = "not_sent"
    # RevOps ticket fields (see migrations/0008_tickets_revops.sql). Defaults preserve prior
    # behavior: a freshly-created conversation is an `open` ticket with no assignee/SLA.
    ticket_status: TicketStatus = "open"
    assignee: str | None = None
    priority: TicketPriority | None = None
    pipeline_stage: str | None = None
    sla_due_at: datetime | None = None
    trace_url: str | None = None
    eval_tags: list[str] = Field(default_factory=list)
    trace_attributes: dict[str, object] = Field(default_factory=dict)
    diagnostic_payload: dict[str, object] = Field(default_factory=dict)
    decision_reason: str | None = None
    guardrail_findings: list[QaFinding] = Field(default_factory=list)
    confidence_breakdown: dict[str, object] = Field(default_factory=dict)
    final_confidence_score: float | None = None
    quality_score: float | None = None
    quality_label: str | None = None
    quality_signals: dict[str, object] = Field(default_factory=dict)
    quality_notes: str | None = None
    quality_evaluated_at: datetime | None = None
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
    # GHL-specific display fields (nullable/False so chatwoot/twenty rows stay valid).
    location_id: str | None = None
    outbound_mode: str | None = None
    signature_scheme: str | None = None
    poll_enabled: bool | None = None
    poll_interval_seconds: int | None = None
    has_webhook_secret: bool = False
    has_native_webhook_key: bool = False
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
    # GHL-specific writable fields (ignored by chatwoot/twenty upserts).
    location_id: str | None = None
    outbound_mode: str | None = None
    signature_scheme: str | None = None
    poll_enabled: bool | None = None
    poll_interval_seconds: int | None = None
    poll_conversation_limit: int | None = None
    poll_message_limit: int | None = None
    webhook_secret: str | None = None
    native_webhook_key: str | None = None


class IntegrationConnectionTestResponse(BaseModel):
    provider: IntegrationProvider
    status: IntegrationStatus
    detail: str
    connection: IntegrationConnection


class ModelProviderConfigUpsertRequest(BaseModel):
    """Writable model-provider config (SuperAdmin console).

    Nullable fields mean "leave unchanged". Secret fields (openai_api_key, ...) are only
    written when a non-empty value is sent -- empty/None keeps the stored value.
    """

    chat_provider: str | None = None
    embedding_provider: str | None = None
    # Per-provider non-secret fields (keys match Settings field names).
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_embedding_model: str | None = None
    fireworks_base_url: str | None = None
    fireworks_model: str | None = None
    fireworks_embedding_model: str | None = None
    ollama_cloud_base_url: str | None = None
    ollama_cloud_model: str | None = None
    ollama_cloud_embedding_model: str | None = None
    openrouter_model: str | None = None
    litellm_base_url: str | None = None
    litellm_model: str | None = None
    litellm_embedding_model: str | None = None
    embedding_dimensions: int | None = None
    classifier_model: str | None = None
    guardrail_model: str | None = None
    extractor_model: str | None = None
    supervisor_model: str | None = None
    # Secrets (only written when non-empty).
    openai_api_key: str | None = None
    fireworks_api_key: str | None = None
    ollama_cloud_api_key: str | None = None
    openrouter_api_key: str | None = None
    litellm_master_key: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool = True
    supervisor_id: str = "dev-supervisor"
    edited_reply: str | None = None


class TicketUpdateRequest(BaseModel):
    # All fields optional; a field is left unchanged when omitted (None). ticket_status and
    # priority are validated against the DB CHECK constraints (migrations/0008) on write.
    ticket_status: TicketStatus | None = None
    assignee: str | None = None
    priority: TicketPriority | None = None
    pipeline_stage: str | None = None
    sla_due_at: datetime | None = None
    supervisor_id: str = "dev-supervisor"


class IntegrationSyncState(BaseModel):
    """Per-(organization, provider) watermark row backing the inbound pollers.

    ``updated_since`` is a millisecond epoch used as the GHL ``updatedSince`` cursor; ``payload``
    holds provider-specific sub-state (for GHL: a ``{"last_message_ids": {conversation_id:
    lastMessageId}}`` map). The poller only advances a watermark after the messages in that
    window have been successfully persisted, so a mid-cycle crash re-fetches (and dedup-skips)
    rather than drops messages.
    """

    model_config = ConfigDict(extra="ignore")

    organization_id: str | None = None
    provider: str
    updated_since: int = 0
    payload: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime | None = None


class CrmLookupContactRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    selected_agent: str | None = None
    approved: bool = True
    supervisor_id: str | None = None


class CrmCreateNoteRequest(BaseModel):
    contact_id: str
    note: str
    conversation_id: str | None = None
    selected_agent: str | None = None
    approved: bool = False
    supervisor_id: str | None = None


class CrmCreateTaskRequest(BaseModel):
    contact_id: str
    title: str
    due_at: datetime | None = None
    owner_id: str | None = None
    conversation_id: str | None = None
    selected_agent: str | None = None
    approved: bool = False
    supervisor_id: str | None = None


class CrmUpdateLeadStageRequest(BaseModel):
    contact_id: str
    lead_stage: str
    conversation_id: str | None = None
    selected_agent: str | None = None
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
