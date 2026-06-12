from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re


class EventTypes:
    CHATWOOT_WEBHOOK_RECEIVED = "chatwoot.webhook.received"
    CHATWOOT_WEBHOOK_PERSISTED = "chatwoot.webhook.persisted"
    WEBHOOK_REJECTED = "webhook.rejected"
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_UPDATED = "conversation.updated"
    ROUTER_CLASSIFIED = "router.classified"
    RETRIEVAL_SEARCH = "retrieval.search"
    RETRIEVAL_NO_MATCH = "retrieval.no_match"
    MEMORY_SELECTED = "memory.selected"
    CRM_CONTEXT_READY = "crm.context.ready"
    TOOL_PLANNED = "tool.planned"
    TOOL_EXECUTED = "tool.executed"
    DRAFT_CREATED = "draft.created"
    QA_REVIEWED = "qa.reviewed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    PROVIDER_REQUEST = "provider.request"
    PROVIDER_RESPONSE = "provider.response"
    PROVIDER_ERROR = "provider.error"
    SEND_SUCCEEDED = "send.succeeded"
    SEND_FAILED = "send.failed"

    ALL = (
        CHATWOOT_WEBHOOK_RECEIVED,
        CHATWOOT_WEBHOOK_PERSISTED,
        WEBHOOK_REJECTED,
        CONVERSATION_CREATED,
        CONVERSATION_UPDATED,
        ROUTER_CLASSIFIED,
        RETRIEVAL_SEARCH,
        RETRIEVAL_NO_MATCH,
        MEMORY_SELECTED,
        CRM_CONTEXT_READY,
        TOOL_PLANNED,
        TOOL_EXECUTED,
        DRAFT_CREATED,
        QA_REVIEWED,
        APPROVAL_REQUESTED,
        APPROVAL_APPROVED,
        APPROVAL_REJECTED,
        PROVIDER_REQUEST,
        PROVIDER_RESPONSE,
        PROVIDER_ERROR,
        SEND_SUCCEEDED,
        SEND_FAILED,
    )


class SpanNames:
    WEBHOOK_INGEST = "agent_studio.webhook.ingest"
    CONVERSATION_PERSIST = "agent_studio.conversation.persist"
    ROUTER_CLASSIFY = "agent_studio.router.classify"
    KNOWLEDGE_RETRIEVAL = "agent_studio.knowledge.retrieve"
    MEMORY_RECALL = "agent_studio.memory.recall"
    CRM_CONTEXT = "agent_studio.crm.context"
    TOOL_POLICY = "agent_studio.tool.policy"
    TOOL_EXECUTION = "agent_studio.tool.execute"
    DRAFT_GENERATION = "agent_studio.draft.generate"
    QA_REVIEW = "agent_studio.qa.review"
    APPROVAL_GATE = "agent_studio.approval.gate"
    PROVIDER_REQUEST = "agent_studio.provider.request"
    PROVIDER_SEND = "agent_studio.provider.send"
    DIAGNOSTIC_EVENT = "agent_studio.diagnostic.event"
    UNKNOWN = "agent_studio.unknown"

    ALL = (
        WEBHOOK_INGEST,
        CONVERSATION_PERSIST,
        ROUTER_CLASSIFY,
        KNOWLEDGE_RETRIEVAL,
        MEMORY_RECALL,
        CRM_CONTEXT,
        TOOL_POLICY,
        TOOL_EXECUTION,
        DRAFT_GENERATION,
        QA_REVIEW,
        APPROVAL_GATE,
        PROVIDER_REQUEST,
        PROVIDER_SEND,
        DIAGNOSTIC_EVENT,
        UNKNOWN,
    )


class ProviderErrorCategory:
    AUTH = "auth"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    PROVIDER_4XX = "provider_4xx"
    PROVIDER_5XX = "provider_5xx"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

    ALL = (
        AUTH,
        CONFIGURATION,
        NETWORK,
        PROVIDER_4XX,
        PROVIDER_5XX,
        RATE_LIMITED,
        TIMEOUT,
        VALIDATION,
        UNKNOWN,
    )


@dataclass(frozen=True)
class ProviderErrorSummary:
    category: str
    retryable: bool
    status_code: int | None = None
    message: str = ""


_REDACTED = "[redacted]"
_REDACTED_PROVIDER_RESPONSE = "[redacted_provider_response]"
_REDACTED_TRANSCRIPT = "[redacted_transcript]"
_CLIPPED_DEPTH = "[clipped_depth]"
_MAX_STRING_LENGTH = 512
_MAX_COLLECTION_ITEMS = 20
_MAX_DEPTH = 6

_EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|webhook[_ -]?"
    r"(?:secret|token)|secret|password|authorization)\b\s*[:=]\s*"
    r"['\"]?[^'\"\s,;}]+",
    re.IGNORECASE,
)
_KNOWN_SECRET_PATTERN = re.compile(
    r"\b(?:sk|pk|rk|whsec|xoxb|ghp|github_pat|glpat)[-_]"
    r"[A-Za-z0-9][A-Za-z0-9_-]{8,}\b",
)

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "accesstoken",
    "auth",
    "authorization",
    "bearer",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "header",
    "headers",
    "password",
    "refresh_token",
    "refreshtoken",
    "secret",
    "set_cookie",
    "setcookie",
    "token",
    "webhook_secret",
    "webhook_token",
    "webhooksecret",
    "webhooktoken",
}
_SENSITIVE_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_cookie",
    "_password",
    "_secret",
    "_token",
)
_PROVIDER_RESPONSE_KEYS = {
    "http_response_body",
    "provider_payload",
    "provider_raw",
    "provider_response",
    "provider_response_body",
    "raw",
    "raw_payload",
    "raw_provider_response",
    "raw_response",
    "response_body",
}
_TRANSCRIPT_KEYS = {
    "chat_history",
    "conversation_history",
    "conversation_transcript",
    "message_history",
    "messages",
    "thread",
    "transcript",
    "transcripts",
}
_SPAN_ALIASES = {
    "approval": SpanNames.APPROVAL_GATE,
    "approval_gate": SpanNames.APPROVAL_GATE,
    "approval_requested": SpanNames.APPROVAL_GATE,
    "chatwoot_webhook": SpanNames.WEBHOOK_INGEST,
    "chatwoot_webhook_persisted": SpanNames.WEBHOOK_INGEST,
    "conversation_persist": SpanNames.CONVERSATION_PERSIST,
    "conversation_updated": SpanNames.CONVERSATION_PERSIST,
    "crm": SpanNames.CRM_CONTEXT,
    "crm_context": SpanNames.CRM_CONTEXT,
    "diagnostic": SpanNames.DIAGNOSTIC_EVENT,
    "diagnostic_event": SpanNames.DIAGNOSTIC_EVENT,
    "draft": SpanNames.DRAFT_GENERATION,
    "draft_created": SpanNames.DRAFT_GENERATION,
    "draft_generation": SpanNames.DRAFT_GENERATION,
    "draft_reply": SpanNames.DRAFT_GENERATION,
    "memory": SpanNames.MEMORY_RECALL,
    "memory_recall": SpanNames.MEMORY_RECALL,
    "provider": SpanNames.PROVIDER_REQUEST,
    "provider_request": SpanNames.PROVIDER_REQUEST,
    "provider_send": SpanNames.PROVIDER_SEND,
    "qa": SpanNames.QA_REVIEW,
    "qa_review": SpanNames.QA_REVIEW,
    "retrieval": SpanNames.KNOWLEDGE_RETRIEVAL,
    "retrieval_search": SpanNames.KNOWLEDGE_RETRIEVAL,
    "router": SpanNames.ROUTER_CLASSIFY,
    "router_classify": SpanNames.ROUTER_CLASSIFY,
    "tool": SpanNames.TOOL_EXECUTION,
    "tool_execution": SpanNames.TOOL_EXECUTION,
    "tool_policy": SpanNames.TOOL_POLICY,
    "webhook": SpanNames.WEBHOOK_INGEST,
}
_EVENT_SPAN_ALIASES = {
    EventTypes.CHATWOOT_WEBHOOK_RECEIVED: SpanNames.WEBHOOK_INGEST,
    EventTypes.CHATWOOT_WEBHOOK_PERSISTED: SpanNames.WEBHOOK_INGEST,
    EventTypes.CONVERSATION_CREATED: SpanNames.CONVERSATION_PERSIST,
    EventTypes.CONVERSATION_UPDATED: SpanNames.CONVERSATION_PERSIST,
    EventTypes.ROUTER_CLASSIFIED: SpanNames.ROUTER_CLASSIFY,
    EventTypes.RETRIEVAL_SEARCH: SpanNames.KNOWLEDGE_RETRIEVAL,
    EventTypes.RETRIEVAL_NO_MATCH: SpanNames.KNOWLEDGE_RETRIEVAL,
    EventTypes.MEMORY_SELECTED: SpanNames.MEMORY_RECALL,
    EventTypes.CRM_CONTEXT_READY: SpanNames.CRM_CONTEXT,
    EventTypes.TOOL_PLANNED: SpanNames.TOOL_POLICY,
    EventTypes.TOOL_EXECUTED: SpanNames.TOOL_EXECUTION,
    EventTypes.DRAFT_CREATED: SpanNames.DRAFT_GENERATION,
    EventTypes.QA_REVIEWED: SpanNames.QA_REVIEW,
    EventTypes.APPROVAL_REQUESTED: SpanNames.APPROVAL_GATE,
    EventTypes.APPROVAL_APPROVED: SpanNames.APPROVAL_GATE,
    EventTypes.APPROVAL_REJECTED: SpanNames.APPROVAL_GATE,
    EventTypes.PROVIDER_REQUEST: SpanNames.PROVIDER_REQUEST,
    EventTypes.PROVIDER_RESPONSE: SpanNames.PROVIDER_REQUEST,
    EventTypes.PROVIDER_ERROR: SpanNames.PROVIDER_REQUEST,
    EventTypes.SEND_SUCCEEDED: SpanNames.PROVIDER_SEND,
    EventTypes.SEND_FAILED: SpanNames.PROVIDER_SEND,
}


def span_name_for(stage: object | None) -> str:
    if not isinstance(stage, str) or not stage.strip():
        return SpanNames.UNKNOWN

    cleaned = stage.strip().lower()
    if cleaned in _EVENT_SPAN_ALIASES:
        return _EVENT_SPAN_ALIASES[cleaned]

    normalized = _normalize_key(cleaned)
    return _SPAN_ALIASES.get(normalized, SpanNames.UNKNOWN)


def sanitize_payload(
    value: object,
    *,
    max_string_length: int = _MAX_STRING_LENGTH,
    max_collection_items: int = _MAX_COLLECTION_ITEMS,
    max_depth: int = _MAX_DEPTH,
) -> object:
    return _sanitize_value(
        value,
        key=None,
        depth=0,
        max_string_length=max_string_length,
        max_collection_items=max_collection_items,
        max_depth=max_depth,
    )


def categorize_provider_error(error: object) -> ProviderErrorSummary:
    status_code = _extract_status_code(error)
    raw_message = _extract_error_message(error)
    message = _redact_text(raw_message, max_string_length=160)
    lowered = message.lower()

    if status_code in {401, 403}:
        return _error_summary(ProviderErrorCategory.AUTH, status_code, message)
    if status_code == 429:
        return _error_summary(ProviderErrorCategory.RATE_LIMITED, status_code, message)
    if status_code == 408 or _contains_any(lowered, ("timeout", "timed out")):
        return _error_summary(ProviderErrorCategory.TIMEOUT, status_code, message)
    if _contains_any(
        lowered,
        (
            "missing api key",
            "missing token",
            "not configured",
            "unconfigured",
            "no provider credentials",
            "credential",
        ),
    ):
        return _error_summary(ProviderErrorCategory.CONFIGURATION, status_code, message)
    if status_code in {400, 422} or _contains_any(
        lowered,
        ("invalid payload", "validation", "schema", "bad request"),
    ):
        return _error_summary(ProviderErrorCategory.VALIDATION, status_code, message)
    if _contains_any(
        lowered,
        (
            "connection reset",
            "connection refused",
            "dns",
            "network",
            "temporary failure",
        ),
    ):
        return _error_summary(ProviderErrorCategory.NETWORK, status_code, message)
    if status_code is not None and 500 <= status_code <= 599:
        return _error_summary(ProviderErrorCategory.PROVIDER_5XX, status_code, message)
    if status_code is not None and 400 <= status_code <= 499:
        return _error_summary(ProviderErrorCategory.PROVIDER_4XX, status_code, message)
    return _error_summary(ProviderErrorCategory.UNKNOWN, status_code, message)


def aggregate_ai_ops_metrics(
    conversations: Iterable[object],
    events: Iterable[object] = (),
) -> dict[str, object]:
    conversation_list = list(conversations)
    event_list = list(events)

    approval_counts: Counter[str] = Counter()
    send_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    intent_counts: Counter[str] = Counter()
    tool_result_counts: Counter[str] = Counter()
    confidence_values: list[float] = []
    missing_knowledge_count = 0
    drafted_count = 0
    trace_linked_count = 0
    memory_available_count = 0
    tool_plan_count = 0

    for record in conversation_list:
        approval_counts.update([_string_field(record, "approval_status", "unknown")])
        send_counts.update([_string_field(record, "send_status", "unknown")])
        risk_counts.update([_string_field(record, "risk_level", "unknown")])
        intent_counts.update([_string_field(record, "intent", "unknown")])

        if bool(_field(record, "missing_knowledge", False)):
            missing_knowledge_count += 1
        if str(_field(record, "draft_reply", "") or "").strip():
            drafted_count += 1
        if str(_field(record, "trace_url", "") or "").strip():
            trace_linked_count += 1
        if _memory_available(record):
            memory_available_count += 1

        confidence = _float_or_none(_field(record, "retrieval_confidence", None))
        if confidence is not None:
            confidence_values.append(confidence)

        tool_plans = _sequence(_field(record, "tool_plans", []))
        tool_results = _sequence(_field(record, "tool_results", []))
        tool_plan_count += len(tool_plans)
        for result in tool_results:
            tool_result_counts.update([_string_field(result, "status", "unknown")])

    event_type_counts: Counter[str] = Counter()
    event_status_counts: Counter[str] = Counter()
    provider_error_counts: Counter[str] = Counter()
    error_event_count = 0

    for event in event_list:
        event_type = _string_field(event, "event_type", "unknown")
        event_status = _string_field(event, "status", "info")
        event_payload = _mapping(_field(event, "payload", {}))
        event_type_counts.update([event_type])
        event_status_counts.update([event_status])

        is_error = (
            event_status == "error"
            or event_type == EventTypes.PROVIDER_ERROR
            or event_type.endswith(".error")
            or event_type.endswith(".failed")
        )
        if is_error:
            error_event_count += 1
        if _is_provider_error_event(event_type, event_status, event_payload):
            category = _provider_error_category(event_payload)
            provider_error_counts.update([category])

    return {
        "conversation_count": len(conversation_list),
        "approval_status_counts": _counter_to_dict(approval_counts),
        "send_status_counts": _counter_to_dict(send_counts),
        "risk_level_counts": _counter_to_dict(risk_counts),
        "intent_counts": _counter_to_dict(intent_counts),
        "missing_knowledge_count": missing_knowledge_count,
        "avg_retrieval_confidence": _average(confidence_values),
        "drafted_count": drafted_count,
        "trace_linked_count": trace_linked_count,
        "memory_available_count": memory_available_count,
        "tool_plan_count": tool_plan_count,
        "tool_result_status_counts": _counter_to_dict(tool_result_counts),
        "diagnostic_event_count": len(event_list),
        "diagnostic_event_type_counts": _counter_to_dict(event_type_counts),
        "diagnostic_status_counts": _counter_to_dict(event_status_counts),
        "error_event_count": error_event_count,
        "provider_error_category_counts": _counter_to_dict(provider_error_counts),
    }


def _sanitize_value(
    value: object,
    *,
    key: str | None,
    depth: int,
    max_string_length: int,
    max_collection_items: int,
    max_depth: int,
) -> object:
    if key is not None:
        if _is_sensitive_key(key):
            return _REDACTED
        if _is_provider_response_key(key):
            return _REDACTED_PROVIDER_RESPONSE
        if _is_transcript_key(key) and isinstance(value, (str, list, tuple)):
            return _REDACTED_TRANSCRIPT

    if depth >= max_depth:
        return _CLIPPED_DEPTH

    dumped = _model_dump(value)
    if dumped is not None:
        return _sanitize_value(
            dumped,
            key=key,
            depth=depth,
            max_string_length=max_string_length,
            max_collection_items=max_collection_items,
            max_depth=max_depth,
        )
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for index, (nested_key, nested_value) in enumerate(value.items()):
            if index >= max_collection_items:
                sanitized["__clipped_items__"] = len(value) - max_collection_items
                break
            key_text = str(nested_key)
            sanitized[key_text] = _sanitize_value(
                nested_value,
                key=key_text,
                depth=depth + 1,
                max_string_length=max_string_length,
                max_collection_items=max_collection_items,
                max_depth=max_depth,
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        sanitized_items = [
            _sanitize_value(
                item,
                key=None,
                depth=depth + 1,
                max_string_length=max_string_length,
                max_collection_items=max_collection_items,
                max_depth=max_depth,
            )
            for item in list(value)[:max_collection_items]
        ]
        if len(value) > max_collection_items:
            sanitized_items.append(
                f"[clipped_items:{len(value) - max_collection_items}]",
            )
        return sanitized_items
    if isinstance(value, str):
        return _redact_text(value, max_string_length=max_string_length)
    return value


def _redact_text(value: str, *, max_string_length: int) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer [redacted]", value)
    redacted = _JWT_PATTERN.sub(_REDACTED, redacted)
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}={_REDACTED}",
        redacted,
    )
    redacted = _KNOWN_SECRET_PATTERN.sub(_REDACTED, redacted)
    redacted = _EMAIL_PATTERN.sub("[email_redacted]", redacted)
    redacted = _PHONE_PATTERN.sub(_redact_phone_match, redacted)
    return _clip_text(redacted, max_string_length=max_string_length)


def _redact_phone_match(match: re.Match[str]) -> str:
    text = match.group(0)
    if sum(character.isdigit() for character in text) < 10:
        return text
    return "[phone_redacted]"


def _clip_text(value: str, *, max_string_length: int) -> str:
    if max_string_length < 1:
        return "...[clipped]"
    if len(value) <= max_string_length:
        return value
    return f"{value[:max_string_length]}...[clipped]"


def _error_summary(
    category: str,
    status_code: int | None,
    message: str,
) -> ProviderErrorSummary:
    return ProviderErrorSummary(
        category=category,
        retryable=category
        in {
            ProviderErrorCategory.NETWORK,
            ProviderErrorCategory.PROVIDER_5XX,
            ProviderErrorCategory.RATE_LIMITED,
            ProviderErrorCategory.TIMEOUT,
        },
        status_code=status_code,
        message=message,
    )


def _extract_status_code(value: object) -> int | None:
    for key in ("status_code", "status", "code"):
        status_code = _int_or_none(_field(value, key, None))
        if status_code is not None:
            return status_code

    response = _field(value, "response", None)
    if response is not None and response is not value:
        return _extract_status_code(response)
    return None


def _extract_error_message(value: object) -> str:
    for key in ("message", "detail", "error", "error_message", "reason"):
        found = _field(value, key, None)
        if isinstance(found, str) and found.strip():
            return found

    response_text = _field(_field(value, "response", None), "text", None)
    if isinstance(response_text, str) and response_text.strip():
        return response_text
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, Mapping):
        return " ".join(str(item) for item in value.values() if item is not None)
    return str(value)


def _provider_error_category(payload: Mapping[str, object]) -> str:
    for key in ("provider_error_category", "error_category", "category"):
        value = payload.get(key)
        if isinstance(value, str) and value in ProviderErrorCategory.ALL:
            return value
    return categorize_provider_error(payload).category


def _is_provider_error_event(
    event_type: str,
    event_status: str,
    payload: Mapping[str, object],
) -> bool:
    if event_type == EventTypes.PROVIDER_ERROR:
        return True
    if event_status != "error":
        return False
    if "provider" in payload or "status_code" in payload:
        return True
    return event_type.startswith("provider.") or event_type.startswith("tool.")


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _string_field(value: object, name: str, default: str) -> str:
    found = _field(value, name, default)
    if found is None:
        return default
    text = str(found).strip()
    return text or default


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    dumped = _model_dump(value)
    if isinstance(dumped, Mapping):
        return dumped
    return {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _model_dump(value: object) -> object | None:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return None


def _memory_available(record: object) -> bool:
    diagnostic = _mapping(_field(record, "memory_diagnostic", {}))
    if bool(diagnostic.get("memory_available")):
        return True
    return bool(_sequence(_field(record, "memory_context", [])))


def _average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    compact = normalized.replace("_", "")
    return (
        normalized in _SENSITIVE_KEYS
        or compact in _SENSITIVE_KEYS
        or normalized.endswith(_SENSITIVE_SUFFIXES)
    )


def _is_provider_response_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _PROVIDER_RESPONSE_KEYS


def _is_transcript_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _TRANSCRIPT_KEYS


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _contains_any(value: str, needles: Iterable[str]) -> bool:
    return any(needle in value for needle in needles)


__all__ = [
    "EventTypes",
    "ProviderErrorCategory",
    "ProviderErrorSummary",
    "SpanNames",
    "aggregate_ai_ops_metrics",
    "categorize_provider_error",
    "sanitize_payload",
    "span_name_for",
]
