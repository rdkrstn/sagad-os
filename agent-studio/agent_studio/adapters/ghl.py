"""GoHighLevel (GHL) channel adapter.

Inbound: GHL Workflow/Custom Webhook delivers a message event. We verify the HMAC-SHA256
signature of the raw body with `GHL_WEBHOOK_SECRET` (header `X-GHL-Signature`), then normalize
the payload to `NormalizedInbound`.

Outbound: an approved/auto reply is sent back to GHL. Two modes, selected by
`GHL_OUTBOUND_MODE` (per-adapter config):
  * "webhook" — POST to the GHL conversations/messages API (working).
  * "mcp"     — auto-send via an MCP tool descriptor (executor stubbed for now; returns
                dry_run with a clear note. Full MCP execution is a follow-up).

GHL does not publish one canonical inbound payload — the shape is workflow-configurable — so
`normalize()` reads defensively across the common key paths. The expected shape is documented
in `docs/adapters/ghl.md`.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Mapping

import httpx

from agent_studio.adapters.base import ChannelAdapter, NormalizedInbound, SendResult

_logger = logging.getLogger(__name__)

#: GHL message-direction values that are NOT inbound customer messages.
_OUTBOUND_DIRECTIONS = {"outbound", "sent", "outgoing"}
#: Header names GHL may use to carry the HMAC signature (checked in order).
_SIGNATURE_HEADERS = ("x-ghl-signature", "webhook-signature", "x-signature")
#: GHL API version header expected by the conversations/messages endpoint.
_GHL_API_VERSION = "2021-04-15"


def _constant_time_hex_eq(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left.lower().encode(), right.lower().encode())


def _hmac_sha256_hex(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return None


def _at(mapping: Mapping[str, object] | None, *keys: str) -> object | None:
    current: object = mapping or {}
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


class GhlAdapter(ChannelAdapter):
    name = "ghl"
    outbound_modes = ["webhook", "mcp"]

    def verify_inbound(self, raw_body: bytes, headers: Mapping[str, str]) -> None:
        from fastapi import HTTPException

        settings = _settings()
        secret = settings.ghl_webhook_secret
        # No secret configured -> verification is a no-op (dev/test mode). In production set
        # GHL_WEBHOOK_SECRET so inbound is authenticated.
        if not secret:
            return
        supplied = None
        lower_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        for header in _SIGNATURE_HEADERS:
            if header in lower_headers and lower_headers[header]:
                supplied = lower_headers[header]
                break
        if not supplied:
            raise HTTPException(status_code=401, detail="Missing GHL webhook signature.")
        expected = _hmac_sha256_hex(secret, raw_body)
        if not _constant_time_hex_eq(supplied, expected):
            raise HTTPException(status_code=401, detail="Invalid GHL webhook signature.")

    def normalize(self, raw_payload: dict[str, object]) -> NormalizedInbound:
        message = _at(raw_payload, "message") if isinstance(raw_payload, Mapping) else None
        contact = _at(raw_payload, "contact")

        conversation_id = _as_text(_at(raw_payload, "conversationId")) or _as_text(
            _at(raw_payload, "conversation", "id")
        )
        message_id = _as_text(_at(message, "id")) if isinstance(message, Mapping) else _as_text(
            raw_payload.get("messageId") if isinstance(raw_payload, Mapping) else None
        )
        message_text = (
            _as_text(_at(message, "body"))
            or _as_text(_at(message, "text"))
            or _as_text(raw_payload.get("body") if isinstance(raw_payload, Mapping) else None)
            or _as_text(_at(raw_payload, "messageBody"))
            or ""
        )
        customer_name = (
            _as_text(_at(contact, "name"))
            or _as_text(_at(contact, "firstName"))
            or _as_text(_at(raw_payload, "contactName"))
            or "GHL contact"
        )
        channel = _as_text(_at(message, "type")) or _as_text(raw_payload.get("channel")) or "ghl"
        event_type = _as_text(raw_payload.get("type")) if isinstance(raw_payload, Mapping) else None
        location_id = _as_text(_at(raw_payload, "locationId")) or _as_text(_at(raw_payload, "location", "id"))

        return NormalizedInbound(
            provider="ghl",
            provider_conversation_id=conversation_id,
            provider_message_id=message_id,
            customer_name=customer_name,
            channel=str(channel).lower() or "ghl",
            message_text=message_text,
            event_type=event_type,
            raw_payload=raw_payload if isinstance(raw_payload, dict) else {},
            extra={"location_id": location_id} if location_id else {},
        )

    def ignores(self, normalized: NormalizedInbound) -> bool:
        message = _at(normalized.raw_payload, "message")
        direction = _as_text(_at(message, "direction")) if isinstance(message, Mapping) else None
        if direction and direction.lower() in _OUTBOUND_DIRECTIONS:
            return True
        if normalized.event_type and normalized.event_type.lower() in {"outboundmessage", "outbound"}:
            return True
        return False

    async def send_outbound(
        self,
        reply: str,
        normalized: NormalizedInbound,
        settings: Any,
    ) -> SendResult:
        action = "ghl.messages.send"
        if not settings.ghl_configured:
            return SendResult(
                status="dry_run",
                provider="GHL",
                action=action,
                detail="GHL credentials are not fully configured; send stayed in dry-run.",
            )

        conversation_id = normalized.provider_conversation_id
        if not conversation_id:
            return SendResult(
                status="failed",
                provider="GHL",
                action=action,
                detail="Missing GHL conversation id; cannot route outbound reply.",
            )

        if settings.ghl_outbound_mode.lower() == "mcp":
            # MCP auto-send executor is a follow-up; surface a clear, honest status rather
            # than silently no-op'ing. Configure GHL_OUTBOUND_MODE=webhook to send live.
            return SendResult(
                status="dry_run",
                provider="GHL",
                action=action,
                detail="GHL MCP auto-send executor is not wired yet; set GHL_OUTBOUND_MODE=webhook to send.",
            )

        base_url = str(settings.ghl_base_url).rstrip("/")
        url = f"{base_url}/conversations/{conversation_id}/messages"

        if settings.ghl_dry_run:
            return SendResult(
                status="dry_run",
                provider="GHL",
                action=action,
                target_url=url,
                detail="GHL credentials are configured, but dry-run is enabled.",
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.ghl_api_key}",
                        "Version": _GHL_API_VERSION,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={"type": "SMS", "message": reply},
                )
        except httpx.TimeoutException as exc:
            return SendResult(
                status="failed",
                provider="GHL",
                action=action,
                target_url=url,
                error_type=exc.__class__.__name__,
                detail="GHL send timed out before a response was received.",
            )
        except httpx.RequestError as exc:
            return SendResult(
                status="failed",
                provider="GHL",
                action=action,
                target_url=url,
                error_type=exc.__class__.__name__,
                detail=f"GHL send failed before receiving an HTTP response: {exc.__class__.__name__}.",
            )

        if response.is_success:
            external_id: str | None = None
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, dict):
                id_value = body.get("id") or _at(body, "message", "id")
                external_id = str(id_value) if id_value is not None else None
            result = SendResult(
                status="sent",
                provider="GHL",
                action=action,
                target_url=url,
                http_status=response.status_code,
                detail="Approved reply sent to GHL.",
            )
            if external_id:
                result["external_id"] = external_id
            return result

        return SendResult(
            status="failed",
            provider="GHL",
            action=action,
            target_url=url,
            http_status=response.status_code,
            detail=f"GHL send failed with HTTP {response.status_code}.",
        )


def _settings():
    # Local import to avoid pulling config at module import time (test isolation).
    from agent_studio.config import get_settings

    return get_settings()