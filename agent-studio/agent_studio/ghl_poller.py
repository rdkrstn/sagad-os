"""GHL inbound poller — the "direct inbound, not via webhook" path.

A GHL Private Integration Token (read/send scopes) lets us **poll** the Conversations API; it is
NOT a push channel (GHL's native push is the Marketplace ``InboundMessage`` webhook with an
Ed25519 signature — see ``GhlAdapter`` / ``docs/adapters/ghl.md``). So "skip the webhook, go
straight to GHL" means: run a poller now (env-only creds, no Marketplace app), with the native
webhook a later flip of ``GHL_SIGNATURE_SCHEME=ed25519``.

Reuse, don't duplicate: the poller feeds the SAME ``_run_universal_inbound`` pipeline as the
``/webhooks/ghl`` route. There is no parallel graph path. It reuses ``GhlAdapter.normalize`` /
``ignores``, ``_message_already_recorded`` / ``_universal_conversation_id``, ``store.*``, and
``evaluate_tool_policy`` (transitively, via the shared pipeline). All GHL API calls share one
``httpx.AsyncClient`` per cycle and use the same Bearer + ``Version: 2021-04-15`` headers as
``send_outbound``.

Watermarks live in ``integration_sync_state``: ``payload["last_message_ids"]`` maps
``conversation_id -> lastMessageId`` cursor (the GHL Get-Messages cursor is the source of truth —
the Search-Conversations response does NOT reliably expose ``lastMessageDate``/``lastMessageId``).
``updated_since`` is stamped to the cycle time for observability only. A conversation's cursor is
advanced ONLY after its new messages are successfully persisted, so a mid-cycle crash re-fetches
(and dedup-skips via ``_message_already_recorded``) rather than dropping messages.

Safety: no creds -> skip the cycle; DB not ready -> skip + continue (the lifespan DB-retry task
recovers); 429 -> honor ``Retry-After`` when present else exponential backoff, capped at 60s;
hard caps on conversations-per-cycle and message-pages-per-conversation.

GHL is env-only / single-location today, so the poller runs under a system ``StoreContext`` (the
store resolves the default organization). Per-org GHL via ``integration_connections`` + OAuth is a
later track.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Mapping

import httpx

from agent_studio.adapters import get_adapter
from agent_studio.adapters.ghl import _OUTBOUND_DIRECTIONS
from agent_studio.config import Settings
from agent_studio.db import database_ready
from agent_studio.schemas import IntegrationSyncState
from agent_studio.store import StoreContext, store

_logger = logging.getLogger(__name__)

#: GHL Conversations API version header (same as send_outbound / CRM fetch).
_GHL_API_VERSION = "2021-04-15"
#: Poller watermark row provider key in integration_sync_state.
_PROVIDER = "ghl"
#: Key under sync-state ``payload`` holding the {conversation_id: lastMessageId} cursor map.
_LAST_MESSAGE_IDS_KEY = "last_message_ids"
#: Hard cap on backoff after a 429 / failure (seconds). GHL does not document Retry-After for
#: these endpoints, so we fall back to exponential backoff capped here.
_MAX_BACKOFF_SECONDS = 60.0
#: Safety net: never page a single conversation forever, even if GHL keeps reporting nextPage.
_MAX_PAGES_PER_CONVERSATION = 10


class _RateLimited(Exception):
    """Raised on HTTP 429 to trigger a cycle-level backoff."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"GHL API rate limited; backoff {retry_after:.1f}s")
        self.retry_after = retry_after


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.ghl_api_key}",
        "Accept": "application/json",
        "Version": _GHL_API_VERSION,
    }


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return None


def _system_context() -> StoreContext:
    # GHL is env-only/single-location today; the store resolves the default organization. The
    # system role marks these ingests as non-human (mirrors the webhook route's system context).
    return StoreContext(role="system")


def _retry_after_from(response: httpx.Response, fallback: float) -> float:
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if raw:
        try:
            return min(float(raw), _MAX_BACKOFF_SECONDS)
        except (TypeError, ValueError):
            pass
    return min(fallback, _MAX_BACKOFF_SECONDS)


async def _search_conversations(
    client: httpx.AsyncClient,
    settings: Settings,
) -> list[dict[str, object]]:
    """Enumerate recently-active inbound conversations for the configured location.

    Uses ``GET /conversations/search`` with ``lastMessageDirection=inbound`` + ``status=recents``
    + ``sortBy=last_message_date`` so the most recently active inbound threads come first. The
    Search response does NOT reliably expose ``lastMessageDate``/``lastMessageId`` per
    conversation, so this list is only the candidate set — the per-conversation ``lastMessageId``
    cursor from Get-Messages is the real watermark.
    """
    params = {
        "locationId": settings.ghl_location_id,
        "lastMessageDirection": "inbound",
        "status": "recents",
        "sortBy": "last_message_date",
        "sort": "desc",
        "limit": str(settings.ghl_poll_conversation_limit),
    }
    response = await client.get("/conversations/search", params=params)
    if response.status_code == 429:
        raise _RateLimited(_retry_after_from(response, fallback=float(settings.ghl_poll_interval_seconds)))
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError as exc:
        raise _RateLimited(float(settings.ghl_poll_interval_seconds)) from exc
    conversations = body.get("conversations") if isinstance(body, Mapping) else None
    if not isinstance(conversations, list):
        return []
    return [conv for conv in conversations if isinstance(conv, Mapping)]


async def _fetch_messages_page(
    client: httpx.AsyncClient,
    conversation_id: str,
    cursor: str | None,
    limit: int,
    interval: float,
) -> tuple[list[dict[str, object]], str | None, bool]:
    """Fetch one page of messages after ``cursor``.

    Returns ``(messages, next_cursor, has_more)``. GHL wraps the array under
    ``messages.messages`` (documented bug #54) and reports the next cursor as
    ``messages.lastMessageId`` + ``messages.nextPage``.
    """
    params: dict[str, str] = {"limit": str(limit)}
    if cursor:
        params["lastMessageId"] = cursor
    response = await client.get(f"/conversations/{conversation_id}/messages", params=params)
    if response.status_code == 429:
        raise _RateLimited(_retry_after_from(response, fallback=interval))
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError as exc:
        raise _RateLimited(interval) from exc
    wrapper = body.get("messages") if isinstance(body, Mapping) else None
    if not isinstance(wrapper, Mapping):
        return [], cursor, False
    raw_messages = wrapper.get("messages")
    messages = [m for m in raw_messages if isinstance(m, Mapping)] if isinstance(raw_messages, list) else []
    next_cursor = _as_text(wrapper.get("lastMessageId")) or cursor
    has_more = bool(wrapper.get("nextPage"))
    return messages, next_cursor, has_more


def _build_raw_payload(
    conversation: Mapping[str, object],
    message: Mapping[str, object],
    settings: Settings,
) -> dict[str, object]:
    """Build a payload in the shape ``GhlAdapter.normalize`` reads (the native InboundMessage shape).

    GHL message ``type`` is numeric; ``messageType`` is the string enum (``SMS``, ...). normalize
    reads ``message.type`` for the channel, so we feed ``messageType`` there to land on a real
    channel like ``sms``.
    """
    contact_id = _as_text(message.get("contactId")) or _as_text(conversation.get("contactId"))
    contact_name = _as_text(conversation.get("fullName")) or _as_text(conversation.get("contactName"))
    return {
        "type": "InboundMessage",
        "conversationId": _as_text(conversation.get("id")),
        "locationId": settings.ghl_location_id,
        "message": {
            "id": _as_text(message.get("id")),
            "body": _as_text(message.get("body")) or "",
            "direction": _as_text(message.get("direction")) or "inbound",
            "type": _as_text(message.get("messageType")) or "SMS",
        },
        "contact": {"id": contact_id, "name": contact_name or "GHL contact"},
    }


class GhlPoller:
    """Background GHL inbound poller. Started from the app lifespan when ``ghl_poll_enabled``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def _resolved_settings(self) -> Settings:
        """DB-backed GHL config (superadmin console) over env, refreshed each cycle.

        ``context=system`` resolves the default organization (single-location GHL today).
        Env is the fallback when no ``ghl`` row is stored, so env-only deployments keep
        working unchanged.
        """
        from agent_studio.config import get_settings
        from agent_studio.integration_config import configured_settings

        return configured_settings(get_settings(), context=_system_context())

    async def run(self) -> None:
        interval = max(1.0, float(self._resolved_settings().ghl_poll_interval_seconds))
        consecutive_failures = 0
        _logger.info("GHL inbound poller started (interval=%.1fs).", interval)
        while not self._stop.is_set():
            wait = interval
            try:
                ingested = await self._cycle()
                consecutive_failures = 0
                if ingested:
                    _logger.info("GHL poller ingested %d inbound message(s).", ingested)
            except _RateLimited as exc:
                consecutive_failures = 0
                wait = exc.retry_after
                self._diagnostic(
                    "ghl.poller.rate_limited",
                    f"GHL poller rate limited; backing off {wait:.1f}s.",
                    status_value="warning",
                    payload={"retry_after": wait},
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a poller tick must never kill the loop
                consecutive_failures += 1
                backoff = min(interval * (2 ** min(consecutive_failures, 5)), _MAX_BACKOFF_SECONDS)
                wait = backoff
                _logger.warning("GHL poller cycle failed (%s); backing off %.1fs.", exc.__class__.__name__, wait)
                self._diagnostic(
                    "ghl.poller.cycle_failed",
                    f"GHL poller cycle failed: {exc.__class__.__name__}.",
                    status_value="warning",
                    payload={"backoff": wait, "consecutive_failures": consecutive_failures},
                )
            # Interruptible sleep so stop() takes effect promptly.
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass
        _logger.info("GHL inbound poller stopped.")

    async def _cycle(self) -> int:
        # Lazy imports keep this module importable from main.lifespan without a circular import,
        # and preserve the tests' `patch("agent_studio.main.graph.ainvoke", ...)` pattern (the
        # poller drives the SAME pipeline as the webhook route, so the same graph object is hit).
        from agent_studio.main import (
            _message_already_recorded,
            _record_diagnostic_event,
            _run_universal_inbound,
            _universal_conversation_id,
        )

        settings = self._resolved_settings()
        if not settings.ghl_configured:
            # No creds -> nothing to poll. Skip silently (not a failure; the loop continues).
            return 0
        db_ready, detail = database_ready(settings)
        if not db_ready:
            self._diagnostic(
                "ghl.poller.db_not_ready",
                "GHL poller skipped: database not ready.",
                status_value="info",
                payload={"detail": detail},
            )
            return 0

        context = _system_context()
        adapter = get_adapter("ghl")
        sync_state = store.get_sync_state(_PROVIDER, context=context) or IntegrationSyncState(
            provider=_PROVIDER, payload={}
        )
        payload = dict(sync_state.payload or {})
        last_message_ids: dict[str, str] = dict(payload.get(_LAST_MESSAGE_IDS_KEY, {}))

        interval = max(1.0, float(settings.ghl_poll_interval_seconds))
        ingested = 0
        base_url = str(settings.ghl_base_url).rstrip("/")
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=float(settings.ghl_poll_timeout_seconds),
            headers=_headers(settings),
        ) as client:
            conversations = await _search_conversations(client, settings)
            # Hard cap per cycle (the search limit already bounds this, but cap defensively).
            for conversation in conversations[: settings.ghl_poll_conversation_limit]:
                if self._stop.is_set():
                    break
                conv_id = _as_text(conversation.get("id"))
                if not conv_id:
                    continue
                cursor = last_message_ids.get(conv_id)
                new_cursor = cursor
                conv_ingested = 0
                for _page in range(_MAX_PAGES_PER_CONVERSATION):
                    messages, page_cursor, has_more = await _fetch_messages_page(
                        client,
                        conv_id,
                        new_cursor,
                        settings.ghl_poll_message_limit,
                        interval,
                    )
                    for message in messages:
                        direction = (_as_text(message.get("direction")) or "").lower()
                        if direction in _OUTBOUND_DIRECTIONS:
                            continue  # only inbound customer messages; reuse the adapter's set
                        raw_payload = _build_raw_payload(conversation, message, settings)
                        normalized = adapter.normalize(raw_payload)
                        if adapter.ignores(normalized):
                            continue
                        conversation_id = _universal_conversation_id(normalized)
                        existing = store.get(conversation_id, context=context) if conversation_id else None
                        if _message_already_recorded(existing, normalized.provider_message_id):
                            _record_diagnostic_event(
                                event_type="ghl.poller.duplicate_skipped",
                                summary="GHL poller skipped an already-recorded message.",
                                status_value="info",
                                conversation_id=conversation_id,
                                payload={"provider_message_id": normalized.provider_message_id},
                                context=context,
                            )
                            continue
                        await _run_universal_inbound(
                            adapter, normalized, context=context, settings=settings
                        )
                        ingested += 1
                        conv_ingested += 1
                    new_cursor = page_cursor or new_cursor
                    if not messages or not has_more:
                        break
                # Advance this conversation's watermark only after its new messages persisted.
                if new_cursor and new_cursor != cursor:
                    last_message_ids[conv_id] = new_cursor
                    payload[_LAST_MESSAGE_IDS_KEY] = last_message_ids
                    sync_state.payload = payload
                    sync_state.updated_since = int(time.time() * 1000)
                    store.save_sync_state(sync_state, context=context)
        return ingested

    def _diagnostic(
        self,
        event_type: str,
        summary: str,
        *,
        status_value: str = "info",
        payload: dict[str, object] | None = None,
    ) -> None:
        # Lazy import to avoid the circular main <-> ghl_poller edge at module load.
        from agent_studio.main import _record_diagnostic_event

        try:
            _record_diagnostic_event(
                event_type=event_type,
                summary=summary,
                status_value=status_value,
                payload=payload,
                context=_system_context(),
            )
        except Exception:  # noqa: BLE001 - diagnostics must never break the poller
            _logger.warning("GHL poller failed to record diagnostic %s.", event_type)


async def run_ghl_poller(settings: Settings) -> GhlPoller:
    """Start a GHL poller for the given settings. Returns the handle so the lifespan can stop it."""
    poller = GhlPoller(settings)
    asyncio.create_task(poller.run())
    return poller