from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Literal, NotRequired, TypedDict

import httpx

from agent_studio.chatwoot_mapping import normalize_chatwoot_channel
from agent_studio.config import Settings
from agent_studio.schemas import ChatwootConversationContext, ChatwootInboxContext


class ChatwootSendResult(TypedDict):
    status: Literal["sent", "dry_run", "failed"]
    detail: str
    provider: str
    action: str
    target_url: NotRequired[str]
    http_status: NotRequired[int]
    response_excerpt: NotRequired[str]
    error_type: NotRequired[str]
    external_id: NotRequired[str]


def _response_excerpt(response: httpx.Response, limit: int = 500) -> str:
    text = response.text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, int):
        return str(value)
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _datetime_or_none(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            return datetime.fromtimestamp(int(cleaned), timezone.utc)
        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mapping_at(mapping: Mapping[str, object], *keys: str) -> object | None:
    current: object = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _inbox_context(payload: Mapping[str, object]) -> ChatwootInboxContext | None:
    inbox = _mapping(payload.get("inbox"))
    if not inbox:
        inbox = _mapping(_mapping_at(payload, "conversation", "inbox"))
    if not inbox:
        inbox = _mapping(_mapping_at(payload, "conversation", "contact_inbox", "inbox"))
    if not inbox:
        return None
    return ChatwootInboxContext(
        id=_str_or_none(inbox.get("id")),
        name=_str_or_none(inbox.get("name")),
        channel_type=_str_or_none(inbox.get("channel_type")),
        provider=_str_or_none(inbox.get("provider")),
    )


def _normalized_channel_from_context_payload(
    payload: Mapping[str, object],
    fallback_channel: str | None,
) -> str | None:
    conversation = _mapping(payload.get("conversation"))
    inbox = _mapping(payload.get("inbox")) or _mapping(conversation.get("inbox"))
    candidates = [
        conversation.get("channel"),
        _mapping(conversation.get("meta")).get("channel"),
        inbox.get("channel_type"),
        inbox.get("medium"),
        inbox.get("provider"),
        payload.get("channel"),
        payload.get("channel_type"),
    ]
    for candidate in candidates:
        normalized = normalize_chatwoot_channel(candidate)
        if normalized:
            return normalized
    return normalize_chatwoot_channel(fallback_channel)


def chatwoot_context_from_payload(
    payload: Mapping[str, object],
    *,
    normalized_channel: str | None = None,
    fetch_status: Literal["not_fetched", "ready", "failed", "unconfigured"] = "not_fetched",
    fetch_error: str | None = None,
) -> ChatwootConversationContext:
    conversation = _mapping(payload.get("conversation")) or payload
    meta = _mapping(conversation.get("meta"))
    sender = _mapping(meta.get("sender"))
    assignee = _mapping(conversation.get("assignee"))
    return ChatwootConversationContext(
        normalized_channel=normalized_channel
        or _normalized_channel_from_context_payload(payload, None),
        contact_last_seen_at=_datetime_or_none(sender.get("last_seen_at"))
        or _datetime_or_none(conversation.get("contact_last_seen_at")),
        agent_last_seen_at=_datetime_or_none(conversation.get("agent_last_seen_at")),
        assignee_last_seen_at=_datetime_or_none(assignee.get("last_seen_at"))
        or _datetime_or_none(conversation.get("assignee_last_seen_at")),
        last_activity_at=_datetime_or_none(conversation.get("last_activity_at")),
        unread_count=_int_or_none(conversation.get("unread_count")),
        can_reply=_bool_or_none(conversation.get("can_reply")),
        source_id=_str_or_none(conversation.get("source_id"))
        or _str_or_none(_mapping_at(conversation, "contact_inbox", "source_id")),
        inbox=_inbox_context(payload),
        status=_str_or_none(conversation.get("status")),
        priority=_str_or_none(conversation.get("priority")),
        labels=_string_list(conversation.get("labels")),
        waiting_since=_datetime_or_none(conversation.get("waiting_since")),
        fetch_status=fetch_status,
        fetch_error=fetch_error,
        fetched_at=_now() if fetch_status in {"ready", "failed", "unconfigured"} else None,
    )


async def fetch_conversation_details(
    *,
    settings: Settings,
    chatwoot_conversation_id: str | None,
    fallback_channel: str | None = None,
) -> ChatwootConversationContext:
    if not settings.chatwoot_configured:
        return ChatwootConversationContext(
            normalized_channel=normalize_chatwoot_channel(fallback_channel),
            fetch_status="unconfigured",
            fetch_error="Chatwoot credentials are not fully configured.",
            fetched_at=_now(),
        )

    if not chatwoot_conversation_id:
        return ChatwootConversationContext(
            normalized_channel=normalize_chatwoot_channel(fallback_channel),
            fetch_status="failed",
            fetch_error="Missing Chatwoot conversation ID.",
            fetched_at=_now(),
        )

    base_url = str(settings.chatwoot_base_url).rstrip("/")
    account_id = settings.chatwoot_account_id
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{chatwoot_conversation_id}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"api_access_token": str(settings.chatwoot_api_access_token)},
            )
    except httpx.HTTPError as exc:
        return ChatwootConversationContext(
            normalized_channel=normalize_chatwoot_channel(fallback_channel),
            fetch_status="failed",
            fetch_error=f"Chatwoot details fetch failed: {exc.__class__.__name__}.",
            fetched_at=_now(),
        )

    if not response.is_success:
        return ChatwootConversationContext(
            normalized_channel=normalize_chatwoot_channel(fallback_channel),
            fetch_status="failed",
            fetch_error=f"Chatwoot details fetch failed with HTTP {response.status_code}.",
            fetched_at=_now(),
        )

    try:
        body = response.json()
    except ValueError:
        body = {}
    payload = body if isinstance(body, Mapping) else {}
    wrapped_payload = payload.get("payload")
    if isinstance(wrapped_payload, Mapping):
        payload = wrapped_payload
    return chatwoot_context_from_payload(
        payload,
        normalized_channel=_normalized_channel_from_context_payload(
            payload,
            fallback_channel,
        ),
        fetch_status="ready",
    )


async def fetch_conversation_messages(
    *,
    settings: Settings,
    chatwoot_conversation_id: str | None,
) -> dict[str, object]:
    if not settings.chatwoot_configured or not chatwoot_conversation_id:
        return {"status": "unconfigured", "messages": []}
    base_url = str(settings.chatwoot_base_url).rstrip("/")
    account_id = settings.chatwoot_account_id
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{chatwoot_conversation_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"api_access_token": str(settings.chatwoot_api_access_token)},
            )
    except httpx.HTTPError as exc:
        return {"status": "failed", "messages": [], "error": exc.__class__.__name__}
    if not response.is_success:
        return {"status": "failed", "messages": [], "http_status": response.status_code}
    try:
        body = response.json()
    except ValueError:
        return {"status": "failed", "messages": [], "error": "invalid_json"}
    messages = body.get("payload") if isinstance(body, Mapping) else None
    return {"status": "ready", "messages": messages if isinstance(messages, list) else []}


async def send_approved_reply(
    *,
    settings: Settings,
    chatwoot_conversation_id: str | None,
    content: str,
) -> ChatwootSendResult:
    if not settings.chatwoot_configured:
        return ChatwootSendResult(
            status="dry_run",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            detail="Chatwoot credentials are not fully configured; approved send stayed in dry-run.",
        )

    if not chatwoot_conversation_id:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            detail="Missing Chatwoot conversation ID.",
        )

    base_url = str(settings.chatwoot_base_url).rstrip("/")
    account_id = settings.chatwoot_account_id
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{chatwoot_conversation_id}/messages"

    if settings.chatwoot_dry_run:
        return ChatwootSendResult(
            status="dry_run",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            detail="Chatwoot credentials are configured, but dry-run is enabled.",
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers={"api_access_token": str(settings.chatwoot_api_access_token)},
                json={"content": content, "message_type": "outgoing"},
            )
    except httpx.TimeoutException as exc:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            error_type=exc.__class__.__name__,
            detail="Chatwoot send timed out before a response was received.",
        )
    except httpx.RequestError as exc:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            error_type=exc.__class__.__name__,
            detail=f"Chatwoot send failed before receiving an HTTP response: {exc.__class__.__name__}.",
        )

    if response.is_success:
        external_id: str | None = None
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            id_value = body.get("id")
            external_id = str(id_value) if id_value is not None else None
        result = ChatwootSendResult(
            status="sent",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            http_status=response.status_code,
            detail="Approved reply sent to Chatwoot.",
        )
        if external_id:
            result["external_id"] = external_id
        return result

    return ChatwootSendResult(
        status="failed",
        provider="Chatwoot",
        action="chatwoot.messages.send_approved",
        target_url=url,
        http_status=response.status_code,
        response_excerpt=_response_excerpt(response),
        detail=f"Chatwoot send failed with HTTP {response.status_code}.",
    )
