"""GHL inbound poller tests.

The poller roundtrip is pytest-only: GHL API calls are stubbed with a fake ``httpx.AsyncClient``
(MockTransport-shaped) so no real GHL credentials or network are touched. The poller feeds the
SAME ``_run_universal_inbound`` pipeline as the ``/webhooks/ghl`` route, so we mock
``agent_studio.main._run_universal_inbound`` (and rely on the real ``_message_already_recorded`` +
InMemory store) to assert ingest/dedup/watermark behavior without invoking the graph.

Covers: one ingest per inbound message (outbound filtered), watermark advances on success only,
dedup skip, 429 backoff, no-creds skip, DB-not-ready skip, and the stop signal.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_studio.config import Settings
from agent_studio.ghl_poller import GhlPoller, _RateLimited
from agent_studio.integration_config import integration_config_store
from agent_studio.store import store


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = dict(
        ghl_api_key="key-123",
        ghl_location_id="loc-1",
        ghl_base_url="https://services.leadconnectorhq.com",
        ghl_outbound_mode="webhook",
        ghl_dry_run=True,
        ghl_poll_interval_seconds=30,
        ghl_poll_conversation_limit=50,
        ghl_poll_message_limit=20,
    )
    base.update(overrides)
    return Settings(**base)


class _Resp:
    """Minimal httpx.Response stand-in (status, json, headers, raise_for_status)."""

    def __init__(self, status_code: int, body: Any, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.is_success = status_code < 400
        self._body = body
        self.headers = headers or {}

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=httpx.Request("GET", "https://x"), response=None  # type: ignore[arg-type]
            )


def _conv(conv_id: str = "conv-1", contact_id: str = "cont-1", name: str = "Jane Doe") -> dict[str, Any]:
    return {"id": conv_id, "contactId": contact_id, "fullName": name}


def _msg(msg_id: str, direction: str = "inbound", body: str = "Hi") -> dict[str, Any]:
    return {"id": msg_id, "body": body, "direction": direction, "messageType": "SMS", "contactId": "cont-1"}


def _messages_body(messages: list[dict[str, Any]], last_id: str, has_more: bool = False) -> dict[str, Any]:
    return {"messages": {"lastMessageId": last_id, "nextPage": has_more, "messages": messages}}


def _patch_httpx(handler: Any) -> Any:
    """Patch ``httpx.AsyncClient`` in ghl_poller so ``async with`` yields a client whose ``get``
    dispatches to ``handler(url, *, params=...)`` and returns a ``_Resp``."""
    inner = MagicMock()
    inner.get = AsyncMock(side_effect=handler)
    outer = MagicMock()
    outer.__aenter__ = AsyncMock(return_value=inner)
    outer.__aexit__ = AsyncMock(return_value=None)
    return patch("agent_studio.ghl_poller.httpx.AsyncClient", return_value=outer)


def setup_function() -> None:
    store.clear()
    # The poller resolves GHL config via `configured_settings`, which overlays the
    # integration_config store. Clear it so leftover rows from other test modules can't
    # flip ghl_configured or override the env-style settings each test builds via _settings().
    integration_config_store.clear()


@pytest.mark.asyncio
async def test_poller_ingests_inbound_only_and_advances_watermark() -> None:
    settings = _settings()
    poller = GhlPoller(settings)

    def handler(url: str, *, params: Any = None) -> _Resp:
        if "search" in url:
            return _Resp(200, {"conversations": [_conv()], "total": 1})
        # /conversations/{id}/messages: one inbound + one outbound; cursor advances to msg-b.
        return _Resp(200, _messages_body([_msg("msg-a", "inbound"), _msg("msg-b", "outbound")], "msg-b"))

    run_mock = AsyncMock(return_value=None)
    with _patch_httpx(handler), patch("agent_studio.main._run_universal_inbound", new=run_mock):
        ingested = await poller._cycle()

    # Only the inbound message reached the shared pipeline; the outbound one was filtered.
    assert ingested == 1
    assert run_mock.await_count == 1
    normalized = run_mock.await_args.args[1]
    assert normalized.provider_conversation_id == "conv-1"
    assert normalized.provider_message_id == "msg-a"
    # Watermark advanced to the page's lastMessageId only after the successful persist.
    state = store.get_sync_state("ghl")
    assert state is not None
    assert state.payload["last_message_ids"]["conv-1"] == "msg-b"
    assert state.updated_since > 0


@pytest.mark.asyncio
async def test_poller_dedup_skips_already_recorded() -> None:
    from agent_studio.adapters import get_adapter
    from agent_studio.main import _universal_conversation_id

    settings = _settings()
    poller = GhlPoller(settings)

    # Pre-seed the store with a record that already carries msg-a (e.g. delivered out-of-band by
    # the webhook route) so the poller must dedup-skip it rather than re-ingest.
    adapter = get_adapter("ghl")
    normalized = adapter.normalize(
        {
            "type": "InboundMessage",
            "conversationId": "conv-1",
            "locationId": "loc-1",
            "message": {"id": "msg-a", "body": "Hi", "direction": "inbound", "type": "SMS"},
            "contact": {"id": "cont-1", "name": "Jane Doe"},
        }
    )
    conv_id = _universal_conversation_id(normalized)
    from agent_studio.schemas import ConversationMessageRecord, ConversationRecord

    store.save(
        ConversationRecord(
            id=conv_id,
            incoming_message="Hi",
            draft_reply="",
            messages=[
                ConversationMessageRecord(
                    sender_type="customer",
                    body="Hi",
                    external_message_id="msg-a",
                    provider="ghl",
                )
            ],
        )
    )

    def handler(url: str, *, params: Any = None) -> _Resp:
        if "search" in url:
            return _Resp(200, {"conversations": [_conv()], "total": 1})
        return _Resp(200, _messages_body([_msg("msg-a", "inbound")], "msg-a"))

    run_mock = AsyncMock(return_value=None)
    diag_mock = MagicMock()
    with _patch_httpx(handler), patch("agent_studio.main._run_universal_inbound", new=run_mock), \
            patch("agent_studio.main._record_diagnostic_event", new=diag_mock):
        ingested = await poller._cycle()

    assert ingested == 0
    run_mock.assert_not_called()
    # A poller-specific duplicate diagnostic was emitted.
    event_types = [call.kwargs.get("event_type") for call in diag_mock.call_args_list]
    assert "ghl.poller.duplicate_skipped" in event_types


@pytest.mark.asyncio
async def test_poller_429_raises_rate_limited_with_retry_after() -> None:
    settings = _settings()
    poller = GhlPoller(settings)

    def handler(url: str, *, params: Any = None) -> _Resp:
        return _Resp(429, {}, headers={"Retry-After": "2"})

    with _patch_httpx(handler):
        with pytest.raises(_RateLimited) as exc:
            await poller._cycle()
    assert exc.value.retry_after == 2.0


@pytest.mark.asyncio
async def test_poller_no_credentials_skips_silently() -> None:
    settings = _settings(ghl_api_key=None)  # ghl_configured is False
    poller = GhlPoller(settings)

    with patch("agent_studio.ghl_poller.httpx.AsyncClient") as mock_client:
        ingested = await poller._cycle()

    assert ingested == 0
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_poller_skips_when_database_not_ready() -> None:
    settings = _settings()
    poller = GhlPoller(settings)

    with patch("agent_studio.ghl_poller.database_ready", return_value=(False, "down")), \
            patch("agent_studio.ghl_poller.httpx.AsyncClient") as mock_client:
        ingested = await poller._cycle()

    assert ingested == 0
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_poller_stop_signal_terminates_loop() -> None:
    # No creds -> each cycle is a fast no-op, then the loop sleeps the interval. Signalling stop
    # makes the interruptible sleep (asyncio.wait_for on the stop event) return immediately, so
    # run() exits promptly rather than waiting out the interval.
    settings = _settings(ghl_api_key=None, ghl_poll_interval_seconds=1)
    poller = GhlPoller(settings)

    import asyncio

    task = asyncio.create_task(poller.run())
    poller.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()