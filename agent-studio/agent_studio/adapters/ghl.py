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

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Mapping

import httpx

from agent_studio.adapters.base import ChannelAdapter, NormalizedInbound, SendResult
from agent_studio.schemas import CrmContactContext

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


def _decode_key_or_sig(value: str) -> bytes | None:
    """Decode an Ed25519 public key or signature that GHL delivers as hex or base64."""
    value = value.strip()
    try:
        return bytes.fromhex(value)
    except ValueError:
        pass
    try:
        import base64

        return base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None


class GhlSignatureVerifier:
    """Verifies a GHL inbound webhook signature. No-op when no secret is configured (dev/test)."""

    def verify(self, raw_body: bytes, headers: Mapping[str, str], settings: Any) -> None:
        raise NotImplementedError


class HmacGhlVerifier(GhlSignatureVerifier):
    """HMAC-SHA256 over the raw body (X-GHL-Signature / webhook-signature / x-signature).

    The default scheme for GHL Workflow/Custom webhooks; behavior is unchanged from the
    original single-implementation verify_inbound.
    """

    def verify(self, raw_body: bytes, headers: Mapping[str, str], settings: Any) -> None:
        from fastapi import HTTPException

        secret = settings.ghl_webhook_secret
        if not secret:
            return
        lower_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        supplied = None
        for header in _SIGNATURE_HEADERS:
            if header in lower_headers and lower_headers[header]:
                supplied = lower_headers[header]
                break
        if not supplied:
            raise HTTPException(status_code=401, detail="Missing GHL webhook signature.")
        expected = _hmac_sha256_hex(secret, raw_body)
        if not _constant_time_hex_eq(supplied, expected):
            raise HTTPException(status_code=401, detail="Invalid GHL webhook signature.")


class Ed25519GhlVerifier(GhlSignatureVerifier):
    """Ed25519 over the raw body (x-wh-signature) -- GHL's native InboundMessage webhook.

    Activates only when GHL_SIGNATURE_SCHEME=ed25519. The verification public key is the one
    GHL shows when you subscribe the native webhook (set via GHL_NATIVE_WEBHOOK_KEY, hex or
    base64). cryptography is imported lazily so the default HMAC path stays dependency-light.
    """

    _SIGNATURE_HEADER = "x-wh-signature"

    def verify(self, raw_body: bytes, headers: Mapping[str, str], settings: Any) -> None:
        from fastapi import HTTPException

        public_key_str = settings.ghl_native_webhook_key
        # No key configured -> verification is a no-op (dev/test mode), matching HMAC behavior.
        if not public_key_str:
            return
        lower_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        supplied = lower_headers.get(self._SIGNATURE_HEADER)
        if not supplied:
            raise HTTPException(status_code=401, detail="Missing GHL native webhook signature.")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError as exc:  # pragma: no cover - cryptography is a transitive dep
            raise HTTPException(
                status_code=500,
                detail="GHL Ed25519 verification requires the 'cryptography' package.",
            ) from exc
        key_bytes = _decode_key_or_sig(public_key_str)
        sig_bytes = _decode_key_or_sig(supplied)
        if key_bytes is None or sig_bytes is None:
            raise HTTPException(status_code=401, detail="Malformed GHL Ed25519 key or signature.")
        try:
            Ed25519PublicKey.from_public_bytes(key_bytes).verify(sig_bytes, raw_body)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid GHL webhook signature.") from exc


_GHL_VERIFIERS: dict[str, GhlSignatureVerifier] = {
    "hmac": HmacGhlVerifier(),
    "ed25519": Ed25519GhlVerifier(),
}


#: TTL for the in-process CRM-context cache (keyed by GHL contact id). Keeps a hot thread from
#: refetching the same contact/opportunity on every inbound message.
_CRM_CACHE_TTL_SECONDS = 300.0
#: Hard cap on a single CRM-context fetch so a slow GHL API can never block inbound processing.
_CRM_FETCH_TIMEOUT_SECONDS = 8.0
# contact_id -> (expiry_monotonic, CrmContactContext)
_crm_context_cache: dict[str, tuple[float, CrmContactContext]] = {}


def _clear_crm_context_cache() -> None:
    """Test hook: drop the in-process CRM-context cache."""
    _crm_context_cache.clear()


def _mask_secret(value: str | None, *, keep_head: int = 2) -> str | None:
    """Mask a phone/email for safe display in CRM context (e.g. '+1***23')."""
    if not value:
        return None
    text = str(value)
    if len(text) <= keep_head:
        return "***"
    return f"{text[:keep_head]}***{text[-2:]}"


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
        settings = _settings()
        # Dispatch on the configured signature scheme. "hmac" (default) is the GHL Workflow/
        # Custom webhook path; "ed25519" is the native InboundMessage webhook (Marketplace/OAuth
        # app). Unknown schemes fall back to HMAC so a misconfigured env never disables auth.
        scheme = (settings.ghl_signature_scheme or "hmac").lower()
        verifier = _GHL_VERIFIERS.get(scheme, _GHL_VERIFIERS["hmac"])
        verifier.verify(raw_body, headers, settings)

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

    async def fetch_crm_context(
        self,
        normalized: NormalizedInbound,
        settings: Any,
    ) -> CrmContactContext | None:
        """Read-only GHL CRM context (contact + first opportunity) for an inbound contact.

        Never raises and never blocks inbound: the fetch is wrapped in an 8s ``asyncio.wait_for``
        plus a broad ``except`` so any timeout/HTTP/parse failure returns ``None`` and the graph
        proceeds without CRM context. Results are cached per ``contact_id`` for 5 minutes so a
        hot thread does not refetch on every message. Only runs when GHL is configured; this is
        strictly read-only -- no CRM writes are ever performed.
        """
        if not getattr(settings, "ghl_configured", False):
            return None
        contact_id = _as_text(_at(normalized.raw_payload, "contact", "id"))
        if not contact_id:
            return None
        now = time.monotonic()
        cached = _crm_context_cache.get(contact_id)
        if cached and cached[0] > now:
            return cached[1]
        try:
            context = await asyncio.wait_for(
                self._fetch_crm_context(contact_id, settings),
                timeout=_CRM_FETCH_TIMEOUT_SECONDS,
            )
        except Exception:  # never let a CRM fetch block or break inbound
            _logger.warning("GHL CRM context fetch failed for contact %s; degrading to None.", contact_id)
            return None
        if context is not None:
            _crm_context_cache[contact_id] = (now + _CRM_CACHE_TTL_SECONDS, context)
        return context

    async def _fetch_crm_context(self, contact_id: str, settings: Any) -> CrmContactContext | None:
        base_url = str(settings.ghl_base_url).rstrip("/")
        headers = {
            "Authorization": f"Bearer {settings.ghl_api_key}",
            "Version": _GHL_API_VERSION,
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=_CRM_FETCH_TIMEOUT_SECONDS) as client:
                contact_resp = await client.get(f"{base_url}/contacts/{contact_id}", headers=headers)
                contact_payload: object = None
                if contact_resp.is_success:
                    try:
                        body = contact_resp.json()
                    except ValueError:
                        body = None
                    contact_payload = body.get("contact") if isinstance(body, Mapping) else body
                # GHL's opportunity search is a POST with a contact_id/location_id body.
                opportunities: list[Mapping[str, object]] = []
                try:
                    opp_resp = await client.post(
                        f"{base_url}/opportunities/search",
                        headers={**headers, "Content-Type": "application/json"},
                        json={"location_id": settings.ghl_location_id, "contact_id": contact_id},
                    )
                    if opp_resp.is_success:
                        opp_body = opp_resp.json()
                        raw_opps = opp_body.get("opportunities") if isinstance(opp_body, Mapping) else None
                        if isinstance(raw_opps, list):
                            opportunities = [o for o in raw_opps if isinstance(o, Mapping)]
                except (httpx.RequestError, ValueError):
                    opportunities = []
        except httpx.RequestError:
            return None
        if not isinstance(contact_payload, Mapping):
            # No contact found -> nothing useful to attach; degrade rather than fabricate.
            return None
        opp = opportunities[0] if opportunities else None
        company_name = _as_text(_at(contact_payload, "companyName")) or _as_text(
            _at(contact_payload, "company", "name")
        )
        tags_raw = contact_payload.get("tags")
        tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []
        return CrmContactContext(
            provider="GHL",
            status="ready",
            contact_id=str(contact_payload.get("id") or contact_id),
            display_name=_as_text(_at(contact_payload, "name")) or _as_text(_at(contact_payload, "firstName")),
            company_name=company_name,
            phone_masked=_mask_secret(_as_text(_at(contact_payload, "phone"))),
            email_masked=_mask_secret(_as_text(_at(contact_payload, "email"))),
            tags=tags,
            deal_stage=_as_text(_at(opp, "pipelineStage", "name")) or _as_text(_at(opp, "status")) if opp else None,
            deal_value=_as_text(_at(opp, "monetaryValue")) if opp else None,
            raw={"contact": dict(contact_payload), "opportunities": [dict(o) for o in opportunities]},
        )

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
            # The Agent Studio MCP gateway is descriptor-only by design (mcp_gateway.py
            # builds redacted tool descriptors; it has no execution runtime and exposes no
            # provider credentials). So MCP-mode outbound is an honest dry-run that names
            # the descriptor the supervisor WOULD invoke once an executor exists, rather
            # than silently no-op'ing or fabricating a send. Set GHL_OUTBOUND_MODE=webhook
            # to send live today; an MCP executor is a tracked follow-up (see docs/adapters/ghl.md).
            return SendResult(
                status="dry_run",
                provider="GHL",
                action=action,
                target_url=f"mcp://ghl.messages.send?conversationId={conversation_id}",
                detail=(
                    "GHL MCP outbound is descriptor-only (no executor runtime yet); "
                    "not sent. Set GHL_OUTBOUND_MODE=webhook to send live."
                ),
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