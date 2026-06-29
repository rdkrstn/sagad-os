from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import asyncio
import logging
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
from fastapi import Body, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_studio.chatwoot import (
    chatwoot_context_from_payload,
    fetch_conversation_details,
    resolve_conversation,
    send_approved_reply,
)
from agent_studio.chatwoot_mapping import channel_from_payload
from agent_studio.adapters import get_adapter, registered_providers
from agent_studio.adapters.base import ChannelAdapter, NormalizedInbound
from agent_studio.webhook_debounce import DebounceCoordinator
from agent_studio.config import Settings
from agent_studio.config import get_settings
from agent_studio.db import TrustedContext, database_ready, initialize_database_safe
from agent_studio.evals import built_in_eval_cases, run_fixture_evals
from agent_studio.graph import graph, get_agent_registry
from agent_studio.integration_config import (
    ADMIN_ROLES,
    configured_settings,
    connection_test_result,
    integration_connections_for_display,
    integration_config_store,
)
from agent_studio.ingestion import KnowledgeIngestionService, build_knowledge_ingestion_store
from agent_studio.memory_workflow import memory_items_from_record
from agent_studio.mcp_gateway import build_mcp_descriptors
from agent_studio.model_config import (
    provider_status,
    resolve_chat_config,
    resolve_embedding_config,
)
from agent_studio.model_provider_config import (
    model_provider_config_store,
    model_provider_config_view,
)
from agent_studio.observability import aggregate_ai_ops_metrics, sanitize_payload
from agent_studio.realtime import realtime_manager, verify_realtime_token
from agent_studio.retrieval import retriever
from agent_studio.revops_autosend import revops_autosend_decision
from agent_studio.schemas import (
    ApprovalRequest,
    ChatwootWebhookPayload,
    ConversationMessageRecord,
    ConversationListResponse,
    ConversationRecord,
    CrmCreateNoteRequest,
    CrmCreateTaskRequest,
    CrmLookupContactRequest,
    CrmContactContext,
    CrmProviderStatus,
    CrmToolResponse,
    CrmUpdateLeadStageRequest,
    DiagnosticEvent,
    DiagnosticEventListResponse,
    ExternalIntegrationStatus,
    HealthResponse,
    IgnoredWebhookResponse,
    IntegrationConnection,
    IntegrationConnectionListResponse,
    IntegrationConnectionTestResponse,
    IntegrationConnectionUpsertRequest,
    IntegrationListResponse,
    IntegrationProvider,
    ModelProviderConfigUpsertRequest,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentRecord,
    KnowledgeIngestionJobCreateRequest,
    KnowledgeIngestionJobListResponse,
    KnowledgeIngestionJobResponse,
    KnowledgeSearchTestRequest,
    KnowledgeSearchTestResponse,
    KnowledgeSourceListResponse,
    ToolPlan,
    ToolResult,
    TicketUpdateRequest,
    TICKET_STATUS_TRANSITIONS,
    compute_sla_status,
)
from agent_studio.skill_registry import list_skill_definitions
from agent_studio.store import StoreContext, store
from agent_studio.tool_manifests import ToolManifestRegistry
from agent_studio.tool_policy import ToolPolicyContext, ToolPolicyDecision, evaluate_tool_policy
from agent_studio.twenty import TwentyAdapter, twenty_status


# Handle to the background GHL poller, if started. Stopped on lifespan shutdown.
_ghl_poller: Any | None = None


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    # Startup must never crash the process. If the DB is briefly unreachable or a migration
    # errors, we log it and keep serving (so /health/live stays 200 = container "healthy"),
    # while /health/ready reports not-ready. A background task retries until the DB recovers,
    # so a slow-to-start Postgres self-heals without a container restart.
    settings = get_settings()
    initialize_database_safe(settings)
    asyncio.create_task(_retry_database_init(settings))
    # GHL inbound poller: opt-in via GHL_POLL_ENABLED. The poller feeds the SAME
    # _run_universal_inbound pipeline as the /webhooks/ghl route (no parallel graph path) and
    # degrades safely when GHL is unconfigured or the DB is not ready. Started here so a live
    # deploy can poll GHL without the native Marketplace webhook; off by default for CI/tests.
    global _ghl_poller
    if settings.ghl_poll_enabled:
        from agent_studio.ghl_poller import run_ghl_poller

        try:
            _ghl_poller = await run_ghl_poller(settings)
        except Exception as exc:  # noqa: BLE001 - startup must never crash the process
            logger.warning("GHL poller failed to start: %s", exc.__class__.__name__)
    yield
    if _ghl_poller is not None:
        _ghl_poller.stop()
        _ghl_poller = None


async def _retry_database_init(settings: Settings, *, attempts: int = 6, delay: float = 2.0) -> None:
    for attempt in range(1, attempts + 1):
        if initialize_database_safe(settings, log=False):
            if attempt > 1:
                logger.info("Database initialization recovered on attempt %d.", attempt)
            return
        logger.warning(
            "Database initialization failed (attempt %d/%d); retrying in %.1fs",
            attempt,
            attempts,
            delay,
        )
        await asyncio.sleep(delay)


app = FastAPI(title="Sagad Agent Studio", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger("agent_studio")
knowledge_ingestion_store = build_knowledge_ingestion_store(get_settings())
knowledge_ingestion_service = KnowledgeIngestionService(
    knowledge_ingestion_store,
    get_settings(),
    runtime_retriever=retriever,
)
tool_manifest_registry = ToolManifestRegistry()
# Share the SAME @lru_cache'd registry instance the graph uses (agent_studio.graph.
# get_agent_registry). The graph reads agent prompts from get_agent_registry(); if this were a
# separate AgentRegistry() instance, POST /agents edits (and .md reloads) would mutate this
# object + disk but never reach the running pipeline until a process restart. Reusing the
# singleton means save_agent/reload_agents (which mutate self.agents in place) are visible to
# the graph on the next node call — edits hot-apply with no restart.
agent_registry = get_agent_registry()

# Populated by the Sprint 2 graph/retrieval workflow when those state fields exist.
_SPRINT2_CONVERSATION_STATE_FIELDS = (
    "selected_agent",
    "customer_driver",
    "retrieval_confidence",
    "missing_knowledge",
    "retrieval_diagnostic",
    "memory_context",
    "memory_diagnostic",
    "eval_tags",
    "trace_attributes",
    "diagnostic_payload",
    "decision_reason",
    "guardrail_findings",
    "confidence_breakdown",
    "final_confidence_score",
    "quality_score",
    "quality_label",
    "quality_signals",
    "quality_notes",
)


def _record_diagnostic_event(
    *,
    event_type: str,
    summary: str,
    status_value: str = "info",
    conversation_id: str | None = None,
    payload: dict[str, object] | None = None,
    context: StoreContext | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> None:
    try:
        sanitized_payload = sanitize_payload(payload or {})
        if not isinstance(sanitized_payload, dict):
            sanitized_payload = {"value": sanitized_payload}
        event = DiagnosticEvent(
            conversation_id=conversation_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            status=status_value,  # type: ignore[arg-type]
            summary=summary,
            payload=sanitized_payload,
        )
        store.record_event(event, context=context)
    except Exception as exc:  # pragma: no cover - diagnostics must not break runtime
        logger.warning(
            "diagnostics.record_failed event_type=%s error=%s",
            event_type,
            exc.__class__.__name__,
        )


def _log_event(
    level: int,
    event_type: str,
    summary: str,
    **fields: object,
) -> None:
    field_text = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.log(level, "%s %s %s", event_type, summary, field_text)


def _trusted_context(
    org_id: str | None = None,
    user_id: str | None = None,
    role: str | None = None,
) -> StoreContext:
    return StoreContext(
        organization_id=org_id,
        user_id=user_id,
        role=role or "system",
    )


def _string_from_mapping(value: dict[str, object] | None, key: str) -> str | None:
    if not value:
        return None
    item = value.get(key)
    if isinstance(item, str):
        return item
    if isinstance(item, int):
        return str(item)
    return None


def _customer_name(payload: ChatwootWebhookPayload) -> str:
    sender_name = _string_from_mapping(payload.sender, "name")
    if sender_name:
        return sender_name
    conversation_meta = payload.conversation or {}
    meta_sender = conversation_meta.get("meta")
    if isinstance(meta_sender, dict):
        contact = meta_sender.get("sender")
        if isinstance(contact, dict):
            name = contact.get("name")
            if isinstance(name, str):
                return name
    return "Chatwoot visitor"


def _conversation_id(payload: ChatwootWebhookPayload) -> str | None:
    conversation = payload.conversation or {}
    value = conversation.get("id")
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _message_id(payload: ChatwootWebhookPayload) -> str | None:
    if isinstance(payload.id, str):
        return payload.id
    if isinstance(payload.id, int):
        return str(payload.id)
    return None


def _safe_id_part(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"_", "-"} else "_"
        for character in value.strip()
    )
    return cleaned or "unknown"


def _sagad_conversation_id(payload: ChatwootWebhookPayload) -> str | None:
    chatwoot_id = _conversation_id(payload)
    if not chatwoot_id:
        return None
    return f"chatwoot_{_safe_id_part(chatwoot_id)}"


def _is_ignored_chatwoot_message(payload: ChatwootWebhookPayload) -> bool:
    message_type = (payload.message_type or "").lower()
    if payload.private is True:
        return True
    return message_type in {"outgoing", "template"}


def _message_already_recorded(
    record: ConversationRecord | None,
    message_id: str | None,
) -> bool:
    if record is None or message_id is None:
        return False
    return any(message.external_message_id == message_id for message in record.messages)


def _verify_webhook_token(token: str | None, context: StoreContext | None = None) -> None:
    settings = configured_settings(get_settings(), context)
    if settings.chatwoot_webhook_token and token != settings.chatwoot_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid Chatwoot webhook token.")


def _verify_internal_secret(token: str | None) -> None:
    settings = get_settings()
    if settings.agent_studio_internal_secret and token != settings.agent_studio_internal_secret:
        raise HTTPException(status_code=401, detail="Invalid Agent Studio internal secret.")


def _require_integration_admin(context: StoreContext) -> None:
    if context.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Integration configuration requires an owner or admin role.",
        )


def _integration_status_from_connection(connection: IntegrationConnection) -> ExternalIntegrationStatus:
    return ExternalIntegrationStatus(
        provider=connection.name,
        kind=connection.kind,
        status=connection.status,
        external=connection.external,
        base_url=connection.base_url,
        mode=connection.api_mode or ("webhook + approved send" if connection.provider == "chatwoot" else None),
        dry_run=connection.dry_run,
        writes_enabled=connection.writes_enabled,
        detail=connection.detail,
    )


def _litellm_status(settings: Settings, detail: str | None = None) -> ExternalIntegrationStatus:
    if not settings.litellm_enabled:
        return ExternalIntegrationStatus(
            provider="LiteLLM Gateway",
            kind="tool_layer",
            status="disabled",
            external=False,
            base_url=settings.litellm_base_url,
            mode="OpenAI-compatible /v1 model gateway",
            dry_run=True,
            writes_enabled=False,
            detail="LiteLLM is optional and disabled. Enable it to route OpenAI and DeepSeek test traffic through one gateway.",
        )

    if not settings.litellm_base_url:
        return ExternalIntegrationStatus(
            provider="LiteLLM Gateway",
            kind="tool_layer",
            status="unconfigured",
            external=False,
            mode="OpenAI-compatible /v1 model gateway",
            dry_run=True,
            writes_enabled=False,
            detail="Set LITELLM_BASE_URL before enabling the LiteLLM gateway.",
        )

    return ExternalIntegrationStatus(
        provider="LiteLLM Gateway",
        kind="tool_layer",
        status="ready" if detail is None else "error",
        external=False,
        base_url=settings.litellm_base_url,
        mode="OpenAI-compatible /v1 model gateway",
        dry_run=False,
        writes_enabled=False,
        detail=detail
        or "LiteLLM is enabled for Agent Studio model calls through an OpenAI-compatible gateway.",
    )


async def _probe_litellm(settings: Settings) -> ExternalIntegrationStatus:
    status_payload = _litellm_status(settings)
    if status_payload.status in {"disabled", "unconfigured"}:
        return status_payload

    health_base_url = settings.litellm_health_base_url
    if not health_base_url:
        return _litellm_status(settings, "LiteLLM base URL could not be normalized for health checks.")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{health_base_url}/health/readiness")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return _litellm_status(settings, f"LiteLLM readiness check failed: {exc.__class__.__name__}.")

    return status_payload


def _integration_statuses(context: StoreContext | None = None) -> list[ExternalIntegrationStatus]:
    settings = configured_settings(get_settings(), context)
    chatwoot_status = "ready" if settings.chatwoot_send_enabled else "dry_run"
    langsmith_ready = bool(settings.langsmith_api_key and settings.langsmith_tracing)
    configured_connections = {
        connection.provider: connection for connection in integration_config_store.list(context=context)
    }
    chatwoot_connection = configured_connections.get("chatwoot")
    twenty_connection = configured_connections.get("twenty")
    return [
        _integration_status_from_connection(chatwoot_connection)
        if chatwoot_connection and chatwoot_connection.configured
        else ExternalIntegrationStatus(
            provider="Chatwoot",
            kind="channel",
            status=chatwoot_status,
            external=True,
            base_url=settings.chatwoot_base_url,
            mode="webhook + approved send",
            dry_run=not settings.chatwoot_send_enabled,
            writes_enabled=settings.chatwoot_send_enabled,
            detail=(
                "Chatwoot approved-send is configured."
                if settings.chatwoot_send_enabled
                else "Chatwoot inbound works locally; outbound send is dry-run until credentials are set."
            ),
        ),
        (
            _integration_status_from_connection(twenty_connection)
            if twenty_connection and twenty_connection.configured
            else twenty_status(settings)
        ),
        ExternalIntegrationStatus(
            provider="Markdown Knowledge Packs",
            kind="knowledge",
            status="ready",
            external=False,
            mode="local markdown",
            dry_run=False,
            writes_enabled=False,
            detail="Home services KB/SOP/QA/compliance records are loaded in memory.",
        ),
        ExternalIntegrationStatus(
            provider="LangSmith",
            kind="observability",
            status="ready" if langsmith_ready else "planned",
            external=True,
            mode="environment telemetry",
            dry_run=not langsmith_ready,
            writes_enabled=False,
            detail="Trace links are attached when LangSmith environment variables are configured.",
        ),
        _litellm_status(settings),
        ExternalIntegrationStatus(
            provider="Generic Webhooks",
            kind="webhook",
            status="planned",
            external=True,
            mode="inbound + outbound webhooks",
            dry_run=True,
            writes_enabled=False,
            detail="Provider-neutral webhooks can connect external apps after Agent Studio policy gates are defined.",
        ),
        ExternalIntegrationStatus(
            provider="MCP Adapter Layer",
            kind="tool_layer",
            status="planned",
            external=False,
            mode="server-side tools",
            dry_run=True,
            writes_enabled=False,
            detail="Future MCP tools will sit behind Agent Studio policy and audit gates.",
        ),
    ]


def _chatwoot_tool_payload(result: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"provider", "action", "status", "detail"}
        and value is not None
    }


def _policy_agent_name(record: ConversationRecord | None = None) -> str:
    if record and record.selected_agent:
        return record.selected_agent
    return "general_support"


def _policy_agent_from_tool_request(
    *,
    context: StoreContext,
    conversation_id: str | None,
    selected_agent: str | None,
) -> str:
    if conversation_id:
        record = store.get(conversation_id, context=context)
        if record and record.selected_agent and record.selected_agent.strip():
            return record.selected_agent.strip()
    if selected_agent and selected_agent.strip():
        return selected_agent.strip()
    return "general_support"


def _policy_metadata(
    *,
    decision: ToolPolicyDecision,
    approved: bool,
    supervisor_id: str | None,
    risk_level: str,
) -> dict[str, object]:
    return {
        "approval_gate": "supervisor_approval" if decision.requires_approval else "none",
        "requires_approval": decision.requires_approval,
        "approved": approved,
        "supervisor_id": supervisor_id,
        "risk_level": risk_level,
        "allowed": decision.allowed,
        "dry_run": decision.dry_run,
        "blocked_reason": decision.blocked_reason,
        "policy_reasons": list(decision.policy_reasons),
    }


def _attach_policy_metadata(
    plan: ToolPlan,
    result: ToolResult,
    *,
    decision: ToolPolicyDecision,
    approved: bool,
    supervisor_id: str | None,
    risk_level: str,
) -> tuple[ToolPlan, ToolResult]:
    metadata = _policy_metadata(
        decision=decision,
        approved=approved,
        supervisor_id=supervisor_id,
        risk_level=risk_level,
    )
    decision_payload = decision.model_dump(mode="json")
    plan.requires_approval = decision.requires_approval
    plan.approved = approved
    plan.dry_run = decision.dry_run
    plan.args = {
        **plan.args,
        "policy_metadata": metadata,
        "policy_decision": decision_payload,
    }
    result.data = {
        **result.data,
        "policy_metadata": metadata,
        "policy_decision": decision_payload,
    }
    return plan, result


def _blocked_policy_tool_result(
    *,
    tool_name: str,
    action: str,
    args: dict[str, object],
    decision: ToolPolicyDecision,
    approved: bool,
    supervisor_id: str | None,
    risk_level: str,
) -> tuple[ToolPlan, ToolResult]:
    manifest = tool_manifest_registry.get_manifest(tool_name)
    plan = ToolPlan(
        provider=manifest.provider,
        tool_name=tool_name,
        action=action,
        risk_level=risk_level,  # type: ignore[arg-type]
        requires_approval=decision.requires_approval,
        approved=approved,
        dry_run=True,
        args=args,
    )
    result = ToolResult(
        plan_id=plan.id,
        provider=manifest.provider,
        tool_name=tool_name,
        status="blocked",
        detail=decision.blocked_reason or "Tool blocked by Agent Studio policy.",
        data={},
    )
    return _attach_policy_metadata(
        plan,
        result,
        decision=decision,
        approved=approved,
        supervisor_id=supervisor_id,
        risk_level=risk_level,
    )


def _chatwoot_policy_context(
    settings: Settings,
    record: ConversationRecord,
    *,
    approved: bool,
    risk_level: str | None = None,
) -> ToolPolicyContext:
    return ToolPolicyContext(
        selected_agent=_policy_agent_name(record),
        conversation_risk=(risk_level or record.risk_level),  # type: ignore[arg-type]
        approved=approved,
        autonomous=False,
        provider_enabled=True,
        provider_configured=settings.chatwoot_configured,
        provider_dry_run=settings.chatwoot_dry_run,
        provider_writes_enabled=settings.chatwoot_send_enabled,
    )


def _twenty_policy_context(
    settings: Settings,
    *,
    selected_agent: str,
    approved: bool,
    risk_level: str = "medium",
) -> ToolPolicyContext:
    return ToolPolicyContext(
        selected_agent=selected_agent,
        conversation_risk=risk_level,  # type: ignore[arg-type]
        approved=approved,
        autonomous=False,
        provider_enabled=settings.twenty_enabled,
        provider_configured=settings.twenty_configured,
        provider_dry_run=settings.twenty_dry_run,
        provider_writes_enabled=settings.twenty_allow_writes,
    )


def _chatwoot_send_tool_result(
    record: ConversationRecord,
    result: dict[str, object],
    *,
    content: str,
) -> tuple[ToolPlan, ToolResult]:
    status_value = str(result.get("status", "failed"))
    tool_status = {
        "sent": "succeeded",
        "dry_run": "dry_run",
        "failed": "failed",
    }.get(status_value, "failed")
    plan = ToolPlan(
        provider="Chatwoot",
        tool_name="chatwoot.messages.send_approved",
        action="send supervisor-approved reply",
        risk_level=record.risk_level,
        requires_approval=True,
        approved=True,
        dry_run=status_value == "dry_run",
        args={
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "content_preview": content[:160],
        },
    )
    return (
        plan,
        ToolResult(
            plan_id=plan.id,
            provider="Chatwoot",
            tool_name="chatwoot.messages.send_approved",
            status=tool_status,  # type: ignore[arg-type]
            detail=str(result.get("detail", "Chatwoot send completed.")),
            external_id=str(result["external_id"]) if result.get("external_id") else None,
            data=_chatwoot_tool_payload(result),
        ),
    )


def _ghl_policy_context(
    settings: Settings,
    record: ConversationRecord,
    *,
    approved: bool,
    risk_level: str | None = None,
) -> ToolPolicyContext:
    return ToolPolicyContext(
        selected_agent=_policy_agent_name(record),
        conversation_risk=(risk_level or record.risk_level),  # type: ignore[arg-type]
        approved=approved,
        autonomous=False,
        provider_enabled=True,
        provider_configured=settings.ghl_configured,
        provider_dry_run=settings.ghl_dry_run,
        provider_writes_enabled=settings.ghl_send_enabled,
    )


def _ghl_tool_payload(result: dict[str, object]) -> dict[str, object]:
    # Same redaction as the Chatwoot payload: drop echoed provider/action/status/detail.
    return {
        key: value
        for key, value in result.items()
        if key not in {"provider", "action", "status", "detail"}
        and value is not None
    }


def _ghl_send_tool_result(
    record: ConversationRecord,
    result: dict[str, object],
    *,
    content: str,
) -> tuple[ToolPlan, ToolResult]:
    status_value = str(result.get("status", "failed"))
    tool_status = {
        "sent": "succeeded",
        "dry_run": "dry_run",
        "failed": "failed",
    }.get(status_value, "failed")
    plan = ToolPlan(
        provider="GHL",
        tool_name="ghl.messages.send_approved",
        action="send supervisor-approved reply",
        risk_level=record.risk_level,
        requires_approval=True,
        approved=True,
        dry_run=status_value == "dry_run",
        args={
            "provider_conversation_id": record.provider_conversation_id,
            "content_preview": content[:160],
        },
    )
    return (
        plan,
        ToolResult(
            plan_id=plan.id,
            provider="GHL",
            tool_name="ghl.messages.send_approved",
            status=tool_status,  # type: ignore[arg-type]
            detail=str(result.get("detail", "GHL send completed.")),
            external_id=str(result["external_id"]) if result.get("external_id") else None,
            data=_ghl_tool_payload(result),
        ),
    )


def _chatwoot_resolve_tool_result(
    record: ConversationRecord,
    result: dict[str, object],
) -> tuple[ToolPlan, ToolResult]:
    status_value = str(result.get("status", "failed"))
    tool_status = {
        "resolved": "succeeded",
        "dry_run": "dry_run",
        "failed": "failed",
    }.get(status_value, "failed")
    plan = ToolPlan(
        provider="Chatwoot",
        tool_name="chatwoot.conversations.resolve",
        action="resolve conversation",
        risk_level="medium",
        requires_approval=True,
        approved=True,
        dry_run=status_value == "dry_run",
        args={
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "source_id": record.chatwoot_context.source_id
            if record.chatwoot_context
            else None,
        },
    )
    return (
        plan,
        ToolResult(
            plan_id=plan.id,
            provider="Chatwoot",
            tool_name="chatwoot.conversations.resolve",
            status=tool_status,  # type: ignore[arg-type]
            detail=str(result.get("detail", "Chatwoot resolve completed.")),
            external_id=str(result["external_id"]) if result.get("external_id") else None,
            data=_chatwoot_tool_payload(result),
        ),
    )


def _attach_memory_context(
    record: ConversationRecord,
    *,
    context: StoreContext | None,
) -> ConversationRecord:
    memory_context = store.list_memory_items(
        record.id,
        query=record.incoming_message,
        context=context,
    )
    record.memory_context = memory_context
    record.memory_diagnostic = {
        **(record.memory_diagnostic or {}),
        "persisted_memory_count": len(memory_context),
        "memory_available": bool(memory_context),
    }
    return record


def _with_sla_status(record: ConversationRecord) -> ConversationRecord:
    """Surface runtime SLA health (on_track/warning/overdue) derived from `sla_due_at` vs now.

    `sla_status` is a transient field (not persisted); recompute it on every read so the queue
    and GET /conversations/{id} reflect the current deadline. No deadline -> "none".
    """
    record.sla_status = compute_sla_status(
        record.sla_due_at,
        priority=record.priority,
        created_at=record.created_at,
    )
    return record


def _append_lifecycle_memory(
    record: ConversationRecord,
    *,
    lifecycle_event: str,
    context: StoreContext | None,
) -> ConversationRecord:
    store.append_memory_items(
        record.id,
        memory_items_from_record(record, lifecycle_event=lifecycle_event),
        context=context,
    )
    return _attach_memory_context(record, context=context)


def _require_supervisor_approval(approved: bool) -> None:
    if not approved:
        raise HTTPException(
            status_code=403,
            detail="CRM write requires an explicit supervisor approval payload.",
        )


def _realtime_event(
    event_type: str,
    record: ConversationRecord,
    *,
    organization_id: str | None,
) -> dict[str, object]:
    return {
        "type": event_type,
        "conversation_id": record.id,
        "chatwoot_conversation_id": record.chatwoot_conversation_id,
        "organization_id": organization_id,
        "approval_status": record.approval_status,
        "send_status": record.send_status,
        "updated_at": record.updated_at.isoformat(),
    }


def _count_status(
    counts: dict[str, object],
    *names: str,
) -> int:
    total = 0
    for name in names:
        value = counts.get(name)
        if value is None:
            value = counts.get(name.lower())
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return total


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _eval_result_payload(result: object, cases_by_id: dict[str, object]) -> dict[str, object]:
    result_payload = result.model_dump(mode="json")
    case = cases_by_id.get(str(result_payload.get("case_id")))
    case_payload = case.model_dump(mode="json") if hasattr(case, "model_dump") else {}
    return {
        "id": f"evalresult_{result_payload['case_id']}",
        "eval_run_id": result_payload.get("run_id"),
        "case_id": result_payload["case_id"],
        "case_name": result_payload["name"],
        "status": "passed" if result_payload["passed"] else "failed",
        "score": result_payload["score"],
        "input": {
            "message": case_payload.get("incoming_message"),
            "description": case_payload.get("description"),
        },
        "expected": case_payload.get("expectation", {}),
        "actual": {
            "passed": result_payload["passed"],
            "scores": result_payload["scores"],
        },
        "metrics": {
            "scores": result_payload["scores"],
            "dimensions": [
                score["dimension"]
                for score in result_payload["scores"]
                if isinstance(score, dict)
            ],
        },
        "failure_reason": "; ".join(
            score["detail"]
            for score in result_payload["scores"]
            if isinstance(score, dict) and not score.get("passed")
        )
        or None,
    }


def _persist_eval_summary(
    *,
    context: StoreContext,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    run_id = f"evalrun_{uuid4().hex[:12]}"
    summary = run_fixture_evals(run_id=run_id)
    cases_by_id = {case.id: case for case in built_in_eval_cases()}
    now = datetime.now(timezone.utc)
    run_record = store.record_eval_run(
        {
            "id": summary.run_id,
            "name": "Sprint 4 built-in quality evals",
            "suite_name": "ai_ops_quality",
            "status": "completed" if summary.passed else "failed",
            "started_at": now,
            "completed_at": now,
            "total_cases": summary.case_count,
            "passed_cases": summary.passed_case_count,
            "failed_cases": summary.failed_case_count,
            "average_score": summary.overall_score,
            "metadata": {
                "dimension_scores": summary.dimension_scores,
                "threshold_checks": [
                    check.model_dump(mode="json")
                    for check in summary.threshold_checks
                ],
                "failed_case_ids": summary.failed_case_ids,
                "source": "builtin_fixture",
            },
        },
        context=context,
    )
    result_records = [
        store.record_eval_result(
            {
                **_eval_result_payload(result, cases_by_id),
                "id": f"{summary.run_id}_{result.case_id}",
                "eval_run_id": summary.run_id,
            },
            context=context,
        )
        for result in summary.results
    ]
    return run_record, result_records, summary.model_dump(mode="json")


def _scorecard_conversation_row(
    record: ConversationRecord,
    index: int,
) -> dict[str, object]:
    final_score = getattr(record, "final_confidence_score", None)
    if final_score is None:
        final_score = getattr(record, "retrieval_confidence", None)
    return {
        "id": record.id,
        "conversation_id": record.id,
        "customer_name": record.customer_name or f"Conversation {index + 1}",
        "driver": getattr(record, "customer_driver", None) or record.intent,
        "intent": record.intent,
        "risk_level": record.risk_level,
        "approval_status": record.approval_status,
        "hitl_status": record.approval_status,
        "queue_status": record.approval_status,
        "send_status": record.send_status,
        "confidence": final_score,
        "final_confidence_score": final_score,
        "quality_label": getattr(record, "quality_label", None),
        "decision_reason": getattr(record, "decision_reason", None),
        "missing_knowledge": getattr(record, "missing_knowledge", False),
        "selected_agent": getattr(record, "selected_agent", None),
        "updated_at": record.updated_at.isoformat(),
    }


def _scorecard_payload(
    *,
    context: StoreContext,
) -> dict[str, object]:
    conversations = store.list(context=context)
    events = store.list_events(limit=200, context=context)
    raw_metrics = aggregate_ai_ops_metrics(conversations, events)
    approval_counts = raw_metrics.get("approval_status_counts", {})
    send_counts = raw_metrics.get("send_status_counts", {})
    risk_counts = raw_metrics.get("risk_level_counts", {})
    tool_counts = raw_metrics.get("tool_result_status_counts", {})
    provider_counts = raw_metrics.get("provider_error_category_counts", {})
    total = int(raw_metrics.get("conversation_count") or 0)
    needs_approval = _count_status(approval_counts, "needs_approval")
    approved = _count_status(approval_counts, "sent", "approved")
    rejected = _count_status(approval_counts, "rejected")
    sent = _count_status(send_counts, "sent")
    failed_sends = _count_status(send_counts, "send_failed", "failed")
    blocked_tools = _count_status(tool_counts, "blocked")
    dry_runs = _count_status(tool_counts, "dry_run")
    tool_failures = _count_status(tool_counts, "failed")
    high_risk = _count_status(risk_counts, "high")
    provider_failures = int(raw_metrics.get("error_event_count") or 0)
    guardrail_findings = sum(
        len(getattr(record, "guardrail_findings", []) or [])
        for record in conversations
    )
    missing_knowledge = int(raw_metrics.get("missing_knowledge_count") or 0)
    average_retrieval = raw_metrics.get("avg_retrieval_confidence")
    provider_failure_categories = [
        {"category": str(category), "count": int(count)}
        for category, count in dict(provider_counts).items()
    ]
    metrics = {
        **raw_metrics,
        "messagesReceived": total,
        "messages_received": total,
        "totalConversations": total,
        "total_conversations": total,
        "aiDraftedResponses": int(raw_metrics.get("drafted_count") or 0),
        "ai_drafted_responses": int(raw_metrics.get("drafted_count") or 0),
        "approvalRequired": needs_approval,
        "approval_required": needs_approval,
        "approvalRequiredCount": needs_approval,
        "approval_required_count": needs_approval,
        "approved": approved,
        "rejected": rejected,
        "autoSentResponses": sent,
        "auto_sent_responses": sent,
        "autoSent": sent,
        "auto_sent": sent,
        "averageConfidence": average_retrieval,
        "average_confidence": average_retrieval,
        "averageRetrievalConfidence": average_retrieval,
        "average_retrieval_confidence": average_retrieval,
        "retrievalMissingKnowledgeRate": _rate(missing_knowledge, total),
        "retrieval_missing_knowledge_rate": _rate(missing_knowledge, total),
        "approvalRequiredRate": _rate(needs_approval, total),
        "approval_required_rate": _rate(needs_approval, total),
        "actualAutoSendRate": _rate(sent, total),
        "actual_auto_send_rate": _rate(sent, total),
        "highRiskCaseCount": high_risk,
        "high_risk_case_count": high_risk,
        "toolCallsPlanned": int(raw_metrics.get("tool_plan_count") or 0),
        "tool_calls_planned": int(raw_metrics.get("tool_plan_count") or 0),
        "toolCallsBlocked": blocked_tools,
        "tool_calls_blocked": blocked_tools,
        "blockedTools": blocked_tools,
        "blocked_tools": blocked_tools,
        "toolDryRuns": dry_runs,
        "tool_dry_runs": dry_runs,
        "dryRuns": dry_runs,
        "dry_runs": dry_runs,
        "toolFailures": tool_failures,
        "tool_failures": tool_failures,
        "sendFailures": failed_sends,
        "send_failures": failed_sends,
        "providerFailures": provider_failures,
        "provider_failures": provider_failures,
        "providerFailureCount": provider_failures,
        "provider_failure_count": provider_failures,
        "providerFailureCategories": [
            row["category"]
            for row in provider_failure_categories
        ],
        "provider_failure_categories": [
            row["category"]
            for row in provider_failure_categories
        ],
        "guardrailFindings": guardrail_findings,
        "guardrail_findings": guardrail_findings,
        "topMissingKnowledgeTopics": [
            record.intent
            for record in conversations
            if getattr(record, "missing_knowledge", False)
        ][:5],
        "top_missing_knowledge_topics": [
            record.intent
            for record in conversations
            if getattr(record, "missing_knowledge", False)
        ][:5],
        "topIssue": "Missing knowledge"
        if missing_knowledge
        else "No missing knowledge trend detected",
        "top_issue": "Missing knowledge"
        if missing_knowledge
        else "No missing knowledge trend detected",
        "recommendedAction": "Review missing-knowledge cases and blocked provider actions."
        if missing_knowledge or blocked_tools or provider_failures
        else "Keep monitoring approval and QA signals.",
        "recommended_action": "Review missing-knowledge cases and blocked provider actions."
        if missing_knowledge or blocked_tools or provider_failures
        else "Keep monitoring approval and QA signals.",
    }
    attention_summary = [
        {
            "id": "missing-knowledge",
            "type": "Missing knowledge",
            "category": "Retrieval",
            "reason": "Cases where the source pack was weak or absent.",
            "count": missing_knowledge,
            "owner": "Knowledge",
            "severity": "Review",
            "status": "Review",
        },
        {
            "id": "blocked-tools",
            "type": "Tool policy blocked",
            "category": "Policy",
            "reason": "Tool attempts blocked by capability policy.",
            "count": blocked_tools,
            "owner": "Agent Studio",
            "severity": "High risk",
            "status": "High risk",
        },
        {
            "id": "provider-failures",
            "type": "Provider failures",
            "category": "Delivery",
            "reason": "Provider or integration failures recorded in diagnostics.",
            "count": provider_failures,
            "owner": "Platform",
            "severity": "High risk",
            "status": "High risk",
        },
        {
            "id": "guardrail-findings",
            "type": "Guardrail findings",
            "category": "Quality",
            "reason": "QA findings surfaced during graph review.",
            "count": guardrail_findings,
            "owner": "AI Ops",
            "severity": "Review",
            "status": "Review",
        },
    ]
    scorecard = {
        "source": "agent-studio",
        "status": "connected",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "attentionSummary": [
            row
            for row in attention_summary
            if int(row["count"]) > 0
        ],
        "attention_summary": [
            row
            for row in attention_summary
            if int(row["count"]) > 0
        ],
        "providerFailureCategories": provider_failure_categories,
        "provider_failure_categories": provider_failure_categories,
        "conversations": [
            _scorecard_conversation_row(record, index)
            for index, record in enumerate(conversations[:20])
        ],
    }
    return {"scorecard": scorecard, **scorecard}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service="agent-studio",
        knowledge_records=len(retriever.records),
        chatwoot_send_enabled=settings.chatwoot_send_enabled,
        twenty_status=twenty_status(settings),
    )


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive", "service": "agent-studio"}


@app.get("/health/ready")
def health_ready() -> dict[str, object]:
    settings = get_settings()
    db_ready, database_detail = database_ready(settings)

    if not db_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "service": "agent-studio",
                "database_ready": False,
                "database_detail": database_detail,
                "knowledge_records": len(retriever.records),
            },
        )

    return {
        "status": "ready" if db_ready else "not_ready",
        "service": "agent-studio",
        "database_ready": db_ready,
        "database_detail": database_detail,
        "knowledge_records": len(retriever.records),
    }


@app.get("/agents")
def get_agents():
    return [agent.model_dump() for agent in agent_registry.get_all_agents()]


class AgentSavePayload(BaseModel):
    id: str
    name: str
    intents: list[str]
    allowed_tools: list[str]
    system_prompt: str
    original_id: str | None = None
    # Optional, UI-editable metadata. Default "" so older clients keep working and
    # existing agent files stay minimal when these are unset.
    description: str = ""
    model: str = ""
    tier: str = ""
    voice: str = ""


@app.post("/agents")
def save_agent(
    payload: AgentSavePayload,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> list[dict[str, object]]:
    _verify_internal_secret(x_sagad_internal_secret)
    agent_registry.save_agent(
        agent_id=payload.id,
        name=payload.name,
        intents=payload.intents,
        allowed_tools=payload.allowed_tools,
        system_prompt=payload.system_prompt,
        original_id=payload.original_id,
        description=payload.description,
        model=payload.model,
        tier=payload.tier,
        voice=payload.voice,
    )
    return [agent.model_dump() for agent in agent_registry.get_all_agents()]


@app.delete("/agents/{agent_id}")
def delete_agent(
    agent_id: str,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    deleted = agent_registry.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return {"deleted": agent_id, "agents": [agent.model_dump() for agent in agent_registry.get_all_agents()]}


@app.post("/agents/reload")
def reload_agents(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Hot-reload agent definitions from disk without a process restart.

    ``POST /agents`` already reloads the shared registry in place after a save; this endpoint
    covers the case where an agent ``.md`` was edited directly on disk (e.g. via git or an
    editor). Because ``agent_registry`` is the same ``@lru_cache``'d singleton the graph reads
    from, ``reload_agents()`` (which mutates ``self.agents`` in place) makes the new prompts
    visible to the running pipeline immediately.
    """
    _verify_internal_secret(x_sagad_internal_secret)
    agent_registry.reload_agents()
    return {"reloaded": True, "agents": [agent.model_dump() for agent in agent_registry.get_all_agents()]}


@app.get("/conversations/{conversation_id}/draft/stream")
async def stream_draft(
    conversation_id: str,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    record = store.get(conversation_id, context=context)
    if not record:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    incoming = record.normalized_message or record.incoming_message or ""

    # Run the SAME pipeline the webhook runs (graph.ainvoke) so streaming and the drafted reply
    # share one customizable chain: normalize -> retrieve -> classify -> sub-agent -> supervisor
    # -> guardrail. Editing any agent .md (followed by POST /agents or POST /agents/reload) is
    # reflected here identically — there is no longer a divergent stream-only prompt path.
    initial_state: dict[str, object] = {
        "conversation_id": conversation_id,
        "chatwoot_conversation_id": getattr(record, "chatwoot_conversation_id", None),
        "chatwoot_message_id": getattr(record, "chatwoot_message_id", None),
        "customer_name": record.customer_name,
        "channel": record.channel,
        "incoming_message": incoming,
        "conversation_history": record.messages,
        "memory_context": store.list_memory_items(conversation_id, query=incoming, context=context)
        if conversation_id
        else [],
        "trace_url": None,
    }

    async def generate():
        try:
            final_state = await graph.ainvoke(initial_state)
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"
            return

        draft = str(final_state.get("draft_reply", "") or "")
        # Stream the finalized draft as SSE tokens (word-chunked, matching DryRun astream format).
        for token in draft.split():
            yield f"data: {token} \n\n"

        # Persist the graph-produced draft + QA state back onto the record.
        record.draft_reply = draft
        qa_findings = final_state.get("qa_findings")
        if qa_findings is not None:
            record.qa_findings = qa_findings
        compliance_status = final_state.get("compliance_status")
        if compliance_status:
            record.compliance_status = compliance_status
        record.approval_status = "needs_approval"
        store.save(record, context=context)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/skills")
def skills(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, list[dict[str, object]]]:
    _verify_internal_secret(x_sagad_internal_secret)
    return {
        "skills": [
            skill.model_dump(mode="json")
            for skill in list_skill_definitions()
        ],
    }


@app.get("/tools/manifests")
def tool_manifests(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, list[dict[str, object]]]:
    _verify_internal_secret(x_sagad_internal_secret)
    manifests = [
        manifest.model_dump(mode="json")
        for manifest in tool_manifest_registry.list_manifests()
    ]
    return {
        "tools": manifests,
        "manifests": manifests,
    }


@app.get("/mcp/descriptors")
def mcp_descriptors(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, list[dict[str, object]]]:
    _verify_internal_secret(x_sagad_internal_secret)
    descriptors: list[dict[str, object]] = []
    for descriptor in build_mcp_descriptors(tool_manifest_registry.list_manifests()):
        payload = descriptor.model_dump(mode="json")
        payload["policy_wrapped"] = descriptor.policy_wrapped
        descriptors.append(payload)
    return {"descriptors": descriptors}


@app.get("/integrations", response_model=IntegrationListResponse)
def list_integrations(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> IntegrationListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return IntegrationListResponse(integrations=_integration_statuses(context))


@app.get("/integrations/twenty/health", response_model=CrmProviderStatus)
def get_twenty_health(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> CrmProviderStatus:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return twenty_status(configured_settings(get_settings(), context))


@app.get("/integrations/litellm/health", response_model=ExternalIntegrationStatus)
async def get_litellm_health(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> ExternalIntegrationStatus:
    _verify_internal_secret(x_sagad_internal_secret)
    return await _probe_litellm(get_settings())


@app.get("/integration-configs", response_model=IntegrationConnectionListResponse)
def list_integration_configs(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> IntegrationConnectionListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return IntegrationConnectionListResponse(
        connections=integration_connections_for_display(get_settings(), context=context),
    )


@app.get("/diagnostics/events", response_model=DiagnosticEventListResponse)
def list_diagnostic_events(
    conversation_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> DiagnosticEventListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return DiagnosticEventListResponse(
        events=store.list_events(
            conversation_id=conversation_id,
            limit=limit,
            context=context,
        ),
    )


@app.get("/evals/cases")
def list_eval_cases(
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    cases = [case.model_dump(mode="json") for case in built_in_eval_cases()]
    return {"cases": cases, "eval_cases": cases, "items": cases}


@app.post("/evals/run")
def run_evals(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    run_record, result_records, summary = _persist_eval_summary(context=context)
    _record_diagnostic_event(
        event_type="eval.run.completed",
        summary="Sprint 4 built-in quality evals completed.",
        status_value="success" if summary.get("passed") else "warning",
        payload={
            "run_id": run_record["id"],
            "case_count": summary["case_count"],
            "passed_case_count": summary["passed_case_count"],
            "failed_case_count": summary["failed_case_count"],
            "overall_score": summary["overall_score"],
        },
        context=context,
        actor_type="user" if x_sagad_user_id else "system",
        actor_id=x_sagad_user_id,
    )
    return {
        "run": run_record,
        "runs": [run_record],
        "results": result_records,
        "summary": summary,
    }


@app.get("/evals/runs")
def list_eval_runs(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    runs = store.list_eval_runs(limit=limit, context=context)
    enriched_runs = [
        {
            **run,
            "results": store.list_eval_results(
                str(run["id"]),
                limit=200,
                context=context,
            ),
        }
        for run in runs
    ]
    return {"runs": enriched_runs, "eval_runs": enriched_runs, "items": enriched_runs}


@app.get("/ai-ops/scorecard")
def ai_ops_scorecard(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return _scorecard_payload(context=context)


@app.put("/integration-configs/{provider}", response_model=IntegrationConnection)
def upsert_integration_config(
    provider: IntegrationProvider,
    request: IntegrationConnectionUpsertRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> IntegrationConnection:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    return integration_config_store.upsert(provider, request, context=context)


@app.post("/integration-configs/{provider}/disable", response_model=IntegrationConnection)
def disable_integration_config(
    provider: IntegrationProvider,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> IntegrationConnection:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    return integration_config_store.disable(provider, context=context)


@app.post("/integration-configs/{provider}/test", response_model=IntegrationConnectionTestResponse)
def test_integration_config(
    provider: IntegrationProvider,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> IntegrationConnectionTestResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    status_value, detail, connection = connection_test_result(provider, context=context)
    return IntegrationConnectionTestResponse(
        provider=provider,
        status=status_value,
        detail=detail,
        connection=connection,
    )


def _test_chat_provider(settings: Settings) -> dict[str, object]:
    cfg = resolve_chat_config(settings)
    if not cfg.configured:
        return {"ok": False, "detail": cfg.detail or "No chat provider configured.", "model": cfg.model}
    try:
        import litellm

        kwargs: dict[str, object] = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        if cfg.api_base:
            kwargs["api_base"] = cfg.api_base
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        litellm.completion(**kwargs)
        return {"ok": True, "detail": f"Chat reachable via {cfg.provider}.", "model": cfg.model}
    except Exception as exc:  # noqa: BLE001 - test endpoint must report, never raise
        return {
            "ok": False,
            "detail": f"Chat test failed: {exc.__class__.__name__}: {exc}",
            "model": cfg.model,
        }


def _test_embedding_provider(settings: Settings) -> dict[str, object]:
    cfg = resolve_embedding_config(settings)
    if not cfg.configured:
        return {"ok": False, "detail": cfg.detail or "No embedding provider configured.", "model": cfg.model}
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                f"{cfg.base_url}/embeddings",
                headers=headers,
                json={"model": cfg.model, "input": "test", "encoding_format": "float"},
            )
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        ok = isinstance(data, list) and bool(data) and isinstance(data[0].get("embedding"), list)
        return {
            "ok": bool(ok),
            "detail": "Embedding endpoint reachable." if ok else "Embedding response missing vector.",
            "model": cfg.model,
        }
    except Exception as exc:  # noqa: BLE001 - test endpoint must report, never raise
        return {
            "ok": False,
            "detail": f"Embedding test failed: {exc.__class__.__name__}",
            "model": cfg.model,
        }


@app.get("/model-providers")
def list_model_providers(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    settings = configured_settings(get_settings(), context)
    chat_cfg = resolve_chat_config(settings)
    embed_cfg = resolve_embedding_config(settings)
    record = model_provider_config_store.get(context=context)
    return {
        "active": settings.model_provider or "none",
        "embedding_active": embed_cfg.provider,
        "chat_model": chat_cfg.model,
        "embedding_model": embed_cfg.model if embed_cfg.configured else None,
        "embedding_dimensions": embed_cfg.dimensions,
        "providers": [asdict(status) for status in provider_status(settings)],
        "config": model_provider_config_view(record, settings),
    }


@app.put("/model-providers")
def update_model_providers(
    request: ModelProviderConfigUpsertRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    record = model_provider_config_store.upsert(request, context=context)
    settings = configured_settings(get_settings(), context)
    return {
        "active": settings.model_provider or "none",
        "config": model_provider_config_view(record, settings),
    }


@app.post("/model-providers/test")
def test_model_providers(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_integration_admin(context)
    settings = configured_settings(get_settings(), context)
    return {
        "chat": _test_chat_provider(settings),
        "embedding": _test_embedding_provider(settings),
    }


@app.post("/knowledge/ingestion-jobs", response_model=KnowledgeIngestionJobResponse)
def create_knowledge_ingestion_job(
    request: KnowledgeIngestionJobCreateRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeIngestionJobResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    if not request.files:
        raise HTTPException(status_code=400, detail="At least one file is required for ingestion.")
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    response = knowledge_ingestion_service.ingest(request, context=context)
    _record_diagnostic_event(
        event_type="knowledge.ingestion.completed",
        summary=response.job.summary,
        status_value="warning" if response.errors else "success",
        context=context,
        payload={
            "job_id": response.job.id,
            "source_name": response.job.source_name,
            "processed_files": response.job.processed_files,
            "failed_files": response.job.failed_files,
        },
    )
    return response


@app.get("/knowledge/ingestion-jobs", response_model=KnowledgeIngestionJobListResponse)
def list_knowledge_ingestion_jobs(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeIngestionJobListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return KnowledgeIngestionJobListResponse(
        jobs=knowledge_ingestion_store.list_jobs(context=context),
    )


@app.get("/knowledge/sources", response_model=KnowledgeSourceListResponse)
def list_knowledge_sources(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeSourceListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return KnowledgeSourceListResponse(
        sources=knowledge_ingestion_service.list_sources(context=context),
    )


@app.post("/knowledge/sources/{source_id}/sync", response_model=KnowledgeIngestionJobResponse)
def sync_knowledge_source(
    source_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeIngestionJobResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    try:
        response = knowledge_ingestion_service.sync_source(source_id, context=context)
    except RuntimeError as exc:
        _record_diagnostic_event(
            event_type="knowledge.source.sync_failed",
            summary=str(exc),
            status_value="error",
            context=context,
            payload={"source_id": source_id},
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    _record_diagnostic_event(
        event_type="knowledge.source.synced",
        summary=response.job.summary,
        status_value="warning" if response.errors else "success",
        context=context,
        payload={
            "source_id": source_id,
            "job_id": response.job.id,
            "processed_files": response.job.processed_files,
            "failed_files": response.job.failed_files,
        },
    )
    return response


@app.get("/knowledge/documents", response_model=KnowledgeDocumentListResponse)
def list_knowledge_documents(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeDocumentListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return KnowledgeDocumentListResponse(
        documents=knowledge_ingestion_store.list_documents(context=context),
    )


@app.get("/knowledge/documents/{document_id}", response_model=KnowledgeDocumentRecord)
def get_knowledge_document(
    document_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeDocumentRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    document = knowledge_ingestion_store.get_document(document_id, context=context)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return document


@app.post("/knowledge/documents/{document_id}/approve", response_model=KnowledgeDocumentRecord)
def approve_knowledge_document(
    document_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeDocumentRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    try:
        document = knowledge_ingestion_service.approve_document(document_id, context=context)
    except RuntimeError as exc:
        _record_diagnostic_event(
            event_type="knowledge.embedding.failed",
            summary=str(exc),
            status_value="error",
            context=context,
            payload={"document_id": document_id},
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    _record_diagnostic_event(
        event_type="knowledge.document.approved",
        summary="Knowledge document approved for agent retrieval.",
        status_value="success",
        context=context,
        payload={
            "document_id": document.id,
            "source_path": document.source_path,
            "chunk_count": document.chunk_count,
        },
    )
    return document


@app.post("/knowledge/documents/{document_id}/resync", response_model=KnowledgeDocumentRecord)
def resync_knowledge_document(
    document_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeDocumentRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    try:
        document = knowledge_ingestion_service.resync_document(document_id, context=context)
    except RuntimeError as exc:
        _record_diagnostic_event(
            event_type="knowledge.document.resync_failed",
            summary=str(exc),
            status_value="error",
            context=context,
            payload={"document_id": document_id},
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    _record_diagnostic_event(
        event_type="knowledge.document.resynced",
        summary="Knowledge document refreshed through local sync.",
        status_value="success",
        context=context,
        payload={
            "document_id": document.id,
            "source_path": document.source_path,
            "chunk_count": document.chunk_count,
        },
    )
    return document


@app.post("/knowledge/documents/{document_id}/archive", response_model=KnowledgeDocumentRecord)
def archive_knowledge_document(
    document_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeDocumentRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    document = knowledge_ingestion_service.archive_document(document_id, context=context)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    _record_diagnostic_event(
        event_type="knowledge.document.archived",
        summary="Knowledge document archived and removed from retrieval.",
        status_value="info",
        context=context,
        payload={"document_id": document.id, "source_path": document.source_path},
    )
    return document


@app.post("/knowledge/search-test", response_model=KnowledgeSearchTestResponse)
def search_knowledge_test(
    request: KnowledgeSearchTestRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> KnowledgeSearchTestResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return KnowledgeSearchTestResponse(
        hits=retriever.search(
            request.query,
            intent=request.intent,
            risk_level=request.risk_level,
            limit=request.limit,
            context=TrustedContext(
                organization_id=context.organization_id,
                user_id=context.user_id,
                role=context.role,
            ),
        ),
    )


@app.websocket("/ws/conversations")
async def conversations_websocket(websocket: WebSocket, token: str) -> None:
    settings = get_settings()
    if not settings.sagad_realtime_secret:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    claims = verify_realtime_token(
        secret=settings.sagad_realtime_secret,
        token=token,
    )
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await realtime_manager.connect(claims.organization_id, websocket)
    await websocket.send_json(
        {
            "type": "heartbeat",
            "organization_id": claims.organization_id,
            "user_id": claims.user_id,
            "role": claims.role,
        },
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_manager.disconnect(claims.organization_id, websocket)


@app.post("/webhooks/chatwoot", response_model=ConversationRecord | IgnoredWebhookResponse)
async def receive_chatwoot_webhook(
    raw_payload: Annotated[dict[str, object], Body()],
    response: Response,
    x_chatwoot_token: Annotated[str | None, Header()] = None,
    token: Annotated[str | None, Query()] = None,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
) -> ConversationRecord | IgnoredWebhookResponse:
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    supplied_token = x_chatwoot_token or token

    # Always record the raw payload for debugging / audit purposes.
    _record_diagnostic_event(
        event_type="chatwoot.webhook.raw_received",
        summary="Raw Chatwoot webhook payload received.",
        status_value="info",
        conversation_id=None,
        payload={
            "raw_body": raw_payload,
            "token_present": bool(supplied_token),
            "headers": {
                "x_chatwoot_token": bool(x_chatwoot_token),
                "x_sagad_org_id": x_sagad_org_id,
                "x_sagad_user_id": x_sagad_user_id,
                "x_sagad_role": x_sagad_role,
            },
        },
        context=context,
    )

    try:
        payload = ChatwootWebhookPayload.model_validate(raw_payload)
    except Exception as exc:
        _log_event(
            logging.WARNING,
            "chatwoot.webhook.parse_failed",
            "Webhook payload could not be parsed.",
            error=exc.__class__.__name__,
            raw_payload_keys=list(raw_payload.keys()),
        )
        _record_diagnostic_event(
            event_type="chatwoot.webhook.parse_failed",
            summary=f"Webhook payload could not be parsed: {exc.__class__.__name__}.",
            status_value="error",
            conversation_id=None,
            payload={
                "raw_body": raw_payload,
                "error": exc.__class__.__name__,
                "error_detail": str(exc),
            },
            context=context,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "chatwoot_payload_parse_failed",
                "message": str(exc),
                "raw_keys": list(raw_payload.keys()),
            },
        ) from exc

    conversation_id = _sagad_conversation_id(payload)
    chatwoot_message_id = _message_id(payload)
    log_fields = {
        "chatwoot_conversation_id": _conversation_id(payload),
        "chatwoot_message_id": chatwoot_message_id,
        "event": payload.event,
        "message_type": payload.message_type,
        "private": payload.private,
        "token_present": bool(supplied_token),
    }
    _log_event(logging.INFO, "chatwoot.webhook.received", "Webhook request received.", **log_fields)
    _record_diagnostic_event(
        event_type="chatwoot.webhook.received",
        summary="Chatwoot webhook request received.",
        status_value="info",
        conversation_id=conversation_id,
        payload=log_fields,
        context=context,
    )
    try:
        _verify_webhook_token(supplied_token, context)
    except HTTPException:
        _log_event(
            logging.WARNING,
            "chatwoot.webhook.rejected_token",
            "Webhook rejected because the token did not match.",
            **log_fields,
        )
        _record_diagnostic_event(
            event_type="chatwoot.webhook.rejected_token",
            summary="Webhook rejected because the token did not match.",
            status_value="warning",
            conversation_id=conversation_id,
            payload=log_fields,
            context=context,
        )
        raise

    if _is_ignored_chatwoot_message(payload):
        _log_event(logging.INFO, "chatwoot.webhook.ignored", "Webhook event ignored.", **log_fields)
        _record_diagnostic_event(
            event_type="chatwoot.webhook.ignored",
            summary="Chatwoot webhook event ignored because it is not an inbound customer message.",
            status_value="info",
            conversation_id=conversation_id,
            payload=log_fields,
            context=context,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return IgnoredWebhookResponse(reason="Chatwoot event is not an inbound customer message.")

    incoming_message = payload.content or ""
    if not incoming_message.strip():
        _record_diagnostic_event(
            event_type="chatwoot.webhook.invalid_payload",
            summary="Webhook payload did not include message content.",
            status_value="error",
            conversation_id=conversation_id,
            payload=log_fields,
            context=context,
        )
        raise HTTPException(status_code=400, detail="Webhook payload did not include message content.")

    existing_record = store.get(conversation_id, context=context) if conversation_id else None
    if _message_already_recorded(existing_record, chatwoot_message_id):
        _log_event(logging.INFO, "chatwoot.webhook.duplicate", "Duplicate webhook retry ignored.", **log_fields)
        _record_diagnostic_event(
            event_type="chatwoot.webhook.duplicate",
            summary="Duplicate Chatwoot webhook retry ignored.",
            status_value="info",
            conversation_id=conversation_id,
            payload=log_fields,
            context=context,
        )
        return existing_record

    normalized_channel = channel_from_payload(
        payload,
        existing_channel=existing_record.channel if existing_record else None,
    )
    chatwoot_context = chatwoot_context_from_payload(
        payload.model_dump(mode="json", exclude_none=True),
        normalized_channel=normalized_channel,
    )
    initial_state = {
        "conversation_id": conversation_id,
        "chatwoot_conversation_id": _conversation_id(payload),
        "chatwoot_message_id": chatwoot_message_id,
        "customer_name": _customer_name(payload),
        "channel": normalized_channel,
        "incoming_message": incoming_message,
        "conversation_history": existing_record.messages if existing_record else [],
        "memory_context": store.list_memory_items(
            conversation_id,
            query=incoming_message,
            context=context,
        )
        if conversation_id
        else [],
        "trace_url": None,
    }
    final_state = await graph.ainvoke(initial_state)
    record_payload: dict[str, object] = {
        "chatwoot_conversation_id": final_state.get("chatwoot_conversation_id"),
        "chatwoot_message_id": final_state.get("chatwoot_message_id"),
        "customer_name": str(final_state.get("customer_name", "Chatwoot visitor")),
        "channel": str(final_state.get("channel", "chatwoot")),
        "incoming_message": incoming_message,
        "normalized_message": str(final_state.get("normalized_message", incoming_message)),
        "intent": str(final_state.get("intent", "unknown")),
        "risk_level": final_state.get("risk_level", "medium"),
        "retrieved_knowledge": final_state.get("retrieved_knowledge", []),
        "chatwoot_context": chatwoot_context,
        "draft_reply": str(final_state.get("draft_reply", "")),
        "qa_findings": final_state.get("qa_findings", []),
        "compliance_status": final_state.get("compliance_status", "needs_review"),
        "approval_status": "needs_approval",
        "send_status": "not_sent",
        "trace_url": final_state.get("trace_url"),
        "messages": [
            ConversationMessageRecord(
                sender_type="customer",
                body=incoming_message,
                external_message_id=chatwoot_message_id,
                provider="chatwoot",
                payload=payload.model_dump(mode="json", exclude_none=True),
            ),
        ],
    }
    for field_name in _SPRINT2_CONVERSATION_STATE_FIELDS:
        if field_name in ConversationRecord.model_fields and field_name in final_state:
            record_payload[field_name] = final_state.get(field_name)
    record = ConversationRecord(**record_payload)
    if conversation_id:
        record.id = conversation_id

    # Auto-send logic based on thresholds
    settings = configured_settings(get_settings(), context)
    compliance_status = record.compliance_status
    risk_level = record.risk_level
    confidence = record.final_confidence_score
    if confidence is None:
        confidence = record.retrieval_confidence
    draft_reply = record.draft_reply.strip()

    is_auto_send = (
        compliance_status == "pass"
        and risk_level == "low"
        and confidence is not None
        and confidence >= 0.88
        and bool(draft_reply)
    )

    plan = None
    tool_result = None
    result = None

    if is_auto_send:
        can_reply = True
        if record.chatwoot_context and record.chatwoot_context.can_reply is False:
            can_reply = False
            _record_diagnostic_event(
                event_type="chatwoot.send.blocked",
                summary="Chatwoot reports this conversation cannot receive replies.",
                status_value="warning",
                conversation_id=record.id,
                payload={
                    "chatwoot_conversation_id": record.chatwoot_conversation_id,
                },
                context=context,
                actor_type="system",
            )

        if can_reply:
            _log_event(
                logging.INFO,
                "chatwoot.send.attempt",
                "Auto-send conditions met; attempting Chatwoot send.",
                sagad_conversation_id=record.id,
                chatwoot_conversation_id=record.chatwoot_conversation_id,
            )
            _record_diagnostic_event(
                event_type="chatwoot.send.attempt",
                summary="Auto-send conditions met; attempting Chatwoot send.",
                status_value="info",
                conversation_id=record.id,
                payload={
                    "chatwoot_conversation_id": record.chatwoot_conversation_id,
                    "confidence": confidence,
                    "risk_level": risk_level,
                },
                context=context,
                actor_type="system",
            )
            policy_decision = evaluate_tool_policy(
                "chatwoot.messages.send_approved",
                _chatwoot_policy_context(
                    settings,
                    record,
                    approved=True,
                ),
                registry=tool_manifest_registry,
            )
            if policy_decision.allowed:
                result = await send_approved_reply(
                    settings=settings,
                    chatwoot_conversation_id=record.chatwoot_conversation_id,
                    content=draft_reply,
                )
                plan, tool_result = _chatwoot_send_tool_result(record, result, content=draft_reply)
                plan, tool_result = _attach_policy_metadata(
                    plan,
                    tool_result,
                    decision=policy_decision,
                    approved=True,
                    supervisor_id="system",
                    risk_level=record.risk_level,
                )
            else:
                result = {
                    "status": "blocked",
                    "detail": policy_decision.blocked_reason or "Send blocked by policy.",
                    "error_type": "policy_blocked",
                }
                plan, tool_result = _blocked_policy_tool_result(
                    tool_name="chatwoot.messages.send_approved",
                    action="send supervisor-approved reply",
                    args={
                        "chatwoot_conversation_id": record.chatwoot_conversation_id,
                        "content_preview": draft_reply[:160],
                    },
                    decision=policy_decision,
                    approved=True,
                    supervisor_id="system",
                    risk_level=record.risk_level,
                )
            record.approval_status = "sent" if result["status"] in {"sent", "dry_run"} else "send_failed"
            record.send_status = result["status"]
            if all(existing.id != plan.id for existing in record.tool_plans):
                record.tool_plans.append(plan)
            if all(existing.id != tool_result.id for existing in record.tool_results):
                record.tool_results.append(tool_result)
            if result["status"] in {"sent", "dry_run"}:
                record.messages.append(
                    ConversationMessageRecord(
                        sender_type="ai_agent",
                        body=draft_reply,
                        provider="sagad",
                        payload={
                            "approval": "auto_send",
                            "send_status": result["status"],
                            "tool_result_id": tool_result.id,
                        },
                    ),
                )

    saved = store.save(record, context=context)

    if is_auto_send and plan and tool_result:
        store.record_tool_execution(
            plan,
            tool_result,
            conversation_id=saved.id,
            context=context,
        )

    saved = _append_lifecycle_memory(
        saved,
        lifecycle_event="draft_created",
        context=context,
    )

    if is_auto_send and result and result["status"] in {"sent", "dry_run"}:
        saved = _append_lifecycle_memory(
            saved,
            lifecycle_event="approved_send",
            context=context,
        )
        event_status = "success" if result["status"] in {"sent", "dry_run"} else "error"
        event_type = (
            "chatwoot.send.succeeded"
            if result["status"] == "sent"
            else "chatwoot.send.dry_run"
            if result["status"] == "dry_run"
            else "chatwoot.send.failed"
        )
        log_level = logging.INFO if event_status != "error" else logging.ERROR
        _log_event(
            log_level,
            event_type,
            str(result.get("detail", "Chatwoot send completed.")),
            sagad_conversation_id=saved.id,
            chatwoot_conversation_id=saved.chatwoot_conversation_id,
            send_status=saved.send_status,
            http_status=result.get("http_status"),
            error_type=result.get("error_type"),
        )
        _record_diagnostic_event(
            event_type=event_type,
            summary=str(result.get("detail", "Chatwoot send completed.")),
            status_value=event_status,
            conversation_id=saved.id,
            payload={
                "send_status": saved.send_status,
                "approval_status": saved.approval_status,
                "tool_result_id": tool_result.id,
                "provider_result": _chatwoot_tool_payload(result),
                "policy_metadata": tool_result.data.get("policy_metadata"),
            },
            context=context,
            actor_type="system",
        )
    _log_event(
        logging.INFO,
        "chatwoot.webhook.persisted",
        "Inbound message persisted and draft generated.",
        sagad_conversation_id=saved.id,
        **log_fields,
    )
    _record_diagnostic_event(
        event_type="chatwoot.webhook.persisted",
        summary="Inbound message persisted and draft generated.",
        status_value="success",
        conversation_id=saved.id,
        payload={
            **log_fields,
            "intent": saved.intent,
            "risk_level": saved.risk_level,
            "approval_status": saved.approval_status,
        },
        context=context,
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "conversation.message_appended",
            saved,
            organization_id=context.organization_id,
        ),
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "conversation.upserted",
            saved,
            organization_id=context.organization_id,
        ),
    )
    return saved


# ---------------------------------------------------------------------------
# Universal webhook — POST /webhooks/{provider}
# ---------------------------------------------------------------------------


class DebouncedWebhookResponse(BaseModel):
    """Returned (202) when WEBHOOK_DEBOUNCE_ENABLED is on; processing completes in the background."""

    status: Literal["debounced"] = "debounced"
    provider: str
    conversation_id: str | None = None
    pending_keys: int = 0


# Dispatches to a registered ChannelAdapter (ghl today; chatwoot keeps its own
# dedicated /webhooks/chatwoot route above so its 14 tests stay untouched). The
# adapter verifies the inbound signature, normalizes the payload, then we run
# the same graph.ainvoke → record → (optional) auto-send pipeline. Debouncing is
# opt-in via WEBHOOK_DEBOUNCE_ENABLED (default false = synchronous ConversationRecord).

_debounce: DebounceCoordinator | None = None


def _get_debounce(settings: Settings) -> DebounceCoordinator:
    global _debounce
    if _debounce is None:
        _debounce = DebounceCoordinator(settings.webhook_debounce_ms, _debounce_process)
    return _debounce


def _universal_conversation_id(normalized: NormalizedInbound) -> str | None:
    ref = normalized.provider_conversation_id
    if not ref:
        ref = normalized.provider_message_id
    if not ref:
        return None
    return f"{normalized.provider}_{_safe_id_part(str(ref))}"


async def _maybe_auto_send_universal(
    adapter: ChannelAdapter,
    record: ConversationRecord,
    normalized: NormalizedInbound,
    settings: Settings,
    context: StoreContext,
) -> dict[str, object] | None:
    """Auto-send the draft through the adapter when risk/compliance thresholds are met.

    Auto-send fires when compliance is "pass", risk is low, confidence meets the configured
    RevOps auto-send threshold, and the draft is non-empty. The confidence threshold is
    ``settings.revops_autosend_confidence`` (default 0.88) — the SAME threshold the
    ``revops_autosend`` safe lane used to decide promotion, so the two gates stay consistent.
    In practice ``compliance_status == "pass"`` is only ever produced by the safe-lane
    promotion (the guardrail itself emits only needs_review/blocked), so this gate is reached
    solely via that narrow allowlist. Returns the send result dict, or None when auto-send
    conditions are not met.
    """
    draft_reply = (record.draft_reply or "").strip()
    confidence = record.final_confidence_score
    if confidence is None:
        confidence = record.retrieval_confidence
    is_auto_send = (
        record.compliance_status == "pass"
        and record.risk_level == "low"
        and confidence is not None
        and confidence >= float(settings.revops_autosend_confidence)
        and bool(draft_reply)
    )
    if not is_auto_send:
        return None

    _record_diagnostic_event(
        event_type=f"{normalized.provider}.send.attempt",
        summary=f"Auto-send conditions met; attempting {normalized.provider.upper()} send.",
        status_value="info",
        conversation_id=record.id,
        payload={
            "provider_conversation_id": normalized.provider_conversation_id,
            "confidence": confidence,
            "risk_level": record.risk_level,
            "outbound_mode": settings.ghl_outbound_mode if normalized.provider == "ghl" else "webhook",
        },
        context=context,
        actor_type="system",
    )
    result = await adapter.send_outbound(draft_reply, normalized, settings)
    record.approval_status = "sent" if result.get("status") in {"sent", "dry_run"} else "send_failed"
    record.send_status = result.get("status", "not_sent")
    if result.get("status") in {"sent", "dry_run"}:
        record.messages.append(
            ConversationMessageRecord(
                sender_type="ai_agent",
                body=draft_reply,
                provider=normalized.provider,
                payload={
                    "approval": "auto_send",
                    "send_status": result.get("status"),
                    "provider": normalized.provider,
                },
            ),
        )
    _record_diagnostic_event(
        event_type=f"{normalized.provider}.send.completed",
        summary=str(result.get("detail", f"{normalized.provider} send completed.")),
        status_value="success" if result.get("status") in {"sent", "dry_run"} else "error",
        conversation_id=record.id,
        payload={"provider_result": result},
        context=context,
        actor_type="system",
    )
    return result


async def _run_universal_inbound(
    adapter: ChannelAdapter,
    normalized: NormalizedInbound,
    *,
    context: StoreContext,
    settings: Settings,
) -> ConversationRecord:
    """Shared synchronous pipeline: normalize → graph.ainvoke → record → save → (auto-send).

    Called both by the universal webhook route (sync mode) and by the debounce
    flush callback (the burst is merged into `normalized.message_text` before calling).
    """
    conversation_id = _universal_conversation_id(normalized)
    incoming_message = normalized.message_text or ""

    existing_record = store.get(conversation_id, context=context) if conversation_id else None
    if _message_already_recorded(existing_record, normalized.provider_message_id):
        _record_diagnostic_event(
            event_type=f"{normalized.provider}.webhook.duplicate",
            summary=f"Duplicate {normalized.provider} webhook retry ignored.",
            status_value="info",
            conversation_id=conversation_id,
            payload={"provider_message_id": normalized.provider_message_id},
            context=context,
        )
        return existing_record  # type: ignore[return-value]

    log_fields = {
        "provider": normalized.provider,
        "provider_conversation_id": normalized.provider_conversation_id,
        "provider_message_id": normalized.provider_message_id,
        "event": normalized.event_type,
        "channel": normalized.channel,
    }
    _record_diagnostic_event(
        event_type=f"{normalized.provider}.webhook.processing",
        summary=f"{normalized.provider} webhook processing.",
        status_value="info",
        conversation_id=conversation_id,
        payload=log_fields,
        context=context,
    )

    initial_state: dict[str, object] = {
        "conversation_id": conversation_id,
        "chatwoot_conversation_id": None,
        "chatwoot_message_id": normalized.provider_message_id,
        "customer_name": normalized.customer_name,
        "channel": normalized.channel,
        "incoming_message": incoming_message,
        "conversation_history": existing_record.messages if existing_record else [],
        "memory_context": store.list_memory_items(
            conversation_id,
            query=incoming_message,
            context=context,
        )
        if conversation_id
        else [],
        "trace_url": None,
    }
    # Read-only CRM context (GHL today): pull contact + opportunity so the graph and the
    # RevOps queue can reason about deal stage/value. Provider-agnostic guard so non-GHL
    # adapters (Chatwoot) skip this and behave exactly as before. The fetch never blocks
    # inbound -- it degrades to None on timeout/error (see GhlAdapter.fetch_crm_context).
    crm_context: CrmContactContext | None = None
    if hasattr(adapter, "fetch_crm_context"):
        try:
            crm_context = await adapter.fetch_crm_context(normalized, settings)
        except Exception:  # belt-and-suspenders: never let CRM context break inbound
            crm_context = None
    if crm_context is not None:
        initial_state["crm_context"] = crm_context
    final_state = await graph.ainvoke(initial_state)

    # RevOps safe-lane promotion: a narrow allowlist of low-risk intents may be promoted from
    # needs_review -> "pass" so the reply can auto-send without a supervisor round-trip. The
    # guardrail's "blocked" verdict always wins -- we only consult the safe lane when the
    # guardrail did NOT block. Empty allowlist (default) => no promotion => prior behavior.
    if final_state.get("compliance_status") != "blocked":
        if revops_autosend_decision(final_state, settings) == "pass":
            final_state["compliance_status"] = "pass"

    record_payload: dict[str, object] = {
        "chatwoot_conversation_id": None,
        "chatwoot_message_id": None,
        "provider_conversation_id": normalized.provider_conversation_id,
        "customer_name": str(final_state.get("customer_name", normalized.customer_name)),
        "channel": str(final_state.get("channel", normalized.channel)),
        "incoming_message": incoming_message,
        "normalized_message": str(final_state.get("normalized_message", incoming_message)),
        "intent": str(final_state.get("intent", "unknown")),
        "risk_level": final_state.get("risk_level", "medium"),
        "retrieved_knowledge": final_state.get("retrieved_knowledge", []),
        "draft_reply": str(final_state.get("draft_reply", "")),
        "qa_findings": final_state.get("qa_findings", []),
        "compliance_status": final_state.get("compliance_status", "needs_review"),
        "approval_status": "needs_approval",
        "send_status": "not_sent",
        "trace_url": final_state.get("trace_url"),
        "crm_context": final_state.get("crm_context") or crm_context,
        "messages": [
            ConversationMessageRecord(
                sender_type="customer",
                body=incoming_message,
                external_message_id=normalized.provider_message_id,
                provider=normalized.provider,
                payload=normalized.raw_payload,
            ),
        ],
    }
    for field_name in _SPRINT2_CONVERSATION_STATE_FIELDS:
        if field_name in ConversationRecord.model_fields and field_name in final_state:
            record_payload[field_name] = final_state.get(field_name)
    record = ConversationRecord(**record_payload)
    if conversation_id:
        record.id = conversation_id

    await _maybe_auto_send_universal(adapter, record, normalized, settings, context)

    saved = store.save(record, context=context)
    saved = _append_lifecycle_memory(saved, lifecycle_event="draft_created", context=context)

    _record_diagnostic_event(
        event_type=f"{normalized.provider}.webhook.persisted",
        summary=f"{normalized.provider} inbound message persisted and draft generated.",
        status_value="success",
        conversation_id=saved.id,
        payload={
            **log_fields,
            "intent": saved.intent,
            "risk_level": saved.risk_level,
            "approval_status": saved.approval_status,
            "send_status": saved.send_status,
        },
        context=context,
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "conversation.upserted",
            saved,
            organization_id=context.organization_id,
        ),
    )
    return saved


async def _debounce_process(key: str, messages: list[NormalizedInbound]) -> None:
    """Debounce flush callback: merge the burst into the lead message and run the pipeline once."""
    if not messages:
        return
    lead = messages[-1]
    context = lead.extra.get("_debounce_context")
    settings = lead.extra.get("_debounce_settings")
    if context is None or settings is None:
        logger.warning("debounce.process_missing_context key=%s", key)
        return
    adapter = get_adapter(lead.provider)
    if adapter is None:
        logger.warning("debounce.unknown_provider key=%s provider=%s", key, lead.provider)
        return
    texts = [m.message_text for m in messages if m.message_text]
    if texts:
        lead.message_text = " | ".join(texts)
    _record_diagnostic_event(
        event_type=f"{lead.provider}.webhook.debounce_flushed",
        summary=f"Debounced burst of {len(messages)} message(s) flushed into one graph run.",
        status_value="info",
        conversation_id=key,
        payload={"provider": lead.provider, "message_count": len(messages)},
        context=context,
    )
    await _run_universal_inbound(adapter, lead, context=context, settings=settings)


@app.post("/webhooks/{provider}", response_model=ConversationRecord | IgnoredWebhookResponse | DebouncedWebhookResponse)
async def receive_universal_webhook(
    provider: str,
    request: Request,
    response: Response,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
) -> ConversationRecord | IgnoredWebhookResponse | DebouncedWebhookResponse:
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    adapter = get_adapter(provider)
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_webhook_provider",
                "message": f"Unknown webhook provider '{provider}'.",
                "known_providers": registered_providers(),
                "note": "Chatwoot uses the dedicated /webhooks/chatwoot endpoint.",
            },
        )

    raw_body = await request.body()
    try:
        raw_payload = await request.json()
    except Exception as exc:
        _record_diagnostic_event(
            event_type=f"{provider}.webhook.parse_failed",
            summary=f"{provider} webhook payload could not be parsed: {exc.__class__.__name__}.",
            status_value="error",
            conversation_id=None,
            payload={"error": exc.__class__.__name__},
            context=context,
        )
        raise HTTPException(
            status_code=400,
            detail={"error": f"{provider}_payload_parse_failed", "message": str(exc)},
        ) from exc

    _record_diagnostic_event(
        event_type=f"{provider}.webhook.raw_received",
        summary=f"Raw {provider} webhook payload received.",
        status_value="info",
        conversation_id=None,
        payload={"raw_body": raw_payload, "provider": provider},
        context=context,
    )

    # verify_inbound raises HTTPException(401) on signature/token failure.
    adapter.verify_inbound(raw_body, dict(request.headers))
    normalized = adapter.normalize(raw_payload if isinstance(raw_payload, dict) else {})

    log_fields = {
        "provider": normalized.provider,
        "provider_conversation_id": normalized.provider_conversation_id,
        "provider_message_id": normalized.provider_message_id,
        "channel": normalized.channel,
        "event": normalized.event_type,
    }
    _log_event(logging.INFO, f"{normalized.provider}.webhook.received", "Webhook request received.", **log_fields)

    if adapter.ignores(normalized):
        _record_diagnostic_event(
            event_type=f"{normalized.provider}.webhook.ignored",
            summary=f"{normalized.provider} webhook event ignored (not an inbound customer message).",
            status_value="info",
            conversation_id=_universal_conversation_id(normalized),
            payload=log_fields,
            context=context,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return IgnoredWebhookResponse(reason=f"{normalized.provider} event is not an inbound customer message.")

    if not (normalized.message_text or "").strip():
        _record_diagnostic_event(
            event_type=f"{normalized.provider}.webhook.invalid_payload",
            summary=f"{normalized.provider} webhook payload did not include message content.",
            status_value="error",
            conversation_id=_universal_conversation_id(normalized),
            payload=log_fields,
            context=context,
        )
        raise HTTPException(status_code=400, detail="Webhook payload did not include message content.")

    settings = configured_settings(get_settings(), context)

    if settings.webhook_debounce_enabled:
        normalized.extra["_debounce_context"] = context
        normalized.extra["_debounce_settings"] = settings
        coordinator = _get_debounce(settings)
        await coordinator.schedule(_universal_conversation_id(normalized) or provider, normalized)
        _record_diagnostic_event(
            event_type=f"{normalized.provider}.webhook.debounced",
            summary=f"{normalized.provider} webhook buffered for debounced processing.",
            status_value="info",
            conversation_id=_universal_conversation_id(normalized),
            payload={**log_fields, "pending_keys": coordinator.pending_keys},
            context=context,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "debounced",
            "provider": normalized.provider,
            "conversation_id": _universal_conversation_id(normalized),
            "pending_keys": coordinator.pending_keys,
        }  # type: ignore[return-value]

    saved = await _run_universal_inbound(adapter, normalized, context=context, settings=settings)
    return saved


@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
    ticket_status: Annotated[str | None, Query(description="Filter the RevOps ticket queue by ticket status.")] = None,
    assignee: Annotated[str | None, Query(description="Filter by assigned supervisor/user id.")] = None,
    priority: Annotated[str | None, Query(description="Filter by ticket priority.")] = None,
    sla_status: Annotated[str | None, Query(description="Filter by runtime SLA health (on_track|warning|overdue|none).")] = None,
    overdue: Annotated[bool | None, Query(description="When true, return only tickets past their SLA deadline.")] = None,
) -> ConversationListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    records = store.list(
        context=context,
        ticket_status=ticket_status,
        assignee=assignee,
        priority=priority,
    )
    # SLA-derived filters are applied here (not in the store) because `sla_status` is a runtime
    # computation against `now`, not a persisted column.
    if overdue or sla_status:
        filtered: list[ConversationRecord] = []
        for record in records:
            status = compute_sla_status(
                record.sla_due_at,
                priority=record.priority,
                created_at=record.created_at,
            )
            if overdue and status != "overdue":
                continue
            if sla_status and status != sla_status:
                continue
            filtered.append(record)
        records = filtered
    return ConversationListResponse(
        conversations=[
            _with_sla_status(_attach_memory_context(record, context=context))
            for record in records
        ],
    )


@app.patch("/conversations/{conversation_id}/ticket", response_model=ConversationRecord)
async def update_conversation_ticket(
    conversation_id: str,
    request: TicketUpdateRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
    force: Annotated[bool, Query(description="Bypass ticket_status transition validation (supervisor override, e.g. to reopen a resolved ticket).")] = False,
) -> ConversationRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    record = store.get(conversation_id, context=context)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _require_supervisor_approval(True)
    # Validate the ticket_status transition against the allowed-state machine. Same-status
    # writes are no-ops and allowed; `resolved` is terminal and requires `force=true` to reopen.
    if request.ticket_status is not None and not force:
        current = record.ticket_status
        if request.ticket_status != current:
            allowed = TICKET_STATUS_TRANSITIONS.get(current, set())
            if request.ticket_status not in allowed:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Invalid ticket status transition: {current} -> {request.ticket_status}. "
                        "Use ?force=true to override (supervisor reopen)."
                    ),
                )
    updated = store.update_ticket(
        conversation_id,
        ticket_status=request.ticket_status,
        assignee=request.assignee,
        priority=request.priority,
        pipeline_stage=request.pipeline_stage,
        sla_due_at=request.sla_due_at,
        context=context,
    )
    if updated is None:
        updated = record
    _record_diagnostic_event(
        event_type="ticket.updated",
        summary="Supervisor updated the RevOps ticket fields.",
        status_value="info",
        conversation_id=updated.id,
        payload={
            "ticket_status": updated.ticket_status,
            "assignee": updated.assignee,
            "priority": updated.priority,
            "pipeline_stage": updated.pipeline_stage,
            "supervisor_id": request.supervisor_id,
        },
        context=context,
        actor_type="user",
        actor_id=request.supervisor_id,
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "ticket.updated",
            updated,
            organization_id=context.organization_id,
        ),
    )
    return _with_sla_status(_attach_memory_context(updated, context=context))


@app.get("/conversations/{conversation_id}", response_model=ConversationRecord)
async def get_conversation(
    conversation_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> ConversationRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    record = store.get(conversation_id, context=context)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if record.chatwoot_conversation_id:
        chatwoot_context = await fetch_conversation_details(
            settings=configured_settings(get_settings(), context),
            chatwoot_conversation_id=record.chatwoot_conversation_id,
            fallback_channel=record.channel,
        )
        record.chatwoot_context = chatwoot_context
        if (
            chatwoot_context.normalized_channel
            and record.channel in {"chatwoot", "unknown"}
        ):
            record.channel = chatwoot_context.normalized_channel
        if chatwoot_context.fetch_status in {"ready", "failed"}:
            record = store.save(record, context=context)
            if chatwoot_context.fetch_status == "failed":
                _record_diagnostic_event(
                    event_type="chatwoot.details.failed",
                    summary="Chatwoot conversation details could not be fetched.",
                    status_value="warning",
                    conversation_id=record.id,
                    payload={"fetch_error": chatwoot_context.fetch_error or "unknown"},
                    context=context,
                )
    return _with_sla_status(_attach_memory_context(record, context=context))


@app.post("/conversations/{conversation_id}/resolve", response_model=ConversationRecord)
async def resolve_chatwoot_conversation(
    conversation_id: str,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> ConversationRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    _require_supervisor_approval(True)
    record = store.get(conversation_id, context=context)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if record.chatwoot_context and record.chatwoot_context.status == "resolved":
        _record_diagnostic_event(
            event_type="chatwoot.resolve.preflight_failed",
            summary="Chatwoot resolve skipped because the conversation is already resolved.",
            status_value="warning",
            conversation_id=record.id,
            payload={
                "reason": "already_resolved",
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
            },
            context=context,
            actor_type="user",
            actor_id=context.user_id,
        )
        raise HTTPException(status_code=409, detail="Conversation is already resolved.")

    settings = configured_settings(get_settings(), context)
    if settings.chatwoot_dry_run:
        _record_diagnostic_event(
            event_type="chatwoot.resolve.preflight_failed",
            summary="Chatwoot resolve skipped because dry-run is enabled.",
            status_value="warning",
            conversation_id=record.id,
            payload={
                "reason": "dry_run_enabled",
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
            },
            context=context,
            actor_type="user",
            actor_id=context.user_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Chatwoot resolve is disabled while dry-run is enabled.",
        )

    source_id = record.chatwoot_context.source_id if record.chatwoot_context else None
    if not source_id:
        _record_diagnostic_event(
            event_type="chatwoot.resolve.preflight_failed",
            summary="Chatwoot resolve requires a contact/source identifier.",
            status_value="warning",
            conversation_id=record.id,
            payload={
                "reason": "missing_source_id",
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
            },
            context=context,
            actor_type="user",
            actor_id=context.user_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Chatwoot resolve requires a contact/source identifier.",
        )

    inbox_identifier = settings.chatwoot_inbox_identifier
    if not inbox_identifier:
        _record_diagnostic_event(
            event_type="chatwoot.resolve.preflight_failed",
            summary="Chatwoot resolve requires the API channel inbox identifier.",
            status_value="warning",
            conversation_id=record.id,
            payload={
                "reason": "missing_inbox_identifier",
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
                "source_id": source_id,
            },
            context=context,
            actor_type="user",
            actor_id=context.user_id,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Chatwoot resolve requires the API channel inbox identifier. "
                "Set CHATWOOT_INBOX_IDENTIFIER or the Chatwoot integration "
                "Inbox identifier to the value from API Channel -> Settings -> "
                "Configuration; this is not the numeric inbox_id."
            ),
        )

    _record_diagnostic_event(
        event_type="chatwoot.resolve.attempt",
        summary="Supervisor requested Chatwoot conversation resolve.",
        status_value="info",
        conversation_id=record.id,
        payload={
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "source_id": source_id,
            "inbox_identifier": inbox_identifier,
        },
        context=context,
        actor_type="user",
        actor_id=context.user_id,
    )
    policy_decision = evaluate_tool_policy(
        "chatwoot.conversations.resolve",
        _chatwoot_policy_context(
            settings,
            record,
            approved=True,
            risk_level="medium",
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        result = await resolve_conversation(
            settings=settings,
            chatwoot_conversation_id=record.chatwoot_conversation_id,
            contact_identifier=source_id,
            inbox_identifier=inbox_identifier,
        )
        plan, tool_result = _chatwoot_resolve_tool_result(record, result)
        plan, tool_result = _attach_policy_metadata(
            plan,
            tool_result,
            decision=policy_decision,
            approved=True,
            supervisor_id=context.user_id,
            risk_level="medium",
        )
    else:
        result = {
            "status": "blocked",
            "detail": policy_decision.blocked_reason or "Resolve blocked by policy.",
            "error_type": "policy_blocked",
        }
        plan, tool_result = _blocked_policy_tool_result(
            tool_name="chatwoot.conversations.resolve",
            action="resolve conversation",
            args={
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
                "source_id": source_id,
            },
            decision=policy_decision,
            approved=True,
            supervisor_id=context.user_id,
            risk_level="medium",
        )
    if all(existing.id != plan.id for existing in record.tool_plans):
        record.tool_plans.append(plan)
    if all(existing.id != tool_result.id for existing in record.tool_results):
        record.tool_results.append(tool_result)
    if result["status"] == "resolved" and record.chatwoot_context:
        record.chatwoot_context.status = "resolved"
    record.updated_at = datetime.now(timezone.utc)
    saved = store.save(record, context=context)
    store.record_tool_execution(
        plan,
        tool_result,
        conversation_id=saved.id,
        context=context,
    )
    event_type = (
        "chatwoot.resolve.succeeded"
        if result["status"] == "resolved"
        else "chatwoot.resolve.failed"
    )
    _record_diagnostic_event(
        event_type=event_type,
        summary=str(result.get("detail", "Chatwoot resolve completed.")),
        status_value="success" if result["status"] == "resolved" else "error",
        conversation_id=saved.id,
        payload={
            **_chatwoot_tool_payload(result),
            "policy_metadata": tool_result.data.get("policy_metadata"),
        },
        context=context,
        actor_type="user",
        actor_id=context.user_id,
    )
    if result["status"] == "resolved":
        saved = _append_lifecycle_memory(
            saved,
            lifecycle_event="resolved",
            context=context,
        )
    else:
        saved = _attach_memory_context(saved, context=context)
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "conversation.resolved",
            saved,
            organization_id=context.organization_id,
        ),
    )
    return saved


async def _approve_send_ghl(
    record: ConversationRecord,
    content: str,
    request: ApprovalRequest,
    settings: Settings,
    context: StoreContext,
) -> ConversationRecord:
    """Supervisor-approved send for a GHL-sourced conversation.

    Routes the approved reply through ``GhlAdapter.send_outbound`` (rebuilt NormalizedInbound
    carries ``record.provider_conversation_id`` so the send lands in the right GHL conversation),
    runs the ``ghl.messages.send_approved`` tool policy, records the tool execution + approval,
    and broadcasts the update. Mirrors the Chatwoot approve-send shape but skips the
    Chatwoot-only ``can_reply`` 409. Provider-agnostic ``store.record_approval`` handles the
    ``sent``/``send_failed`` audit.
    """
    adapter = get_adapter("ghl")
    normalized = NormalizedInbound(
        provider="ghl",
        provider_conversation_id=record.provider_conversation_id,
        provider_message_id=None,
        customer_name=record.customer_name,
        channel=record.channel or "sms",
        message_text=record.incoming_message,
        event_type=None,
        raw_payload={},
        extra={},
    )
    _log_event(
        logging.INFO,
        "ghl.send.attempt",
        "Supervisor approved reply; attempting GHL send.",
        sagad_conversation_id=record.id,
        provider_conversation_id=record.provider_conversation_id,
    )
    _record_diagnostic_event(
        event_type="ghl.send.attempt",
        summary="Supervisor approved reply; attempting GHL send.",
        status_value="info",
        conversation_id=record.id,
        payload={
            "provider_conversation_id": record.provider_conversation_id,
            "supervisor_id": request.supervisor_id,
            "edited": bool(request.edited_reply),
        },
        context=context,
        actor_type="user",
        actor_id=request.supervisor_id,
    )
    policy_decision = evaluate_tool_policy(
        "ghl.messages.send_approved",
        _ghl_policy_context(settings, record, approved=True),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        result = await adapter.send_outbound(content, normalized, settings)
        result = dict(result)  # SendResult -> plain dict for the helper paths below
        plan, tool_result = _ghl_send_tool_result(record, result, content=content)
        plan, tool_result = _attach_policy_metadata(
            plan,
            tool_result,
            decision=policy_decision,
            approved=True,
            supervisor_id=request.supervisor_id,
            risk_level=record.risk_level,
        )
    else:
        result = {
            "status": "blocked",
            "detail": policy_decision.blocked_reason or "Send blocked by policy.",
            "error_type": "policy_blocked",
        }
        plan, tool_result = _blocked_policy_tool_result(
            tool_name="ghl.messages.send_approved",
            action="send supervisor-approved reply",
            args={
                "provider_conversation_id": record.provider_conversation_id,
                "content_preview": content[:160],
            },
            decision=policy_decision,
            approved=True,
            supervisor_id=request.supervisor_id,
            risk_level=record.risk_level,
        )
    record.draft_reply = content
    record.approval_status = "sent" if result["status"] in {"sent", "dry_run"} else "send_failed"
    record.send_status = result["status"]
    if all(existing.id != plan.id for existing in record.tool_plans):
        record.tool_plans.append(plan)
    if all(existing.id != tool_result.id for existing in record.tool_results):
        record.tool_results.append(tool_result)
    if result["status"] in {"sent", "dry_run"}:
        record.messages.append(
            ConversationMessageRecord(
                sender_type="ai_agent",
                body=content,
                provider="ghl",
                payload={
                    "approval": "supervisor_approved",
                    "send_status": result["status"],
                    "tool_result_id": tool_result.id,
                },
            ),
        )
    record.updated_at = datetime.now(timezone.utc)
    saved = store.save(record, context=context)
    store.record_tool_execution(
        plan,
        tool_result,
        conversation_id=saved.id,
        context=context,
    )
    store.record_approval(
        saved,
        supervisor_id=request.supervisor_id,
        approved=True,
        edited_reply=request.edited_reply,
        context=context,
    )
    if result["status"] in {"sent", "dry_run"}:
        saved = _append_lifecycle_memory(saved, lifecycle_event="approved_send", context=context)
    else:
        saved = _attach_memory_context(saved, context=context)
    event_status = "success" if result["status"] in {"sent", "dry_run"} else "error"
    event_type = (
        "ghl.send.succeeded"
        if result["status"] == "sent"
        else "ghl.send.dry_run"
        if result["status"] == "dry_run"
        else "ghl.send.failed"
    )
    log_level = logging.INFO if event_status != "error" else logging.ERROR
    _log_event(
        log_level,
        event_type,
        str(result.get("detail", "GHL send completed.")),
        sagad_conversation_id=saved.id,
        provider_conversation_id=saved.provider_conversation_id,
        send_status=saved.send_status,
        http_status=result.get("http_status"),
        error_type=result.get("error_type"),
    )
    _record_diagnostic_event(
        event_type=event_type,
        summary=str(result.get("detail", "GHL send completed.")),
        status_value=event_status,
        conversation_id=saved.id,
        payload={
            "send_status": saved.send_status,
            "approval_status": saved.approval_status,
            "tool_result_id": tool_result.id,
            "provider_result": _ghl_tool_payload(result),
            "policy_metadata": tool_result.data.get("policy_metadata"),
        },
        context=context,
        actor_type="user",
        actor_id=request.supervisor_id,
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "approval.updated",
            saved,
            organization_id=context.organization_id,
        ),
    )
    return saved


@app.post("/conversations/{conversation_id}/approve-send", response_model=ConversationRecord)
async def approve_send(
    conversation_id: str,
    request: ApprovalRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> ConversationRecord:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    record = store.get(conversation_id, context=context)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if not request.approved:
        record.approval_status = "rejected"
        record.send_status = "not_sent"
        saved = store.save(record, context=context)
        store.record_approval(
            saved,
            supervisor_id=request.supervisor_id,
            approved=False,
            edited_reply=request.edited_reply,
            context=context,
        )
        await realtime_manager.broadcast(
            context.organization_id,
            _realtime_event(
                "approval.updated",
                saved,
                organization_id=context.organization_id,
            ),
        )
        return _attach_memory_context(saved, context=context)

    if record.approval_status not in {"needs_approval", "send_failed"}:
        raise HTTPException(status_code=409, detail="Conversation is not waiting for approval.")

    content = request.edited_reply or record.draft_reply
    # Provider dispatch: a GHL-sourced conversation (provider_conversation_id set, no Chatwoot
    # context) routes through the GHL adapter's send_outbound. Everything else uses the existing
    # Chatwoot send path verbatim below, so all Chatwoot approve-send behavior is unchanged.
    if (
        record.provider_conversation_id
        and not record.chatwoot_conversation_id
        and not record.chatwoot_context
    ):
        settings = configured_settings(get_settings(), context)
        return await _approve_send_ghl(record, content, request, settings, context)

    if record.chatwoot_context and record.chatwoot_context.can_reply is False:
        _record_diagnostic_event(
            event_type="chatwoot.send.blocked",
            summary="Chatwoot reports this conversation cannot receive replies.",
            status_value="warning",
            conversation_id=record.id,
            payload={
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
                "source_id": record.chatwoot_context.source_id,
            },
            context=context,
            actor_type="user",
            actor_id=request.supervisor_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Chatwoot reports this conversation cannot receive replies.",
        )
    _log_event(
        logging.INFO,
        "chatwoot.send.attempt",
        "Supervisor approved reply; attempting Chatwoot send.",
        sagad_conversation_id=record.id,
        chatwoot_conversation_id=record.chatwoot_conversation_id,
    )
    _record_diagnostic_event(
        event_type="chatwoot.send.attempt",
        summary="Supervisor approved reply; attempting Chatwoot send.",
        status_value="info",
        conversation_id=record.id,
        payload={
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "supervisor_id": request.supervisor_id,
            "edited": bool(request.edited_reply),
        },
        context=context,
        actor_type="user",
        actor_id=request.supervisor_id,
    )
    settings = configured_settings(get_settings(), context)
    policy_decision = evaluate_tool_policy(
        "chatwoot.messages.send_approved",
        _chatwoot_policy_context(
            settings,
            record,
            approved=True,
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        result = await send_approved_reply(
            settings=settings,
            chatwoot_conversation_id=record.chatwoot_conversation_id,
            content=content,
        )
        plan, tool_result = _chatwoot_send_tool_result(record, result, content=content)
        plan, tool_result = _attach_policy_metadata(
            plan,
            tool_result,
            decision=policy_decision,
            approved=True,
            supervisor_id=request.supervisor_id,
            risk_level=record.risk_level,
        )
    else:
        result = {
            "status": "blocked",
            "detail": policy_decision.blocked_reason or "Send blocked by policy.",
            "error_type": "policy_blocked",
        }
        plan, tool_result = _blocked_policy_tool_result(
            tool_name="chatwoot.messages.send_approved",
            action="send supervisor-approved reply",
            args={
                "chatwoot_conversation_id": record.chatwoot_conversation_id,
                "content_preview": content[:160],
            },
            decision=policy_decision,
            approved=True,
            supervisor_id=request.supervisor_id,
            risk_level=record.risk_level,
        )
    record.draft_reply = content
    record.approval_status = "sent" if result["status"] in {"sent", "dry_run"} else "send_failed"
    record.send_status = result["status"]
    if all(existing.id != plan.id for existing in record.tool_plans):
        record.tool_plans.append(plan)
    if all(existing.id != tool_result.id for existing in record.tool_results):
        record.tool_results.append(tool_result)
    if result["status"] in {"sent", "dry_run"}:
        record.messages.append(
            ConversationMessageRecord(
                sender_type="ai_agent",
                body=content,
                provider="sagad",
                payload={
                    "approval": "supervisor_approved",
                    "send_status": result["status"],
                    "tool_result_id": tool_result.id,
                },
            ),
        )
    record.updated_at = datetime.now(timezone.utc)
    saved = store.save(record, context=context)
    store.record_tool_execution(
        plan,
        tool_result,
        conversation_id=saved.id,
        context=context,
    )
    store.record_approval(
        saved,
        supervisor_id=request.supervisor_id,
        approved=True,
        edited_reply=request.edited_reply,
        context=context,
    )
    if result["status"] in {"sent", "dry_run"}:
        saved = _append_lifecycle_memory(
            saved,
            lifecycle_event="approved_send",
            context=context,
        )
    else:
        saved = _attach_memory_context(saved, context=context)
    event_status = "success" if result["status"] in {"sent", "dry_run"} else "error"
    event_type = (
        "chatwoot.send.succeeded"
        if result["status"] == "sent"
        else "chatwoot.send.dry_run"
        if result["status"] == "dry_run"
        else "chatwoot.send.failed"
    )
    log_level = logging.INFO if event_status != "error" else logging.ERROR
    _log_event(
        log_level,
        event_type,
        str(result.get("detail", "Chatwoot send completed.")),
        sagad_conversation_id=saved.id,
        chatwoot_conversation_id=saved.chatwoot_conversation_id,
        send_status=saved.send_status,
        http_status=result.get("http_status"),
        error_type=result.get("error_type"),
    )
    _record_diagnostic_event(
        event_type=event_type,
        summary=str(result.get("detail", "Chatwoot send completed.")),
        status_value=event_status,
        conversation_id=saved.id,
        payload={
            "send_status": saved.send_status,
            "approval_status": saved.approval_status,
            "tool_result_id": tool_result.id,
            "provider_result": _chatwoot_tool_payload(result),
            "policy_metadata": tool_result.data.get("policy_metadata"),
        },
        context=context,
        actor_type="user",
        actor_id=request.supervisor_id,
    )
    await realtime_manager.broadcast(
        context.organization_id,
        _realtime_event(
            "approval.updated",
            saved,
            organization_id=context.organization_id,
        ),
    )
    return saved


@app.post("/tools/crm/lookup-contact", response_model=CrmToolResponse)
async def crm_lookup_contact(
    request: CrmLookupContactRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> CrmToolResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    settings = configured_settings(get_settings(), context)
    policy_decision = evaluate_tool_policy(
        "crm.lookup_contact",
        _twenty_policy_context(
            settings,
            selected_agent=_policy_agent_from_tool_request(
                context=context,
                conversation_id=request.conversation_id,
                selected_agent=request.selected_agent,
            ),
            approved=request.approved,
            risk_level="low",
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        crm_context, plan, result = await TwentyAdapter(settings).lookup_contact(
            request.query,
            conversation_id=request.conversation_id,
        )
        plan, result = _attach_policy_metadata(
            plan,
            result,
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="low",
        )
    else:
        crm_context = None
        plan, result = _blocked_policy_tool_result(
            tool_name="crm.lookup_contact",
            action="Lookup contact in external Twenty CRM.",
            args={
                "query": request.query,
                "conversation_id": request.conversation_id,
            },
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="low",
        )
    store.record_tool_execution(
        plan,
        result,
        conversation_id=request.conversation_id,
        crm_context=crm_context,
        context=context,
    )
    return CrmToolResponse(plan=plan, result=result, crm_context=crm_context)


@app.post("/tools/crm/create-note", response_model=CrmToolResponse)
async def crm_create_note(
    request: CrmCreateNoteRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> CrmToolResponse:
    _require_supervisor_approval(request.approved)
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    settings = configured_settings(get_settings(), context)
    policy_decision = evaluate_tool_policy(
        "crm.create_note",
        _twenty_policy_context(
            settings,
            selected_agent=_policy_agent_from_tool_request(
                context=context,
                conversation_id=request.conversation_id,
                selected_agent=request.selected_agent,
            ),
            approved=request.approved,
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        plan, result = await TwentyAdapter(settings).create_note(
            request.contact_id,
            request.note,
            conversation_id=request.conversation_id,
            approved=request.approved,
        )
        plan, result = _attach_policy_metadata(
            plan,
            result,
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="medium",
        )
    else:
        plan, result = _blocked_policy_tool_result(
            tool_name="crm.create_note",
            action="Create a note in external Twenty CRM.",
            args={
                "contact_id": request.contact_id,
                "note": request.note,
                "conversation_id": request.conversation_id,
            },
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="medium",
        )
    store.record_tool_execution(
        plan,
        result,
        conversation_id=request.conversation_id,
        context=context,
    )
    return CrmToolResponse(plan=plan, result=result)


@app.post("/tools/crm/create-task", response_model=CrmToolResponse)
async def crm_create_task(
    request: CrmCreateTaskRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> CrmToolResponse:
    _require_supervisor_approval(request.approved)
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    settings = configured_settings(get_settings(), context)
    policy_decision = evaluate_tool_policy(
        "crm.create_task",
        _twenty_policy_context(
            settings,
            selected_agent=_policy_agent_from_tool_request(
                context=context,
                conversation_id=request.conversation_id,
                selected_agent=request.selected_agent,
            ),
            approved=request.approved,
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        plan, result = await TwentyAdapter(settings).create_task(
            request.contact_id,
            request.title,
            due_at=request.due_at,
            owner_id=request.owner_id,
            conversation_id=request.conversation_id,
            approved=request.approved,
        )
        plan, result = _attach_policy_metadata(
            plan,
            result,
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="medium",
        )
    else:
        plan, result = _blocked_policy_tool_result(
            tool_name="crm.create_task",
            action="Create a task in external Twenty CRM.",
            args={
                "contact_id": request.contact_id,
                "title": request.title,
                "due_at": request.due_at.isoformat() if request.due_at else None,
                "owner_id": request.owner_id,
                "conversation_id": request.conversation_id,
            },
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="medium",
        )
    store.record_tool_execution(
        plan,
        result,
        conversation_id=request.conversation_id,
        context=context,
    )
    return CrmToolResponse(plan=plan, result=result)


@app.post("/tools/crm/update-lead-stage", response_model=CrmToolResponse)
async def crm_update_lead_stage(
    request: CrmUpdateLeadStageRequest,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> CrmToolResponse:
    _require_supervisor_approval(request.approved)
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    settings = configured_settings(get_settings(), context)
    policy_decision = evaluate_tool_policy(
        "crm.update_lead_stage",
        _twenty_policy_context(
            settings,
            selected_agent=_policy_agent_from_tool_request(
                context=context,
                conversation_id=request.conversation_id,
                selected_agent=request.selected_agent,
            ),
            approved=request.approved,
            risk_level="high",
        ),
        registry=tool_manifest_registry,
    )
    if policy_decision.allowed:
        plan, result = await TwentyAdapter(settings).update_lead_stage(
            request.contact_id,
            request.lead_stage,
            conversation_id=request.conversation_id,
            approved=request.approved,
        )
        plan, result = _attach_policy_metadata(
            plan,
            result,
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="high",
        )
    else:
        plan, result = _blocked_policy_tool_result(
            tool_name="crm.update_lead_stage",
            action="Update lead stage in external Twenty CRM.",
            args={
                "contact_id": request.contact_id,
                "lead_stage": request.lead_stage,
                "conversation_id": request.conversation_id,
            },
            decision=policy_decision,
            approved=request.approved,
            supervisor_id=request.supervisor_id,
            risk_level="high",
        )
    store.record_tool_execution(
        plan,
        result,
        conversation_id=request.conversation_id,
        context=context,
    )
    return CrmToolResponse(plan=plan, result=result)
