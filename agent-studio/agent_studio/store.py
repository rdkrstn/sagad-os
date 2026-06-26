from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database,
    initialize_database_safe,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.embeddings import EmbeddingService, content_hash, tokenize, vector_literal
from agent_studio.schemas import (
    ConversationMessageRecord,
    ConversationRecord,
    CrmContactContext,
    DiagnosticEvent,
    IntegrationSyncState,
    MemoryHit,
    QaFinding,
    ToolPlan,
    ToolResult,
)


@dataclass(frozen=True)
class StoreContext:
    organization_id: str | None = None
    user_id: str | None = None
    role: str = "system"


DEFAULT_CONTEXT = StoreContext()
QUALITY_FIELD_NAMES = (
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
    "quality_evaluated_at",
)
EVAL_RUN_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}
EVAL_RESULT_STATUSES = {"passed", "failed", "errored", "skipped"}


class ConversationStoreProtocol(Protocol):
    backend_name: str

    def list(
        self,
        context: StoreContext | None = None,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
    ) -> list[ConversationRecord]:
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

    def update_ticket(
        self,
        conversation_id: str,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        pipeline_stage: str | None = None,
        sla_due_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
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

    def update_conversation_quality(
        self,
        conversation_id: str,
        *,
        eval_tags: list[str] | None = None,
        trace_attributes: Mapping[str, object] | None = None,
        diagnostic_payload: Mapping[str, object] | None = None,
        decision_reason: str | None = None,
        guardrail_findings: Sequence[object] | None = None,
        confidence_breakdown: Mapping[str, object] | None = None,
        final_confidence_score: float | None = None,
        quality_score: float | None = None,
        quality_label: str | None = None,
        quality_signals: Mapping[str, object] | None = None,
        quality_notes: str | None = None,
        quality_evaluated_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        ...

    def record_eval_run(
        self,
        run: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        ...

    def record_eval_result(
        self,
        result: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        ...

    def list_eval_runs(
        self,
        *,
        limit: int = 50,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        ...

    def list_eval_results(
        self,
        eval_run_id: str,
        *,
        limit: int = 200,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        ...

    def append_memory_items(
        self,
        conversation_id: str,
        items: list[MemoryHit],
        context: StoreContext | None = None,
    ) -> None:
        ...

    def list_memory_items(
        self,
        conversation_id: str,
        *,
        query: str | None = None,
        limit: int = 8,
        context: StoreContext | None = None,
    ) -> list[MemoryHit]:
        ...

    def list_events(
        self,
        *,
        conversation_id: str | None = None,
        limit: int = 100,
        context: StoreContext | None = None,
    ) -> list[DiagnosticEvent]:
        ...

    def get_sync_state(
        self,
        provider: str,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState | None:
        ...

    def save_sync_state(
        self,
        state: IntegrationSyncState,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState:
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
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _coerce_datetime(value)


def _coerce_status(value: object, allowed: set[str], default: str) -> str:
    status = str(value) if value else default
    return status if status in allowed else default


def _set_model_field(model: BaseModel, field_name: str, value: object) -> None:
    if field_name == "guardrail_findings":
        value = [
            item if isinstance(item, QaFinding) else QaFinding.model_validate(item)
            for item in _json_list(value)
        ]
    if field_name in type(model).model_fields:
        setattr(model, field_name, value)
        return
    object.__setattr__(model, field_name, value)


def _attach_quality_fields(
    record: ConversationRecord,
    values: Mapping[str, object],
) -> ConversationRecord:
    for field_name in QUALITY_FIELD_NAMES:
        if field_name in values:
            _set_model_field(record, field_name, values[field_name])
    return record


def _quality_values(
    *,
    eval_tags: list[str] | None = None,
    trace_attributes: Mapping[str, object] | None = None,
    diagnostic_payload: Mapping[str, object] | None = None,
    decision_reason: str | None = None,
    guardrail_findings: Sequence[object] | None = None,
    confidence_breakdown: Mapping[str, object] | None = None,
    final_confidence_score: float | None = None,
    quality_score: float | None = None,
    quality_label: str | None = None,
    quality_signals: Mapping[str, object] | None = None,
    quality_notes: str | None = None,
    quality_evaluated_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "eval_tags": list(eval_tags or []),
        "trace_attributes": dict(trace_attributes or {}),
        "diagnostic_payload": dict(diagnostic_payload or {}),
        "decision_reason": decision_reason,
        "guardrail_findings": _dump_mixed_models(list(guardrail_findings or [])),
        "confidence_breakdown": dict(confidence_breakdown or {}),
        "final_confidence_score": _coerce_optional_float(final_confidence_score),
        "quality_score": _coerce_optional_float(quality_score),
        "quality_label": quality_label,
        "quality_signals": dict(quality_signals or {}),
        "quality_notes": quality_notes,
        "quality_evaluated_at": quality_evaluated_at or _now(),
    }


def _record_quality_values(record: ConversationRecord) -> dict[str, object]:
    return {
        "eval_tags": list(getattr(record, "eval_tags", [])),
        "trace_attributes": _json_dict(getattr(record, "trace_attributes", None)),
        "diagnostic_payload": _json_dict(getattr(record, "diagnostic_payload", None)),
        "decision_reason": getattr(record, "decision_reason", None),
        "guardrail_findings": _dump_mixed_models(
            getattr(record, "guardrail_findings", []),
        ),
        "confidence_breakdown": _json_dict(getattr(record, "confidence_breakdown", None)),
        "final_confidence_score": _coerce_optional_float(
            getattr(record, "final_confidence_score", None),
        ),
        "quality_score": _coerce_optional_float(getattr(record, "quality_score", None)),
        "quality_label": getattr(record, "quality_label", None),
        "quality_signals": _json_dict(getattr(record, "quality_signals", None)),
        "quality_notes": getattr(record, "quality_notes", None),
        "quality_evaluated_at": getattr(record, "quality_evaluated_at", None),
    }


def _dump_mixed_models(values: Sequence[object]) -> list[dict[str, object]]:
    dumped: list[dict[str, object]] = []
    for value in values:
        if isinstance(value, BaseModel):
            dumped.append(_dump_model(value))
        elif isinstance(value, Mapping):
            dumped.append(dict(value))
    return dumped


def _normalize_eval_run(
    run: Mapping[str, object],
    *,
    organization_id: str | None = None,
    existing: Mapping[str, object] | None = None,
) -> dict[str, object]:
    existing = existing or {}
    now = _now()
    run_id = str(
        run.get("id")
        or run.get("run_id")
        or existing.get("id")
        or f"evalrun_{uuid4().hex[:12]}"
    )
    suite_name = str(run.get("suite_name") or existing.get("suite_name") or "default")
    name = str(run.get("name") or existing.get("name") or suite_name)
    default_status = "running"
    if run.get("passed") is True:
        default_status = "completed"
    elif run.get("passed") is False:
        default_status = "failed"
    return {
        "id": run_id,
        "organization_id": organization_id or existing.get("organization_id"),
        "name": name,
        "suite_name": suite_name,
        "status": _coerce_status(
            run.get("status", existing.get("status")),
            EVAL_RUN_STATUSES,
            default_status,
        ),
        "started_at": _coerce_datetime(
            run.get("started_at", existing.get("started_at", now)),
        ),
        "completed_at": _coerce_optional_datetime(
            run.get("completed_at", existing.get("completed_at")),
        ),
        "total_cases": _coerce_int(
            run.get("total_cases", run.get("case_count", existing.get("total_cases"))),
            0,
        ),
        "passed_cases": _coerce_int(
            run.get(
                "passed_cases",
                run.get("passed_case_count", existing.get("passed_cases")),
            ),
            0,
        ),
        "failed_cases": _coerce_int(
            run.get(
                "failed_cases",
                run.get("failed_case_count", existing.get("failed_cases")),
            ),
            0,
        ),
        "average_score": _coerce_optional_float(
            run.get("average_score", run.get("overall_score", existing.get("average_score"))),
        ),
        "metadata": _json_dict(run.get("metadata", existing.get("metadata"))),
        "trace_url": run.get("trace_url", existing.get("trace_url")),
        "created_at": _coerce_datetime(existing.get("created_at", now)),
        "updated_at": now,
    }


def _normalize_eval_result(
    result: Mapping[str, object],
    *,
    organization_id: str | None = None,
    existing: Mapping[str, object] | None = None,
) -> dict[str, object]:
    existing = existing or {}
    eval_run_id = result.get("eval_run_id") or existing.get("eval_run_id")
    if not eval_run_id:
        raise ValueError("eval_run_id is required to record an eval result.")
    now = _now()
    default_status = "passed"
    if result.get("passed") is False:
        default_status = "failed"
    elif result.get("passed") is True:
        default_status = "passed"
    metrics = result.get("metrics", existing.get("metrics"))
    if metrics is None and "scores" in result:
        metrics = {"scores": result["scores"]}
    return {
        "id": str(result.get("id") or existing.get("id") or f"evalresult_{uuid4().hex[:12]}"),
        "organization_id": organization_id or existing.get("organization_id"),
        "eval_run_id": str(eval_run_id),
        "conversation_id": result.get("conversation_id", existing.get("conversation_id")),
        "case_name": str(
            result.get("case_name")
            or result.get("name")
            or result.get("case_id")
            or existing.get("case_name")
            or "unnamed_case"
        ),
        "status": _coerce_status(
            result.get("status", existing.get("status")),
            EVAL_RESULT_STATUSES,
            default_status,
        ),
        "score": _coerce_optional_float(result.get("score", existing.get("score"))),
        "input": _json_dict(result.get("input", existing.get("input"))),
        "expected": _json_dict(result.get("expected", existing.get("expected"))),
        "actual": _json_dict(result.get("actual", existing.get("actual"))),
        "metrics": _json_dict(metrics),
        "failure_reason": result.get("failure_reason", existing.get("failure_reason")),
        "trace_url": result.get("trace_url", existing.get("trace_url")),
        "created_at": _coerce_datetime(existing.get("created_at", now)),
    }


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
    provider = "chatwoot" if record.chatwoot_conversation_id else record.channel
    return ConversationMessageRecord(
        sender_type="customer",
        body=record.incoming_message,
        external_message_id=record.chatwoot_message_id,
        provider=provider,
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


def _memory_overlap_score(query: str | None, content: str) -> float:
    if not query:
        return 0.0
    query_tokens = tokenize(query)
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return min(0.4, overlap / max(len(query_tokens), 1))


def _memory_sort_key(query: str | None, hit: MemoryHit) -> tuple[float, datetime]:
    return (hit.score + _memory_overlap_score(query, hit.content), hit.created_at)


def _memory_from_row(row: Mapping[str, object]) -> MemoryHit:
    score_value = row.get("rank_score", row.get("score", 0))
    return MemoryHit(
        id=str(row["id"]),
        memory_type=str(row["memory_type"]),
        content=str(row["content"]),
        source=str(row["source"]),
        score=float(score_value or 0),
        conversation_id=str(row["conversation_id"]) if row["conversation_id"] else None,
        chatwoot_conversation_id=str(row["chatwoot_conversation_id"])
        if row["chatwoot_conversation_id"]
        else None,
        source_message_id=str(row["source_message_id"]) if row["source_message_id"] else None,
        metadata=_json_dict(row.get("metadata")),
        created_at=_coerce_datetime(row["created_at"]),
    )


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
        self._memory: dict[str, list[MemoryHit]] = {}
        self._eval_runs: dict[str, dict[str, object]] = {}
        self._eval_results: dict[str, dict[str, dict[str, object]]] = {}
        # Per-(organization_id, provider) poller watermark rows (integration_sync_state).
        self._sync_state: dict[tuple[str | None, str], IntegrationSyncState] = {}

    def list(
        self,
        context: StoreContext | None = None,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
    ) -> list[ConversationRecord]:
        records = list(self._records.values())
        if ticket_status:
            records = [r for r in records if r.ticket_status == ticket_status]
        if assignee:
            records = [r for r in records if r.assignee == assignee]
        if priority:
            records = [r for r in records if r.priority == priority]
        return sorted(records, key=lambda record: record.updated_at, reverse=True)

    def update_ticket(
        self,
        conversation_id: str,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        pipeline_stage: str | None = None,
        sla_due_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        record = self._records.get(conversation_id)
        if record is None:
            return None
        if ticket_status is not None:
            record.ticket_status = ticket_status  # type: ignore[assignment]
        if assignee is not None:
            record.assignee = assignee
        if priority is not None:
            record.priority = priority  # type: ignore[assignment]
        if pipeline_stage is not None:
            record.pipeline_stage = pipeline_stage
        if sla_due_at is not None:
            record.sla_due_at = sla_due_at
        record.updated_at = _now()
        self._records[conversation_id] = record
        return record

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
            # Preserve RevOps ticket fields across inbound re-saves. The inbound pipeline never
            # manages tickets (only the PATCH endpoint does, via update_ticket), so a fresh
            # record with default ticket fields must not overwrite a supervisor's assignment.
            # Mirrors the Postgres store, where ticket columns are absent from ON CONFLICT DO UPDATE.
            record.ticket_status = existing.ticket_status
            record.assignee = existing.assignee
            record.priority = existing.priority
            record.pipeline_stage = existing.pipeline_stage
            record.sla_due_at = existing.sla_due_at
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

    def update_conversation_quality(
        self,
        conversation_id: str,
        *,
        eval_tags: list[str] | None = None,
        trace_attributes: Mapping[str, object] | None = None,
        diagnostic_payload: Mapping[str, object] | None = None,
        decision_reason: str | None = None,
        guardrail_findings: Sequence[object] | None = None,
        confidence_breakdown: Mapping[str, object] | None = None,
        final_confidence_score: float | None = None,
        quality_score: float | None = None,
        quality_label: str | None = None,
        quality_signals: Mapping[str, object] | None = None,
        quality_notes: str | None = None,
        quality_evaluated_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        record = self._records.get(conversation_id)
        if record is None:
            return None
        values = _quality_values(
            eval_tags=eval_tags,
            trace_attributes=trace_attributes,
            diagnostic_payload=diagnostic_payload,
            decision_reason=decision_reason,
            guardrail_findings=guardrail_findings,
            confidence_breakdown=confidence_breakdown,
            final_confidence_score=final_confidence_score,
            quality_score=quality_score,
            quality_label=quality_label,
            quality_signals=quality_signals,
            quality_notes=quality_notes,
            quality_evaluated_at=quality_evaluated_at,
        )
        _attach_quality_fields(record, values)
        record.updated_at = _now()
        self._records[conversation_id] = record
        return record

    def record_eval_run(
        self,
        run: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        scoped = context or DEFAULT_CONTEXT
        run_id = str(run.get("id") or run.get("run_id") or f"evalrun_{uuid4().hex[:12]}")
        saved = _normalize_eval_run(
            {**run, "id": run_id},
            organization_id=scoped.organization_id,
            existing=self._eval_runs.get(run_id),
        )
        self._eval_runs[run_id] = saved
        return dict(saved)

    def record_eval_result(
        self,
        result: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        scoped = context or DEFAULT_CONTEXT
        result_id = str(result.get("id") or f"evalresult_{uuid4().hex[:12]}")
        existing = next(
            (
                bucket[result_id]
                for bucket in self._eval_results.values()
                if result_id in bucket
            ),
            None,
        )
        saved = _normalize_eval_result(
            {**result, "id": result_id},
            organization_id=scoped.organization_id,
            existing=existing,
        )
        result_bucket = self._eval_results.setdefault(str(saved["eval_run_id"]), {})
        result_bucket[result_id] = saved
        return dict(saved)

    def list_eval_runs(
        self,
        *,
        limit: int = 50,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        scoped = context or DEFAULT_CONTEXT
        runs = list(self._eval_runs.values())
        if scoped.organization_id:
            runs = [
                run
                for run in runs
                if run.get("organization_id") in {None, scoped.organization_id}
            ]
        runs.sort(key=lambda run: _coerce_datetime(run["started_at"]), reverse=True)
        return [dict(run) for run in runs[: max(limit, 0)]]

    def list_eval_results(
        self,
        eval_run_id: str,
        *,
        limit: int = 200,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        scoped = context or DEFAULT_CONTEXT
        results = list(self._eval_results.get(eval_run_id, {}).values())
        if scoped.organization_id:
            results = [
                result
                for result in results
                if result.get("organization_id") in {None, scoped.organization_id}
            ]
        results.sort(key=lambda result: _coerce_datetime(result["created_at"]))
        return [dict(result) for result in results[: max(limit, 0)]]

    def append_memory_items(
        self,
        conversation_id: str,
        items: list[MemoryHit],
        context: StoreContext | None = None,
    ) -> None:
        if not items:
            return
        record = self._records.get(conversation_id)
        existing = self._memory.setdefault(conversation_id, [])
        seen = {
            (item.memory_type, content_hash(item.content))
            for item in existing
        }
        for item in items:
            key = (item.memory_type, content_hash(item.content))
            if key in seen:
                continue
            saved = item.model_copy(
                update={
                    "conversation_id": conversation_id,
                    "chatwoot_conversation_id": item.chatwoot_conversation_id
                    or (record.chatwoot_conversation_id if record else None),
                    "created_at": item.created_at or _now(),
                },
            )
            existing.append(saved)
            seen.add(key)
        if record is not None:
            record.memory_context = self.list_memory_items(
                conversation_id,
                query=record.incoming_message,
                context=context,
            )
            record.memory_diagnostic = {
                "workflow": "store_memory",
                "memory_available": bool(record.memory_context),
                "selected_count": len(record.memory_context),
            }
            self._records[conversation_id] = record

    def list_memory_items(
        self,
        conversation_id: str,
        *,
        query: str | None = None,
        limit: int = 8,
        context: StoreContext | None = None,
    ) -> list[MemoryHit]:
        hits = list(self._memory.get(conversation_id, []))
        hits.sort(key=lambda item: _memory_sort_key(query, item), reverse=True)
        ranked = []
        for hit in hits[: max(limit, 0)]:
            ranked.append(
                hit.model_copy(
                    update={
                        "score": min(1.0, hit.score + _memory_overlap_score(query, hit.content)),
                    },
                ),
            )
        return ranked

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

    def get_sync_state(
        self,
        provider: str,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState | None:
        scoped = context or DEFAULT_CONTEXT
        return self._sync_state.get((scoped.organization_id, provider))

    def save_sync_state(
        self,
        state: IntegrationSyncState,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState:
        scoped = context or DEFAULT_CONTEXT
        state.organization_id = scoped.organization_id
        state.updated_at = _now()
        self._sync_state[(scoped.organization_id, state.provider)] = state
        return state

    def clear(self) -> None:
        self._records.clear()
        self._events.clear()
        self._memory.clear()
        self._eval_runs.clear()
        self._eval_results.clear()
        self._sync_state.clear()


class PostgresConversationStore:
    backend_name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedding_service = EmbeddingService(settings)
        # Non-fatal: a slow/unreachable DB at construction must not kill the process.
        initialize_database_safe(settings)

    def list(
        self,
        context: StoreContext | None = None,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
    ) -> list[ConversationRecord]:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            where = ["organization_id = %s"]
            params: list[object] = [scoped.organization_id]
            if ticket_status:
                where.append("ticket_status = %s")
                params.append(ticket_status)
            if assignee:
                where.append("assignee = %s")
                params.append(assignee)
            if priority:
                where.append("priority = %s")
                params.append(priority)
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
                WHERE """ + " AND ".join(where) + """
                ORDER BY updated_at DESC
                """,
                tuple(params),
            ).fetchall()
            return [self._record_from_row(row) for row in rows]

    def update_ticket(
        self,
        conversation_id: str,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        pipeline_stage: str | None = None,
        sla_due_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        sets: list[str] = []
        params: list[object] = []
        if ticket_status is not None:
            sets.append("ticket_status = %s")
            params.append(ticket_status)
        if assignee is not None:
            sets.append("assignee = %s")
            params.append(assignee)
        if priority is not None:
            sets.append("priority = %s")
            params.append(priority)
        if pipeline_stage is not None:
            sets.append("pipeline_stage = %s")
            params.append(pipeline_stage)
        if sla_due_at is not None:
            sets.append("sla_due_at = %s")
            params.append(sla_due_at)
        if not sets:
            return self.get(conversation_id, context=context)
        sets.append("updated_at = now()")
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            cursor = connection.execute(
                "UPDATE conversations SET " + ", ".join(sets) + """
                WHERE organization_id = %s AND id = %s
                """,
                (*params, scoped.organization_id, conversation_id),
            )
            if cursor.rowcount:
                self._record_audit_event(
                    connection,
                    organization_id=scoped.organization_id,
                    conversation_id=conversation_id,
                    actor_type=_audit_actor_type(scoped.role),
                    actor_id=scoped.user_id,
                    event_type="ticket.updated",
                    payload={
                        "ticket_status": ticket_status,
                        "assignee": assignee,
                        "priority": priority,
                        "pipeline_stage": pipeline_stage,
                    },
                )
            connection.commit()
        return self.get(conversation_id, context=context)

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
                  provider_conversation_id,
                  customer_name,
                  channel,
                  incoming_message,
                  normalized_message,
                  intent,
                  risk_level,
                  selected_agent,
                  customer_driver,
                  retrieved_knowledge,
                  retrieval_confidence,
                  missing_knowledge,
                  retrieval_diagnostic,
                  crm_context,
                  chatwoot_context,
                  tool_plans,
                  tool_results,
                  draft_reply,
                  qa_findings,
                  compliance_status,
                  approval_status,
                  send_status,
                  ticket_status,
                  assignee,
                  priority,
                  pipeline_stage,
                  sla_due_at,
                  trace_url,
                  eval_tags,
                  trace_attributes,
                  diagnostic_payload,
                  decision_reason,
                  guardrail_findings,
                  confidence_breakdown,
                  final_confidence_score,
                  quality_score,
                  quality_label,
                  quality_signals,
                  quality_notes,
                  quality_evaluated_at,
                  created_at,
                  updated_at
                )
                VALUES (
                  %(id)s,
                  %(organization_id)s,
                  %(chatwoot_conversation_id)s,
                  %(chatwoot_message_id)s,
                  %(provider_conversation_id)s,
                  %(customer_name)s,
                  %(channel)s,
                  %(incoming_message)s,
                  %(normalized_message)s,
                  %(intent)s,
                  %(risk_level)s,
                  %(selected_agent)s,
                  %(customer_driver)s,
                  %(retrieved_knowledge)s,
                  %(retrieval_confidence)s,
                  %(missing_knowledge)s,
                  %(retrieval_diagnostic)s,
                  %(crm_context)s,
                  %(chatwoot_context)s,
                  %(tool_plans)s,
                  %(tool_results)s,
                  %(draft_reply)s,
                  %(qa_findings)s,
                  %(compliance_status)s,
                  %(approval_status)s,
                  %(send_status)s,
                  %(ticket_status)s,
                  %(assignee)s,
                  %(priority)s,
                  %(pipeline_stage)s,
                  %(sla_due_at)s,
                  %(trace_url)s,
                  %(eval_tags)s,
                  %(trace_attributes)s,
                  %(diagnostic_payload)s,
                  %(decision_reason)s,
                  %(guardrail_findings)s,
                  %(confidence_breakdown)s,
                  %(final_confidence_score)s,
                  %(quality_score)s,
                  %(quality_label)s,
                  %(quality_signals)s,
                  %(quality_notes)s,
                  %(quality_evaluated_at)s,
                  %(created_at)s,
                  %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                  chatwoot_conversation_id = EXCLUDED.chatwoot_conversation_id,
                  chatwoot_message_id = EXCLUDED.chatwoot_message_id,
                  provider_conversation_id = EXCLUDED.provider_conversation_id,
                  customer_name = EXCLUDED.customer_name,
                  channel = EXCLUDED.channel,
                  incoming_message = EXCLUDED.incoming_message,
                  normalized_message = EXCLUDED.normalized_message,
                  intent = EXCLUDED.intent,
                  risk_level = EXCLUDED.risk_level,
                  selected_agent = EXCLUDED.selected_agent,
                  customer_driver = EXCLUDED.customer_driver,
                  retrieved_knowledge = EXCLUDED.retrieved_knowledge,
                  retrieval_confidence = EXCLUDED.retrieval_confidence,
                  missing_knowledge = EXCLUDED.missing_knowledge,
                  retrieval_diagnostic = EXCLUDED.retrieval_diagnostic,
                  crm_context = EXCLUDED.crm_context,
                  chatwoot_context = EXCLUDED.chatwoot_context,
                  tool_plans = EXCLUDED.tool_plans,
                  tool_results = EXCLUDED.tool_results,
                  draft_reply = EXCLUDED.draft_reply,
                  qa_findings = EXCLUDED.qa_findings,
                  compliance_status = EXCLUDED.compliance_status,
                  approval_status = EXCLUDED.approval_status,
                  send_status = EXCLUDED.send_status,
                  trace_url = EXCLUDED.trace_url,
                  eval_tags = EXCLUDED.eval_tags,
                  trace_attributes = EXCLUDED.trace_attributes,
                  diagnostic_payload = EXCLUDED.diagnostic_payload,
                  decision_reason = EXCLUDED.decision_reason,
                  guardrail_findings = EXCLUDED.guardrail_findings,
                  confidence_breakdown = EXCLUDED.confidence_breakdown,
                  final_confidence_score = EXCLUDED.final_confidence_score,
                  quality_score = EXCLUDED.quality_score,
                  quality_label = EXCLUDED.quality_label,
                  quality_signals = EXCLUDED.quality_signals,
                  quality_notes = EXCLUDED.quality_notes,
                  quality_evaluated_at = EXCLUDED.quality_evaluated_at,
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

    def update_conversation_quality(
        self,
        conversation_id: str,
        *,
        eval_tags: list[str] | None = None,
        trace_attributes: Mapping[str, object] | None = None,
        diagnostic_payload: Mapping[str, object] | None = None,
        decision_reason: str | None = None,
        guardrail_findings: Sequence[object] | None = None,
        confidence_breakdown: Mapping[str, object] | None = None,
        final_confidence_score: float | None = None,
        quality_score: float | None = None,
        quality_label: str | None = None,
        quality_signals: Mapping[str, object] | None = None,
        quality_notes: str | None = None,
        quality_evaluated_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        values = _quality_values(
            eval_tags=eval_tags,
            trace_attributes=trace_attributes,
            diagnostic_payload=diagnostic_payload,
            decision_reason=decision_reason,
            guardrail_findings=guardrail_findings,
            confidence_breakdown=confidence_breakdown,
            final_confidence_score=final_confidence_score,
            quality_score=quality_score,
            quality_label=quality_label,
            quality_signals=quality_signals,
            quality_notes=quality_notes,
            quality_evaluated_at=quality_evaluated_at,
        )
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            cursor = connection.execute(
                """
                UPDATE conversations
                SET eval_tags = %s,
                    trace_attributes = %s,
                    diagnostic_payload = %s,
                    decision_reason = %s,
                    guardrail_findings = %s,
                    confidence_breakdown = %s,
                    final_confidence_score = %s,
                    quality_score = %s,
                    quality_label = %s,
                    quality_signals = %s,
                    quality_notes = %s,
                    quality_evaluated_at = %s,
                    updated_at = now()
                WHERE organization_id = %s
                  AND id = %s
                """,
                (
                    Jsonb(values["eval_tags"]),
                    Jsonb(values["trace_attributes"]),
                    Jsonb(values["diagnostic_payload"]),
                    values["decision_reason"],
                    Jsonb(values["guardrail_findings"]),
                    Jsonb(values["confidence_breakdown"]),
                    values["final_confidence_score"],
                    values["quality_score"],
                    values["quality_label"],
                    Jsonb(values["quality_signals"]),
                    values["quality_notes"],
                    values["quality_evaluated_at"],
                    scoped.organization_id,
                    conversation_id,
                ),
            )
            if cursor.rowcount:
                self._record_audit_event(
                    connection,
                    organization_id=scoped.organization_id,
                    conversation_id=conversation_id,
                    actor_type=_audit_actor_type(scoped.role),
                    actor_id=scoped.user_id,
                    event_type="conversation.quality_updated",
                    payload={
                        "final_confidence_score": values["final_confidence_score"],
                        "quality_score": values["quality_score"],
                        "quality_label": values["quality_label"],
                    },
                )
            connection.commit()
        return self.get(conversation_id, context=context)

    def record_eval_run(
        self,
        run: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            run_id = str(run.get("id") or run.get("run_id") or f"evalrun_{uuid4().hex[:12]}")
            existing = self._get_eval_run(connection, scoped.organization_id, run_id)
            saved = _normalize_eval_run(
                {**run, "id": run_id},
                organization_id=scoped.organization_id,
                existing=existing,
            )
            connection.execute(
                """
                INSERT INTO eval_runs (
                  id,
                  organization_id,
                  name,
                  suite_name,
                  status,
                  started_at,
                  completed_at,
                  total_cases,
                  passed_cases,
                  failed_cases,
                  average_score,
                  metadata,
                  trace_url,
                  created_at,
                  updated_at
                )
                VALUES (
                  %(id)s,
                  %(organization_id)s,
                  %(name)s,
                  %(suite_name)s,
                  %(status)s,
                  %(started_at)s,
                  %(completed_at)s,
                  %(total_cases)s,
                  %(passed_cases)s,
                  %(failed_cases)s,
                  %(average_score)s,
                  %(metadata)s,
                  %(trace_url)s,
                  %(created_at)s,
                  %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                  name = EXCLUDED.name,
                  suite_name = EXCLUDED.suite_name,
                  status = EXCLUDED.status,
                  started_at = EXCLUDED.started_at,
                  completed_at = EXCLUDED.completed_at,
                  total_cases = EXCLUDED.total_cases,
                  passed_cases = EXCLUDED.passed_cases,
                  failed_cases = EXCLUDED.failed_cases,
                  average_score = EXCLUDED.average_score,
                  metadata = EXCLUDED.metadata,
                  trace_url = EXCLUDED.trace_url,
                  updated_at = EXCLUDED.updated_at
                """,
                {**saved, "metadata": Jsonb(saved["metadata"])},
            )
            loaded = self._get_eval_run(connection, scoped.organization_id, run_id)
            connection.commit()
        return loaded or saved

    def record_eval_result(
        self,
        result: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            result_id = str(result.get("id") or f"evalresult_{uuid4().hex[:12]}")
            existing = self._get_eval_result(connection, scoped.organization_id, result_id)
            saved = _normalize_eval_result(
                {**result, "id": result_id},
                organization_id=scoped.organization_id,
                existing=existing,
            )
            connection.execute(
                """
                INSERT INTO eval_results (
                  id,
                  organization_id,
                  eval_run_id,
                  conversation_id,
                  case_name,
                  status,
                  score,
                  input_payload,
                  expected_payload,
                  actual_payload,
                  metrics,
                  failure_reason,
                  trace_url,
                  created_at
                )
                VALUES (
                  %(id)s,
                  %(organization_id)s,
                  %(eval_run_id)s,
                  %(conversation_id)s,
                  %(case_name)s,
                  %(status)s,
                  %(score)s,
                  %(input)s,
                  %(expected)s,
                  %(actual)s,
                  %(metrics)s,
                  %(failure_reason)s,
                  %(trace_url)s,
                  %(created_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                  eval_run_id = EXCLUDED.eval_run_id,
                  conversation_id = EXCLUDED.conversation_id,
                  case_name = EXCLUDED.case_name,
                  status = EXCLUDED.status,
                  score = EXCLUDED.score,
                  input_payload = EXCLUDED.input_payload,
                  expected_payload = EXCLUDED.expected_payload,
                  actual_payload = EXCLUDED.actual_payload,
                  metrics = EXCLUDED.metrics,
                  failure_reason = EXCLUDED.failure_reason,
                  trace_url = EXCLUDED.trace_url
                """,
                {
                    **saved,
                    "input": Jsonb(saved["input"]),
                    "expected": Jsonb(saved["expected"]),
                    "actual": Jsonb(saved["actual"]),
                    "metrics": Jsonb(saved["metrics"]),
                },
            )
            loaded = self._get_eval_result(connection, scoped.organization_id, result_id)
            connection.commit()
        return loaded or saved

    def list_eval_runs(
        self,
        *,
        limit: int = 50,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 200))
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            rows = connection.execute(
                """
                SELECT *
                FROM eval_runs
                WHERE organization_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (scoped.organization_id, bounded_limit),
            ).fetchall()
        return [self._eval_run_from_row(row) for row in rows]

    def list_eval_results(
        self,
        eval_run_id: str,
        *,
        limit: int = 200,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 500))
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            rows = connection.execute(
                """
                SELECT *
                FROM eval_results
                WHERE organization_id = %s
                  AND eval_run_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (scoped.organization_id, eval_run_id, bounded_limit),
            ).fetchall()
        return [self._eval_result_from_row(row) for row in rows]

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

    def get_sync_state(
        self,
        provider: str,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState | None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            row = connection.execute(
                """
                SELECT organization_id::text AS organization_id,
                       provider,
                       updated_since,
                       payload,
                       updated_at
                FROM integration_sync_state
                WHERE organization_id = %s
                  AND provider = %s
                """,
                (scoped.organization_id, provider),
            ).fetchone()
        if row is None:
            return None
        return IntegrationSyncState(
            organization_id=row["organization_id"],
            provider=row["provider"],
            updated_since=int(row["updated_since"] or 0),
            payload=_json_dict(row["payload"]),
            updated_at=_coerce_datetime(row["updated_at"]),
        )

    def save_sync_state(
        self,
        state: IntegrationSyncState,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            payload_json = Jsonb(state.payload or {})
            connection.execute(
                """
                INSERT INTO integration_sync_state
                    (organization_id, provider, updated_since, payload, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (organization_id, provider) DO UPDATE
                SET updated_since = EXCLUDED.updated_since,
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at
                """,
                (scoped.organization_id, state.provider, int(state.updated_since), payload_json),
            )
            connection.commit()
        state.organization_id = scoped.organization_id
        return state

    def clear(self) -> None:
        with connect(self.settings) as connection:
            connection.execute("TRUNCATE conversation_summaries CASCADE")
            connection.execute("TRUNCATE eval_results CASCADE")
            connection.execute("TRUNCATE eval_runs CASCADE")
            connection.execute("TRUNCATE conversation_memory_items CASCADE")
            connection.execute("TRUNCATE retrieval_hits CASCADE")
            connection.execute("TRUNCATE retrieval_runs CASCADE")
            connection.execute("TRUNCATE knowledge_chunk_embeddings CASCADE")
            connection.execute("TRUNCATE knowledge_chunks CASCADE")
            connection.execute("TRUNCATE knowledge_documents CASCADE")
            connection.execute("TRUNCATE knowledge_ingestion_errors CASCADE")
            connection.execute("TRUNCATE knowledge_ingestion_jobs CASCADE")
            connection.execute("TRUNCATE knowledge_sources CASCADE")
            connection.execute("TRUNCATE audit_events CASCADE")
            connection.execute("TRUNCATE tool_results CASCADE")
            connection.execute("TRUNCATE tool_plans CASCADE")
            connection.execute("TRUNCATE approvals CASCADE")
            connection.execute("TRUNCATE conversation_messages CASCADE")
            connection.execute("TRUNCATE conversations CASCADE")
            connection.commit()

    def _get_eval_run(
        self,
        connection: object,
        organization_id: str | None,
        run_id: str,
    ) -> dict[str, object] | None:
        row = connection.execute(
            """
            SELECT *
            FROM eval_runs
            WHERE organization_id = %s
              AND id = %s
            """,
            (organization_id, run_id),
        ).fetchone()
        return self._eval_run_from_row(row) if row is not None else None

    def _get_eval_result(
        self,
        connection: object,
        organization_id: str | None,
        result_id: str,
    ) -> dict[str, object] | None:
        row = connection.execute(
            """
            SELECT *
            FROM eval_results
            WHERE organization_id = %s
              AND id = %s
            """,
            (organization_id, result_id),
        ).fetchone()
        return self._eval_result_from_row(row) if row is not None else None

    def _eval_run_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": row["id"],
            "organization_id": str(row["organization_id"]) if row["organization_id"] else None,
            "name": row["name"],
            "suite_name": row["suite_name"],
            "status": row["status"],
            "started_at": _coerce_datetime(row["started_at"]),
            "completed_at": _coerce_optional_datetime(row.get("completed_at")),
            "total_cases": _coerce_int(row["total_cases"]),
            "passed_cases": _coerce_int(row["passed_cases"]),
            "failed_cases": _coerce_int(row["failed_cases"]),
            "average_score": _coerce_optional_float(row.get("average_score")),
            "metadata": _json_dict(row.get("metadata")),
            "trace_url": row.get("trace_url"),
            "created_at": _coerce_datetime(row["created_at"]),
            "updated_at": _coerce_datetime(row["updated_at"]),
        }

    def _eval_result_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": row["id"],
            "organization_id": str(row["organization_id"]) if row["organization_id"] else None,
            "eval_run_id": row["eval_run_id"],
            "conversation_id": row.get("conversation_id"),
            "case_name": row["case_name"],
            "status": row["status"],
            "score": _coerce_optional_float(row.get("score")),
            "input": _json_dict(row.get("input_payload")),
            "expected": _json_dict(row.get("expected_payload")),
            "actual": _json_dict(row.get("actual_payload")),
            "metrics": _json_dict(row.get("metrics")),
            "failure_reason": row.get("failure_reason"),
            "trace_url": row.get("trace_url"),
            "created_at": _coerce_datetime(row["created_at"]),
        }

    def _record_from_row(self, row: Mapping[str, object]) -> ConversationRecord:
        payload = {
            "id": row["id"],
            "chatwoot_conversation_id": row["chatwoot_conversation_id"],
            "chatwoot_message_id": row["chatwoot_message_id"],
            "provider_conversation_id": row.get("provider_conversation_id"),
            "customer_name": row["customer_name"],
            "channel": row["channel"],
            "incoming_message": row["incoming_message"],
            "normalized_message": row["normalized_message"],
            "intent": row["intent"],
            "risk_level": row["risk_level"],
            "selected_agent": row.get("selected_agent"),
            "customer_driver": row.get("customer_driver"),
            "retrieved_knowledge": _json_list(row["retrieved_knowledge"]),
            "retrieval_confidence": row.get("retrieval_confidence"),
            "missing_knowledge": bool(row.get("missing_knowledge", False)),
            "retrieval_diagnostic": _json_dict(row.get("retrieval_diagnostic")),
            "crm_context": row["crm_context"],
            "chatwoot_context": row.get("chatwoot_context"),
            "tool_plans": _json_list(row["tool_plans"]),
            "tool_results": _json_list(row["tool_results"]),
            "draft_reply": row["draft_reply"],
            "qa_findings": _json_list(row["qa_findings"]),
            "compliance_status": row["compliance_status"],
            "approval_status": row["approval_status"],
            "send_status": row["send_status"],
            "ticket_status": row.get("ticket_status", "open"),
            "assignee": row.get("assignee"),
            "priority": row.get("priority"),
            "pipeline_stage": row.get("pipeline_stage"),
            "sla_due_at": _coerce_optional_datetime(row.get("sla_due_at")),
            "trace_url": row["trace_url"],
            "eval_tags": _json_list(row.get("eval_tags")),
            "trace_attributes": _json_dict(row.get("trace_attributes")),
            "diagnostic_payload": _json_dict(row.get("diagnostic_payload")),
            "decision_reason": row.get("decision_reason"),
            "guardrail_findings": _json_list(row.get("guardrail_findings")),
            "confidence_breakdown": _json_dict(row.get("confidence_breakdown")),
            "final_confidence_score": row.get("final_confidence_score"),
            "quality_score": row.get("quality_score"),
            "quality_label": row.get("quality_label"),
            "quality_signals": _json_dict(row.get("quality_signals")),
            "quality_notes": row.get("quality_notes"),
            "quality_evaluated_at": row.get("quality_evaluated_at"),
            "messages": _json_list(row.get("messages")),
            "created_at": _coerce_datetime(row["created_at"]),
            "updated_at": _coerce_datetime(row["updated_at"]),
        }
        record = ConversationRecord.model_validate(payload)
        return _attach_quality_fields(record, payload)

    def _conversation_values(
        self,
        record: ConversationRecord,
        organization_id: str | None,
    ) -> dict[str, object]:
        quality_values = _record_quality_values(record)
        return {
            "id": record.id,
            "organization_id": organization_id,
            "chatwoot_conversation_id": record.chatwoot_conversation_id,
            "chatwoot_message_id": record.chatwoot_message_id,
            "provider_conversation_id": getattr(record, "provider_conversation_id", None),
            "customer_name": record.customer_name,
            "channel": record.channel,
            "incoming_message": record.incoming_message,
            "normalized_message": record.normalized_message,
            "intent": record.intent,
            "risk_level": record.risk_level,
            "selected_agent": getattr(record, "selected_agent", None),
            "customer_driver": getattr(record, "customer_driver", None),
            "retrieved_knowledge": Jsonb(_dump_models(record.retrieved_knowledge)),
            "retrieval_confidence": getattr(record, "retrieval_confidence", None),
            "missing_knowledge": bool(getattr(record, "missing_knowledge", False)),
            "retrieval_diagnostic": Jsonb(
                getattr(record, "retrieval_diagnostic", None) or {}
            ),
            "crm_context": Jsonb(_dump_model(record.crm_context))
            if record.crm_context
            else None,
            "chatwoot_context": Jsonb(_dump_model(record.chatwoot_context))
            if record.chatwoot_context
            else None,
            "tool_plans": Jsonb(_dump_models(record.tool_plans)),
            "tool_results": Jsonb(_dump_models(record.tool_results)),
            "draft_reply": record.draft_reply,
            "qa_findings": Jsonb(_dump_models(record.qa_findings)),
            "compliance_status": record.compliance_status,
            "approval_status": record.approval_status,
            "send_status": record.send_status,
            "ticket_status": getattr(record, "ticket_status", "open"),
            "assignee": getattr(record, "assignee", None),
            "priority": getattr(record, "priority", None),
            "pipeline_stage": getattr(record, "pipeline_stage", None),
            "sla_due_at": getattr(record, "sla_due_at", None),
            "trace_url": record.trace_url,
            "eval_tags": Jsonb(quality_values["eval_tags"]),
            "trace_attributes": Jsonb(quality_values["trace_attributes"]),
            "diagnostic_payload": Jsonb(quality_values["diagnostic_payload"]),
            "decision_reason": quality_values["decision_reason"],
            "guardrail_findings": Jsonb(quality_values["guardrail_findings"]),
            "confidence_breakdown": Jsonb(quality_values["confidence_breakdown"]),
            "final_confidence_score": quality_values["final_confidence_score"],
            "quality_score": quality_values["quality_score"],
            "quality_label": quality_values["quality_label"],
            "quality_signals": Jsonb(quality_values["quality_signals"]),
            "quality_notes": quality_values["quality_notes"],
            "quality_evaluated_at": quality_values["quality_evaluated_at"],
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

    def append_memory_items(
        self,
        conversation_id: str,
        items: list[MemoryHit],
        context: StoreContext | None = None,
    ) -> None:
        if not items:
            return
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            record = self.get(conversation_id, context=context)
            embedding_model = self.embedding_service.embedding_model
            for item in items:
                content = item.content.strip()
                if not content:
                    continue
                embedding = vector_literal(self.embedding_service.embed_text(content))
                connection.execute(
                    """
                    INSERT INTO conversation_memory_items (
                      organization_id,
                      conversation_id,
                      chatwoot_conversation_id,
                      customer_name,
                      memory_type,
                      content,
                      source,
                      score,
                      source_message_id,
                      metadata,
                      embedding_model,
                      embedding,
                      content_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (organization_id, conversation_id, memory_type, content_hash)
                    WHERE conversation_id IS NOT NULL
                    DO UPDATE SET
                      score = GREATEST(conversation_memory_items.score, EXCLUDED.score),
                      metadata = conversation_memory_items.metadata || EXCLUDED.metadata,
                      updated_at = now()
                    """,
                    (
                        scoped.organization_id,
                        conversation_id,
                        item.chatwoot_conversation_id
                        or (record.chatwoot_conversation_id if record else None),
                        record.customer_name if record else None,
                        item.memory_type,
                        content,
                        item.source,
                        item.score,
                        item.source_message_id,
                        Jsonb(item.metadata),
                        embedding_model,
                        embedding,
                        content_hash(content),
                    ),
                )
            connection.commit()

    def list_memory_items(
        self,
        conversation_id: str,
        *,
        query: str | None = None,
        limit: int = 8,
        context: StoreContext | None = None,
    ) -> list[MemoryHit]:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            if query:
                embedding = vector_literal(self.embedding_service.embed_text(query))
                rows = connection.execute(
                    """
                    SELECT
                      *,
                      GREATEST(score, 1 - (embedding <=> %s::vector)) AS rank_score
                    FROM conversation_memory_items
                    WHERE organization_id = %s
                      AND conversation_id = %s
                      AND embedding_model = %s
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        embedding,
                        scoped.organization_id,
                        conversation_id,
                        self.embedding_service.embedding_model,
                        embedding,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM conversation_memory_items
                    WHERE organization_id = %s
                      AND conversation_id = %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (scoped.organization_id, conversation_id, limit),
                ).fetchall()
            return [_memory_from_row(row) for row in rows]

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

    def list(
        self,
        context: StoreContext | None = None,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
    ) -> list[ConversationRecord]:
        return self._current().list(
            context=context,
            ticket_status=ticket_status,
            assignee=assignee,
            priority=priority,
        )

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

    def update_ticket(
        self,
        conversation_id: str,
        *,
        ticket_status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        pipeline_stage: str | None = None,
        sla_due_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        return self._current().update_ticket(
            conversation_id,
            ticket_status=ticket_status,
            assignee=assignee,
            priority=priority,
            pipeline_stage=pipeline_stage,
            sla_due_at=sla_due_at,
            context=context,
        )

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

    def update_conversation_quality(
        self,
        conversation_id: str,
        *,
        eval_tags: list[str] | None = None,
        trace_attributes: Mapping[str, object] | None = None,
        diagnostic_payload: Mapping[str, object] | None = None,
        decision_reason: str | None = None,
        guardrail_findings: Sequence[object] | None = None,
        confidence_breakdown: Mapping[str, object] | None = None,
        final_confidence_score: float | None = None,
        quality_score: float | None = None,
        quality_label: str | None = None,
        quality_signals: Mapping[str, object] | None = None,
        quality_notes: str | None = None,
        quality_evaluated_at: datetime | None = None,
        context: StoreContext | None = None,
    ) -> ConversationRecord | None:
        return self._current().update_conversation_quality(
            conversation_id,
            eval_tags=eval_tags,
            trace_attributes=trace_attributes,
            diagnostic_payload=diagnostic_payload,
            decision_reason=decision_reason,
            guardrail_findings=guardrail_findings,
            confidence_breakdown=confidence_breakdown,
            final_confidence_score=final_confidence_score,
            quality_score=quality_score,
            quality_label=quality_label,
            quality_signals=quality_signals,
            quality_notes=quality_notes,
            quality_evaluated_at=quality_evaluated_at,
            context=context,
        )

    def record_eval_run(
        self,
        run: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        return self._current().record_eval_run(run, context=context)

    def record_eval_result(
        self,
        result: Mapping[str, object],
        context: StoreContext | None = None,
    ) -> dict[str, object]:
        return self._current().record_eval_result(result, context=context)

    def list_eval_runs(
        self,
        *,
        limit: int = 50,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        return self._current().list_eval_runs(limit=limit, context=context)

    def list_eval_results(
        self,
        eval_run_id: str,
        *,
        limit: int = 200,
        context: StoreContext | None = None,
    ) -> list[dict[str, object]]:
        return self._current().list_eval_results(
            eval_run_id,
            limit=limit,
            context=context,
        )

    def append_memory_items(
        self,
        conversation_id: str,
        items: list[MemoryHit],
        context: StoreContext | None = None,
    ) -> None:
        return self._current().append_memory_items(
            conversation_id,
            items,
            context=context,
        )

    def list_memory_items(
        self,
        conversation_id: str,
        *,
        query: str | None = None,
        limit: int = 8,
        context: StoreContext | None = None,
    ) -> list[MemoryHit]:
        return self._current().list_memory_items(
            conversation_id,
            query=query,
            limit=limit,
            context=context,
        )

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

    def get_sync_state(
        self,
        provider: str,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState | None:
        return self._current().get_sync_state(provider, context=context)

    def save_sync_state(
        self,
        state: IntegrationSyncState,
        *,
        context: StoreContext | None = None,
    ) -> IntegrationSyncState:
        return self._current().save_sync_state(state, context=context)


ConversationStore = InMemoryConversationStore
store = StoreProxy()
