from collections.abc import Mapping

from agent_studio.schemas import ChatwootWebhookPayload


NORMALIZED_CHANNELS = {
    "email",
    "web_chat",
    "sms",
    "voice",
    "facebook",
    "instagram",
    "whatsapp",
    "telegram",
    "line",
    "api",
    "unknown",
}

LEGACY_PROVIDER_CHANNELS = {"chatwoot", "channel::chatwoot"}

CHANNEL_ALIASES = {
    "channel::email": "email",
    "email": "email",
    "mail": "email",
    "channel::webwidget": "web_chat",
    "webwidget": "web_chat",
    "web_widget": "web_chat",
    "website": "web_chat",
    "widget": "web_chat",
    "live_chat": "web_chat",
    "web_chat": "web_chat",
    "channel::twiliosms": "sms",
    "twiliosms": "sms",
    "sms": "sms",
    "channel::voice": "voice",
    "phone": "voice",
    "voice": "voice",
    "channel::facebookpage": "facebook",
    "facebookpage": "facebook",
    "facebook": "facebook",
    "messenger": "facebook",
    "channel::instagram": "instagram",
    "instagram": "instagram",
    "channel::whatsapp": "whatsapp",
    "whatsapp": "whatsapp",
    "channel::telegram": "telegram",
    "telegram": "telegram",
    "channel::line": "line",
    "line": "line",
    "channel::api": "api",
    "api": "api",
}

WEB_WIDGET_EVIDENCE_KEYS = {
    "website_token",
    "web_widget",
    "widget",
    "browser",
    "browser_language",
    "referer",
    "referrer",
    "user_agent",
}


def normalize_chatwoot_channel(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    compact = value.strip().lower()
    if not compact:
        return None
    return CHANNEL_ALIASES.get(compact)


def normalized_existing_channel(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip().lower()
    if compact in LEGACY_PROVIDER_CHANNELS:
        return None
    if compact in NORMALIZED_CHANNELS and compact != "unknown":
        return compact
    return normalize_chatwoot_channel(compact)


def _mapping_value(mapping: Mapping[str, object] | None, key: str) -> object | None:
    if mapping is None:
        return None
    return mapping.get(key)


def _mapping_at(mapping: Mapping[str, object] | None, *keys: str) -> object | None:
    current: object = mapping or {}
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _web_widget_evidence(mapping: Mapping[str, object] | None) -> bool:
    if mapping is None:
        return False
    for key, value in mapping.items():
        lowered = key.lower()
        if lowered in WEB_WIDGET_EVIDENCE_KEYS and value:
            return True
        if isinstance(value, Mapping) and _web_widget_evidence(value):
            return True
    return False


def channel_from_payload(
    payload: ChatwootWebhookPayload,
    *,
    existing_channel: str | None = None,
) -> str:
    conversation = payload.conversation or {}
    inbox = payload.inbox or {}

    candidates = [
        _mapping_value(conversation, "channel"),
        _mapping_at(conversation, "meta", "channel"),
        _mapping_value(inbox, "channel_type"),
        _mapping_value(inbox, "medium"),
        _mapping_value(inbox, "provider"),
        _mapping_at(conversation, "inbox", "channel_type"),
        _mapping_at(conversation, "contact_inbox", "inbox", "channel_type"),
        _mapping_at(conversation, "additional_attributes", "channel"),
    ]
    for candidate in candidates:
        normalized = normalize_chatwoot_channel(candidate)
        if normalized:
            return normalized

    preserved = normalized_existing_channel(existing_channel)
    if preserved:
        return preserved

    if _web_widget_evidence(conversation) or _web_widget_evidence(inbox):
        return "web_chat"

    return "unknown"
