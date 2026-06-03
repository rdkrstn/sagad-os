from datetime import datetime, timezone
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect, status

from agent_studio.chatwoot import send_approved_reply
from agent_studio.config import get_settings
from agent_studio.db import initialize_database
from agent_studio.graph import graph
from agent_studio.realtime import realtime_manager, verify_realtime_token
from agent_studio.retrieval import retriever
from agent_studio.schemas import (
    ApprovalRequest,
    ChatwootWebhookPayload,
    ConversationMessageRecord,
    ConversationListResponse,
    ConversationRecord,
    CrmCreateNoteRequest,
    CrmCreateTaskRequest,
    CrmLookupContactRequest,
    CrmProviderStatus,
    CrmToolResponse,
    CrmUpdateLeadStageRequest,
    ExternalIntegrationStatus,
    HealthResponse,
    IgnoredWebhookResponse,
    IntegrationListResponse,
)
from agent_studio.store import StoreContext, store
from agent_studio.twenty import TwentyAdapter, twenty_status


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    initialize_database(get_settings())
    yield


app = FastAPI(title="Sagad Agent Studio", version="0.1.0", lifespan=lifespan)


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


def _verify_webhook_token(token: str | None) -> None:
    settings = get_settings()
    if settings.chatwoot_webhook_token and token != settings.chatwoot_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid Chatwoot webhook token.")


def _verify_internal_secret(token: str | None) -> None:
    settings = get_settings()
    if settings.agent_studio_internal_secret and token != settings.agent_studio_internal_secret:
        raise HTTPException(status_code=401, detail="Invalid Agent Studio internal secret.")


def _integration_statuses() -> list[ExternalIntegrationStatus]:
    settings = get_settings()
    chatwoot_status = "ready" if settings.chatwoot_send_enabled else "dry_run"
    langsmith_ready = bool(settings.langsmith_api_key and settings.langsmith_tracing)
    return [
        ExternalIntegrationStatus(
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
        twenty_status(settings),
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


@app.get("/integrations", response_model=IntegrationListResponse)
def list_integrations() -> IntegrationListResponse:
    return IntegrationListResponse(integrations=_integration_statuses())


@app.get("/integrations/twenty/health", response_model=CrmProviderStatus)
def get_twenty_health() -> CrmProviderStatus:
    return twenty_status(get_settings())


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
    payload: ChatwootWebhookPayload,
    response: Response,
    x_chatwoot_token: Annotated[str | None, Header()] = None,
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
) -> ConversationRecord | IgnoredWebhookResponse:
    _verify_webhook_token(x_chatwoot_token)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)

    if _is_ignored_chatwoot_message(payload):
        response.status_code = status.HTTP_202_ACCEPTED
        return IgnoredWebhookResponse(reason="Chatwoot event is not an inbound customer message.")

    incoming_message = payload.content or ""
    if not incoming_message.strip():
        raise HTTPException(status_code=400, detail="Webhook payload did not include message content.")

    conversation_id = _sagad_conversation_id(payload)
    chatwoot_message_id = _message_id(payload)
    existing_record = store.get(conversation_id, context=context) if conversation_id else None
    if _message_already_recorded(existing_record, chatwoot_message_id):
        return existing_record

    initial_state = {
        "conversation_id": conversation_id,
        "chatwoot_conversation_id": _conversation_id(payload),
        "chatwoot_message_id": chatwoot_message_id,
        "customer_name": _customer_name(payload),
        "channel": "chatwoot",
        "incoming_message": incoming_message,
        "trace_url": None,
    }
    final_state = graph.invoke(initial_state)
    record = ConversationRecord(
        chatwoot_conversation_id=final_state.get("chatwoot_conversation_id"),
        chatwoot_message_id=final_state.get("chatwoot_message_id"),
        customer_name=str(final_state.get("customer_name", "Chatwoot visitor")),
        channel=str(final_state.get("channel", "chatwoot")),
        incoming_message=incoming_message,
        normalized_message=str(final_state.get("normalized_message", incoming_message)),
        intent=str(final_state.get("intent", "unknown")),
        risk_level=final_state.get("risk_level", "medium"),
        retrieved_knowledge=final_state.get("retrieved_knowledge", []),
        draft_reply=str(final_state.get("draft_reply", "")),
        qa_findings=final_state.get("qa_findings", []),
        compliance_status=final_state.get("compliance_status", "needs_review"),
        approval_status="needs_approval",
        send_status="not_sent",
        trace_url=final_state.get("trace_url"),
        messages=[
            ConversationMessageRecord(
                sender_type="customer",
                body=incoming_message,
                external_message_id=chatwoot_message_id,
                provider="chatwoot",
                payload=payload.model_dump(mode="json", exclude_none=True),
            ),
        ],
    )
    if conversation_id:
        record.id = conversation_id
    saved = store.save(record, context=context)
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


@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    x_sagad_org_id: Annotated[str | None, Header()] = None,
    x_sagad_user_id: Annotated[str | None, Header()] = None,
    x_sagad_role: Annotated[str | None, Header()] = None,
    x_sagad_internal_secret: Annotated[str | None, Header()] = None,
) -> ConversationListResponse:
    _verify_internal_secret(x_sagad_internal_secret)
    context = _trusted_context(x_sagad_org_id, x_sagad_user_id, x_sagad_role)
    return ConversationListResponse(conversations=store.list(context=context))


@app.get("/conversations/{conversation_id}", response_model=ConversationRecord)
def get_conversation(
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
    return record


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
        return saved

    if record.approval_status not in {"needs_approval", "send_failed"}:
        raise HTTPException(status_code=409, detail="Conversation is not waiting for approval.")

    content = request.edited_reply or record.draft_reply
    result = await send_approved_reply(
        settings=get_settings(),
        chatwoot_conversation_id=record.chatwoot_conversation_id,
        content=content,
    )
    record.draft_reply = content
    record.approval_status = "sent" if result["status"] in {"sent", "dry_run"} else "send_failed"
    record.send_status = result["status"]
    if result["status"] in {"sent", "dry_run"}:
        record.messages.append(
            ConversationMessageRecord(
                sender_type="ai_agent",
                body=content,
                provider="sagad",
                payload={
                    "approval": "supervisor_approved",
                    "send_status": result["status"],
                },
            ),
        )
    record.updated_at = datetime.now(timezone.utc)
    saved = store.save(record, context=context)
    store.record_approval(
        saved,
        supervisor_id=request.supervisor_id,
        approved=True,
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
    crm_context, plan, result = await TwentyAdapter(get_settings()).lookup_contact(
        request.query,
        conversation_id=request.conversation_id,
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
    plan, result = await TwentyAdapter(get_settings()).create_note(
        request.contact_id,
        request.note,
        conversation_id=request.conversation_id,
        approved=request.approved,
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
    plan, result = await TwentyAdapter(get_settings()).create_task(
        request.contact_id,
        request.title,
        due_at=request.due_at,
        owner_id=request.owner_id,
        conversation_id=request.conversation_id,
        approved=request.approved,
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
    plan, result = await TwentyAdapter(get_settings()).update_lead_stage(
        request.contact_id,
        request.lead_stage,
        conversation_id=request.conversation_id,
        approved=request.approved,
    )
    store.record_tool_execution(
        plan,
        result,
        conversation_id=request.conversation_id,
        context=context,
    )
    return CrmToolResponse(plan=plan, result=result)
