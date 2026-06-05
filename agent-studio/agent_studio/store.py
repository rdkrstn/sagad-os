from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.schemas import (
    ConversationMessageRecord,
    ConversationRecord,
    CrmContactContext,
    DiagnosticEvent,
    ToolPlan,
    ToolResult,
)


@dataclass(frozen=True)
class StoreContext:
    organization_id: str | None = None
    user_id: str | None = None
    role: str = "system"


DEFAULT_CONTEXT = StoreContext()


class ConversationStoreProtocol(Protocol):
    backend_name: str

    def list(self, context: StoreContext | None = None) -> list[ConversationRecord]:
        ...

    def get(
        self,
        conversation_id: str,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        ...

    def save(
        self,
        record: ConversationRecord,
        context: StoreContext | None = None,
    ) -> ConversationRecord:
        ...

    def record_approval(
        self,
        record: ConversationRecord,
        *,
        supervisor_id: str,
        approved: bool,
        edited_reply: str | None,
        context: StoreContext | None = None,
    ) -> None:
        ...

    def record_tool_execution(
        self,
        plan: ToolPlan,
        result: ToolResult,
        *,
        conversation_id: str | None,
        crm_context: CrmContactContext | None = None,
        context: StoreContext | None = None,
    ) -> None:
        ...

    def record_event(
        self,
        event: DiagnosticEvent,
        context: StoreContext | None = None,
    ) -> DiagnosticEvent:
        ...

    def list_events(
        self,
        *,
        conversation_id: str | None = None,
        limit: int = 100,
        context: StoreContext | None = None,
    ) -> list[DiagnosticEvent]:
        ...

    def clear(self) -> None:
        ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return _now()


def _dump_model(model: BaseModel) -> dict[str, object]:
    return model.model_dump(mode="json")


def _dump_models(models: list[BaseModel]) -> list[dict[str, object]]:
    return [_dump_model(model) for model in models]


def _json_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _json_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _diagnostic_event_from_row(row: Mapping[str, object]) -> DiagnosticEvent:
    payload = _json_dict(row.get("payload"))
    status_value = payload.get("status")
    status = status_value if status_value in {"info", "success", "warning", "error"} else "info"
    summary_value = payload.get("summary")
    summary = str(summary_value) if summary_value else str(row["event_type"])
    return DiagnosticEvent(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]) if row["organization_id"] else None,
        conversation_id=str(row["conversation_id"]) if row["conversation_id"] else None,
        event_type=str(row["event_type"]),
        actor_type=str(row["actor_type"]),
        actor_id=str(row["actor_id"]) if row["actor_id"] else None,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        payload=payload,
        created_at=_coerce_datetime(row["created_at"]),
    )


def _inbound_message_from_record(record: ConversationRecord) -> ConversationMessageRecord:
    return ConversationMessageRecord(
        sender_type="customer",
        body=record.incoming_message,
        external_message_id=record.chatwoot_message_id,
        provider=record.channel,
        payload={
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "customer_name": record.customer_name,
        },
        created_at=record.updated_at,
    )


def _message_merge_key(message: ConversationMessageRecord) -> str:
    if message.external_message_id:
        return f"external:{message.external_message_id}"
    return f"id:{message.id}"


def _merge_messages(
    existing: list[ConversationMessageRecord],
    incoming: list[ConversationMessageRecord],
) -> list[ConversationMessageRecord]:
    merged = list(existing)
    seen = {_message_merge_key(message) for message in merged}
    for message in incoming:
        key = _message_merge_key(message)
        if key in seen:
            continue
        merged.append(message)
        seen.add(key)
    return sorted(merged, key=lambda message: message.created_at)


def _trusted_context(context: StoreContext | None) -> TrustedContext:
    scoped = context or DEFAULT_CONTEXT
    return TrustedContext(
        organization_id=scoped.organization_id,
        user_id=scoped.user_id,
        role=scoped.role,
    )


def _audit_actor_type(role: str) -> str:
    if role in {"owner", "admin", "supervisor", "agent", "qa", "viewer"}:
        return "user"
    return "system"


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


class InMemoryConversationStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._records: dict[str, ConversationRecord] = {}
        self._events: list[DiagnosticEvent] = []

    def list(self, context: StoreContext | None = None) -> list[ConversationRecord]:
        return sorted(
            self._records.values(),
            key=lambda record: record.updated_at,
            reverse=True,
        )

    def get(
        self,
        conversation_id: str,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        return self._records.get(conversation_id)

    def save(
        self,
        record: ConversationRecord,
        context: StoreContext | None = None,
    ) -> ConversationRecord:
        record.updated_at = _now()
        existing = self._records.get(record.id)
        incoming_messages = record.messages or [_inbound_message_from_record(record)]
        if existing is not None:
            record.created_at = existing.created_at
            record.messages = _merge_messages(existing.messages, incoming_messages)
        else:
            record.messages = _merge_messages([], incoming_messages)
        self._records[record.id] = record
        return record

    def record_approval(
        self,
        record: ConversationRecord,
        *,
        supervisor_id: str,
        approved: bool,
        edited_reply: str | None,
        context: StoreContext | None = None,
    ) -> None:
        return None

    def record_tool_execution(
        self,
        plan: ToolPlan,
        result: ToolResult,
        *,
        conversation_id: str | None,
        crm_context: CrmContactContext | None = None,
        context: StoreContext | None = None,
    ) -> None:
        if conversation_id is None:
            return
        record = self._records.get(conversation_id)
        if record is None:
            return
        if all(existing.id != plan.id for existing in record.tool_plans):
            record.tool_plans.append(plan)
        if all(existing.id != result.id for existing in record.tool_results):
            record.tool_results.append(result)
        if crm_context is not None:
            record.crm_context = crm_context
        self.save(record, context=context)

    def record_event(
        self,
        event: DiagnosticEvent,
        context: StoreContext | None = None,
    ) -> DiagnosticEvent:
        scoped = context or DEFAULT_CONTEXT
        if scoped.organization_id and not event.organization_id:
            event.organization_id = scoped.organization_id
        self._events.append(event)
        return event

    def list_events(
        self,
        *,
        conversation_id: str | None = None,
        limit: int = 100,
        context: StoreContext | None = None,
    ) -> list[DiagnosticEvent]:
        events = self._events
        if conversation_id:
            events = [event for event in events if event.conversation_id == conversation_id]
        return sorted(events, key=lambda event: event.created_at, reverse=True)[:limit]

    def clear(self) -> None:
        self._records.clear()
        self._events.clear()


class PostgresConversationStore:
    backend_name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        initialize_database(settings)

    def list(self, context: StoreContext | None = None) -> list[ConversationRecord]:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            rows = connection.execute(
                """
                SELECT
                  conversations.*,
                  COALESCE(
                    (
                      SELECT jsonb_agg(
                        jsonb_build_object(
                          'id', conversation_messages.id::text,
                          'sender_type', conversation_messages.sender_type,
                          'body', conversation_messages.body,
                          'external_message_id', conversation_messages.external_message_id,
                          'provider', conversation_messages.provider,
                          'payload', conversation_messages.payload,
                          'created_at', conversation_messages.created_at
                        )
                        ORDER BY conversation_messages.created_at ASC
                      )
                      FROM conversation_messages
                      WHERE conversation_messages.organization_id = conversations.organization_id
                        AND conversation_messages.conversation_id = conversations.id
                    ),
                    '[]'::jsonb
                  ) AS messages
                FROM conversations
                WHERE organization_id = %s
                ORDER BY updated_at DESC
                """,
                (scoped.organization_id,),
            ).fetchall()
            return [self._record_from_row(row) for row in rows]

    def get(
        self,
        conversation_id: str,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            row = connection.execute(
                """
                SELECT
                  conversations.*,
                  COALESCE(
                    (
                      SELECT jsonb_agg(
                        jsonb_build_object(
                          'id', conversation_messages.id::text,
                          'sender_type', conversation_messages.sender_type,
                          'body', conversation_messages.body,
                          'external_message_id', conversation_messages.external_message_id,
                          'provider', conversation_messages.provider,
                          'payload', conversation_messages.payload,
                          'created_at', conversation_messages.created_at
                        )
                        ORDER BY conversation_messages.created_at ASC
                      )
                      FROM conversation_messages
                      WHERE conversation_messages.organization_id = conversations.organization_id
                        AND conversation_messages.conversation_id = conversations.id
                    ),
                    '[]'::jsonb
                  ) AS messages
                FROM conversations
                WHERE organization_id = %s
                  AND id = %s
                """,
                (scoped.organization_id, conversation_id),
            ).fetchone()
            return self._record_from_row(row) if row is not None else None

    def save(
        self,
        record: ConversationRecord,
        context: StoreContext | None = None,
    ) -> ConversationRecord:
        record.updated_at = _now()
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            existed = self._conversation_exists(
                connection,
                scoped.organization_id,
                record.id,
            )
            if not record.messages:
                record.messages = [_inbound_message_from_record(record)]
            connection.execute(
                """
                INSERT INTO conversations (
                  id,
                  organization_id,
                  chatwoot_conversation_id,
                  chatwoot_message_id,
                  customer_name,
                  channel,
                  incoming_message,
                  normalized_message,
                  intent,
                  risk_level,
                  retrieved_knowledge,
                  crm_context,
                  tool_plans,
                  tool_results,
                  draft_reply,
                  qa_findings,
                  compliance_status,
                  approval_status,
                  send_status,
                  trace_url,
                  created_at,
                  updated_at
                )
                VALUES (
                  %(id)s,
                  %(organization_id)s,
                  %(chatwoot_conversation_id)s,
                  %(chatwoot_message_id)s,
                  %(customer_name)s,
                  %(channel)s,
                  %(incoming_message)s,
                  %(normalized_message)s,
                  %(intent)s,
                  %(risk_level)s,
                  %(retrieved_knowledge)s,
                  %(crm_context)s,
                  %(tool_plans)s,
                  %(tool_results)s,
                  %(draft_reply)s,
                  %(qa_findings)s,
                  %(compliance_status)s,
                  %(approval_status)s,
                  %(send_status)s,
                  %(trace_url)s,
                  %(created_at)s,
                  %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                  chatwoot_conversation_id = EXCLUDED.chatwoot_conversation_id,
                  chatwoot_message_id = EXCLUDED.chatwoot_message_id,
                  customer_name = EXCLUDED.customer_name,
                  channel = EXCLUDED.channel,
                  incoming_message = EXCLUDED.incoming_message,
                  normalized_message = EXCLUDED.normalized_message,
                  intent = EXCLUDED.intent,
                  risk_level = EXCLUDED.risk_level,
                  retrieved_knowledge = EXCLUDED.retrieved_knowledge,
                  crm_context = EXCLUDED.crm_context,
                  tool_plans = EXCLUDED.tool_plans,
                  tool_results = EXCLUDED.tool_results,
                  draft_reply = EXCLUDED.draft_reply,
                  qa_findings = EXCLUDED.qa_findings,
                  compliance_status = EXCLUDED.compliance_status,
                  approval_status = EXCLUDED.approval_status,
                  send_status = EXCLUDED.send_status,
                  trace_url = EXCLUDED.trace_url,
                  updated_at = EXCLUDED.updated_at
                """,
                self._conversation_values(record, scoped.organization_id),
            )
            self._insert_messages(connection, scoped.organization_id, record)
            self._sync_tool_tables(connection, scoped.organization_id, record)
            self._record_audit_event(
                connection,
                organization_id=scoped.organization_id,
                conversation_id=record.id,
                actor_type=_audit_actor_type(scoped.role),
                actor_id=scoped.user_id,
                event_type="conversation.updated" if existed else "conversation.created",
                payload={
                    "approval_status": record.approval_status,
                    "send_status": record.send_status,
                },
            )
            connection.commit()
        return self.get(record.id, context=context) or record

    def record_approval(
        self,
        record: ConversationRecord,
        *,
        supervisor_id: str,
        approved: bool,
        edited_reply: str | None,
        context: StoreContext | None = None,
    ) -> None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            decision = self._approval_decision(record, approved, edited_reply)
            connection.execute(
                """
                INSERT INTO approvals (
                  organization_id,
                  conversation_id,
                  supervisor_id,
                  decision,
                  edited_reply,
                  send_status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    scoped.organization_id,
                    record.id,
                    supervisor_id,
                    decision,
                    edited_reply,
                    record.send_status,
                ),
            )
            self._record_audit_event(
                connection,
                organization_id=scoped.organization_id,
                conversation_id=record.id,
                actor_type="user",
                actor_id=supervisor_id,
                event_type=f"approval.{decision}",
                payload={
                    "approved": approved,
                    "send_status": record.send_status,
                },
            )
            connection.commit()

    def record_tool_execution(
        self,
        plan: ToolPlan,
        result: ToolResult,
        *,
        conversation_id: str | None,
        crm_context: CrmContactContext | None = None,
        context: StoreContext | None = None,
    ) -> None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            scoped_conversation_id = (
                conversation_id
                if self._conversation_exists(
                    connection,
                    scoped.organization_id,
                    conversation_id,
                )
                else None
            )
            self._upsert_tool_plan(
                connection,
                scoped.organization_id,
                scoped_conversation_id,
                plan,
            )
            self._upsert_tool_result(
                connection,
                scoped.organization_id,
                scoped_conversation_id,
                result,
            )
            if scoped_conversation_id is not None:
                self._append_tool_payloads(
                    connection,
                    scoped.organization_id,
                    scoped_conversation_id,
                    plan,
                    result,
                    crm_context,
                )
            self._record_audit_event(
                connection,
                organization_id=scoped.organization_id,
                conversation_id=scoped_conversation_id,
                actor_type=_audit_actor_type(scoped.role),
                actor_id=scoped.user_id,
                event_type="tool.executed",
                payload={
                    "plan_id": plan.id,
                    "result_id": result.id,
                    "tool_name": plan.tool_name,
                    "status": result.status,
                },
            )
            connection.commit()

    def record_event(
        self,
        event: DiagnosticEvent,
        context: StoreContext | None = None,
    ) -> DiagnosticEvent:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            organization_id = event.organization_id or scoped.organization_id
            self._record_audit_event(
                connection,
                organization_id=organization_id,
                conversation_id=event.conversation_id,
                actor_type=event.actor_type,
                actor_id=event.actor_id or scoped.user_id,
                event_type=event.event_type,
                payload={
                    "status": event.status,
                    "summary": event.summary,
                    **event.payload,
                },
            )
            connection.commit()
            event.organization_id = organization_id
        return event

    def list_events(
        self,
        *,
        conversation_id: str | None = None,
        limit: int = 100,
        context: StoreContext | None = None,
    ) -> list[DiagnosticEvent]:
        bounded_limit = max(1, min(limit, 200))
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            if conversation_id:
                rows = connection.execute(
                    """
                    SELECT
                      id::text,
                      organization_id::text,
                      conversation_id,
                      event_type,
                      actor_type,
                      actor_id,
                      payload,
                      created_at
                    FROM audit_events
                    WHERE organization_id = %s
                      AND conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (scoped.organization_id, conversation_id, bounded_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                      id::text,
                      organization_id::text,
                      conversation_id,
                      event_type,
                      actor_type,
                      actor_id,
                      payload,
                      created_at
                    FROM audit_events
                    WHERE organization_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (scoped.organization_id, bounded_limit),
                ).fetchall()
        return [_diagnostic_event_from_row(row) for row in rows]

    def clear(self) -> None:
        with connect(self.settings) as connection:
            connection.execute("TRUNCATE conversation_summaries CASCADE")
            connection.execute("TRUNCATE retrieval_hits CASCADE")
            connection.execute("TRUNCATE retrieval_runs CASCADE")
            connection.execute("TRUNCATE knowledge_chunk_embeddings CASCADE")
            connection.execute("TRUNCATE knowledge_chunks CASCADE")
            connection.execute("TRUNCATE knowledge_documents CASCADE")
            connection.execute("TRUNCATE audit_events CASCADE")
            connection.execute("TRUNCATE tool_results CASCADE")
            connection.execute("TRUNCATE tool_plans CASCADE")
            connection.execute("TRUNCATE approvals CASCADE")
            connection.execute("TRUNCATE conversation_messages CASCADE")
            connection.execute("TRUNCATE conversations CASCADE")
            connection.commit()

    def _record_from_row(self, row: Mapping[str, object]) -> ConversationRecord:
        payload = {
            "id": row["id"],
            "chatwoot_conversation_id": row["chatwoot_conversation_id"],
            "chatwoot_message_id": row["chatwoot_message_id"],
            "customer_name": row["customer_name"],
            "channel": row["channel"],
            "incoming_message": row["incoming_message"],
            "normalized_message": row["normalized_message"],
            "intent": row["intent"],
            "risk_level": row["risk_level"],
            "retrieved_knowledge": _json_list(row["retrieved_knowledge"]),
            "crm_context": row["crm_context"],
            "tool_plans": _json_list(row["tool_plans"]),
            "tool_results": _json_list(row["tool_results"]),
            "draft_reply": row["draft_reply"],
            "qa_findings": _json_list(row["qa_findings"]),
            "compliance_status": row["compliance_status"],
            "approval_status": row["approval_status"],
            "send_status": row["send_status"],
            "trace_url": row["trace_url"],
            "messages": _json_list(row.get("messages")),
            "created_at": _coerce_datetime(row["created_at"]),
            "updated_at": _coerce_datetime(row["updated_at"]),
        }
        return ConversationRecord.model_validate(payload)

    def _conversation_values(
        self,
        record: ConversationRecord,
        organization_id: str | None,
    ) -> dict[str, object]:
        return {
            "id": record.id,
            "organization_id": organization_id,
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "chatwoot_message_id": record.chatwoot_message_id,
            "customer_name": record.customer_name,
            "channel": record.channel,
            "incoming_message": record.incoming_message,
            "normalized_message": record.normalized_message,
            "intent": record.intent,
            "risk_level": record.risk_level,
            "retrieved_knowledge": Jsonb(_dump_models(record.retrieved_knowledge)),
            "crm_context": Jsonb(_dump_model(record.crm_context))
            if record.crm_context
            else None,
            "tool_plans": Jsonb(_dump_models(record.tool_plans)),
            "tool_results": Jsonb(_dump_models(record.tool_results)),
            "draft_reply": record.draft_reply,
            "qa_findings": Jsonb(_dump_models(record.qa_findings)),
            "compliance_status": record.compliance_status,
            "approval_status": record.approval_status,
            "send_status": record.send_status,
            "trace_url": record.trace_url,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def _conversation_exists(
        self,
        connection: object,
        organization_id: str | None,
        conversation_id: str | None,
    ) -> bool:
        if conversation_id is None:
            return False
        row = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE organization_id = %s
              AND id = %s
            """,
            (organization_id, conversation_id),
        ).fetchone()
        return row is not None

    def _insert_messages(
        self,
        connection: object,
        organization_id: str | None,
        record: ConversationRecord,
    ) -> None:
        for message in record.messages:
            if _is_uuid(message.id):
                connection.execute(
                    """
                    INSERT INTO conversation_messages (
                      id,
                      organization_id,
                      conversation_id,
                      sender_type,
                      body,
                      external_message_id,
                      provider,
                      payload,
                      created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        message.id,
                        organization_id,
                        record.id,
                        message.sender_type,
                        message.body,
                        message.external_message_id,
                        message.provider,
                        Jsonb(message.payload),
                        message.created_at,
                    ),
                )
                continue
            connection.execute(
                """
                INSERT INTO conversation_messages (
                  organization_id,
                  conversation_id,
                  sender_type,
                  body,
                  external_message_id,
                  provider,
                  payload,
                  created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    organization_id,
                    record.id,
                    message.sender_type,
                    message.body,
                    message.external_message_id,
                    message.provider,
                    Jsonb(message.payload),
                    message.created_at,
                ),
            )

    def _sync_tool_tables(
        self,
        connection: object,
        organization_id: str | None,
        record: ConversationRecord,
    ) -> None:
        for plan in record.tool_plans:
            self._upsert_tool_plan(connection, organization_id, record.id, plan)
        for result in record.tool_results:
            self._upsert_tool_result(connection, organization_id, record.id, result)

    def _upsert_tool_plan(
        self,
        connection: object,
        organization_id: str | None,
        conversation_id: str | None,
        plan: ToolPlan,
    ) -> None:
        connection.execute(
            """
            INSERT INTO tool_plans (
              id,
              organization_id,
              conversation_id,
              provider,
              tool_name,
              action,
              risk_level,
              requires_approval,
              approved,
              dry_run,
              args
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              conversation_id = EXCLUDED.conversation_id,
              provider = EXCLUDED.provider,
              tool_name = EXCLUDED.tool_name,
              action = EXCLUDED.action,
              risk_level = EXCLUDED.risk_level,
              requires_approval = EXCLUDED.requires_approval,
              approved = EXCLUDED.approved,
              dry_run = EXCLUDED.dry_run,
              args = EXCLUDED.args
            """,
            (
                plan.id,
                organization_id,
                conversation_id,
                plan.provider,
                plan.tool_name,
                plan.action,
                plan.risk_level,
                plan.requires_approval,
                plan.approved,
                plan.dry_run,
                Jsonb(plan.args),
            ),
        )

    def _upsert_tool_result(
        self,
        connection: object,
        organization_id: str | None,
        conversation_id: str | None,
        result: ToolResult,
    ) -> None:
        connection.execute(
            """
            INSERT INTO tool_results (
              id,
              organization_id,
              conversation_id,
              plan_id,
              provider,
              tool_name,
              status,
              detail,
              external_id,
              data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              conversation_id = EXCLUDED.conversation_id,
              plan_id = EXCLUDED.plan_id,
              provider = EXCLUDED.provider,
              tool_name = EXCLUDED.tool_name,
              status = EXCLUDED.status,
              detail = EXCLUDED.detail,
              external_id = EXCLUDED.external_id,
              data = EXCLUDED.data
            """,
            (
                result.id,
                organization_id,
                conversation_id,
                result.plan_id,
                result.provider,
                result.tool_name,
                result.status,
                result.detail,
                result.external_id,
                Jsonb(result.data),
            ),
        )

    def _append_tool_payloads(
        self,
        connection: object,
        organization_id: str | None,
        conversation_id: str,
        plan: ToolPlan,
        result: ToolResult,
        crm_context: CrmContactContext | None,
    ) -> None:
        record = connection.execute(
            """
            SELECT tool_plans, tool_results
            FROM conversations
            WHERE organization_id = %s
              AND id = %s
            """,
            (organization_id, conversation_id),
        ).fetchone()
        if record is None:
            return
        plan_payloads = _json_list(record["tool_plans"])
        result_payloads = _json_list(record["tool_results"])
        plan_dict = _dump_model(plan)
        result_dict = _dump_model(result)
        if all(not isinstance(item, dict) or item.get("id") != plan.id for item in plan_payloads):
            plan_payloads.append(plan_dict)
        if all(
            not isinstance(item, dict) or item.get("id") != result.id
            for item in result_payloads
        ):
            result_payloads.append(result_dict)
        crm_payload = Jsonb(_dump_model(crm_context)) if crm_context else None
        if crm_context:
            connection.execute(
                """
                UPDATE conversations
                SET tool_plans = %s,
                    tool_results = %s,
                    crm_context = %s,
                    updated_at = now()
                WHERE organization_id = %s
                  AND id = %s
                """,
                (
                    Jsonb(plan_payloads),
                    Jsonb(result_payloads),
                    crm_payload,
                    organization_id,
                    conversation_id,
                ),
            )
            return
        connection.execute(
            """
            UPDATE conversations
            SET tool_plans = %s,
                tool_results = %s,
                updated_at = now()
            WHERE organization_id = %s
              AND id = %s
            """,
            (
                Jsonb(plan_payloads),
                Jsonb(result_payloads),
                organization_id,
                conversation_id,
            ),
        )

    def _record_audit_event(
        self,
        connection: object,
        *,
        organization_id: str | None,
        conversation_id: str | None,
        actor_type: str,
        actor_id: str | None,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events (
              organization_id,
              conversation_id,
              event_type,
              actor_type,
              actor_id,
              payload
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                organization_id,
                conversation_id,
                event_type,
                actor_type,
                actor_id,
                Jsonb(payload),
            ),
        )

    def _approval_decision(
        self,
        record: ConversationRecord,
        approved: bool,
        edited_reply: str | None,
    ) -> str:
        if not approved:
            return "rejected"
        if record.send_status == "sent":
            return "sent"
        if record.send_status not in {"not_sent", "dry_run"}:
            return "send_failed"
        if edited_reply:
            return "edited"
        return "approved"


def build_store(settings: Settings | None = None) -> ConversationStoreProtocol:
    scoped_settings = settings or get_settings()
    if database_configured(scoped_settings):
        return PostgresConversationStore(scoped_settings)
    return InMemoryConversationStore()


class StoreProxy:
    backend_name = "proxy"

    def __init__(self) -> None:
        self._store: ConversationStoreProtocol | None = None
        self._database_url: str | None = None

    def _current(self) -> ConversationStoreProtocol:
        settings = get_settings()
        database_url = settings.database_url.strip() if settings.database_url else None
        if self._store is None or self._database_url != database_url:
            self._store = build_store(settings)
            self._database_url = database_url
        return self._store

    def list(self, context: StoreContext | None = None) -> list[ConversationRecord]:
        return self._current().list(context=context)

    def get(
        self,
        conversation_id: str,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        return self._current().get(conversation_id, context=context)

    def save(
        self,
        record: ConversationRecord,
        context: StoreContext | None = None,
    ) -> ConversationRecord:
        return self._current().save(record, context=context)

    def record_approval(
        self,
        record: ConversationRecord,
        *,
        supervisor_id: str,
        approved: bool,
        edited_reply: str | None,
        context: StoreContext | None = None,
    ) -> None:
        return self._current().record_approval(
            record,
            supervisor_id=supervisor_id,
            approved=approved,
            edited_reply=edited_reply,
            context=context,
        )

    def record_tool_execution(
        self,
        plan: ToolPlan,
        result: ToolResult,
        *,
        conversation_id: str | None,
        crm_context: CrmContactContext | None = None,
        context: StoreContext | None = None,
    ) -> None:
        return self._current().record_tool_execution(
            plan,
            result,
            conversation_id=conversation_id,
            crm_context=crm_context,
            context=context,
        )

    def record_event(
        self,
        event: DiagnosticEvent,
        context: StoreContext | None = None,
    ) -> DiagnosticEvent:
        return self._current().record_event(event, context=context)

    def list_events(
        self,
        *,
        conversation_id: str | None = None,
        limit: int = 100,
        context: StoreContext | None = None,
    ) -> list[DiagnosticEvent]:
        return self._current().list_events(
            conversation_id=conversation_id,
            limit=limit,
            context=context,
        )

    def clear(self) -> None:
        return self._current().clear()


ConversationStore = InMemoryConversationStore
store = StoreProxy()
