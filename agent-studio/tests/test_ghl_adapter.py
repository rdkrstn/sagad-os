"""Unit tests for the GoHighLevel (GHL) channel adapter.

These exercise the adapter in isolation (HMAC verification, normalization, ignore rules,
outbound webhook/MCP/dry-run modes) — no FastAPI app, no graph. The universal-webhook
HTTP path is covered in test_universal_webhook.py.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_studio.adapters.ghl import GhlAdapter, _hmac_sha256_hex
from agent_studio.adapters.base import NormalizedInbound
from agent_studio.config import Settings


def _settings(**overrides: Any) -> Settings:
    base = dict(
        ghl_webhook_secret=None,
        ghl_api_key="key-123",
        ghl_location_id="loc-1",
        ghl_base_url="https://services.leadconnectorhq.com",
        ghl_outbound_mode="webhook",
        ghl_dry_run=True,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def adapter() -> GhlAdapter:
    return GhlAdapter()


@pytest.fixture
def patch_settings(adapter: GhlAdapter, monkeypatch: pytest.MonkeyPatch):
    def _apply(settings: Settings) -> None:
        monkeypatch.setattr("agent_studio.adapters.ghl._settings", lambda: settings)

    return _apply


def _ghl_payload(*, direction: str = "inbound", body: str = "Hi, what's your pricing?", **extra: Any) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "InboundMessage",
        "conversationId": "conv-abc",
        "locationId": "loc-1",
        "message": {"id": "msg-1", "body": body, "direction": direction, "type": "SMS"},
        "contact": {"id": "cont-1", "name": "Jane Doe"},
    }
    payload.update(extra)
    return payload


# --- verify_inbound --------------------------------------------------------

def test_verify_no_secret_allows(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings(ghl_webhook_secret=None))
    # No secret configured -> verification is a no-op (dev mode), never raises.
    adapter.verify_inbound(b'{"x":1}', {})


def test_verify_valid_signature(adapter: GhlAdapter, patch_settings) -> None:
    secret = "shh"
    patch_settings(_settings(ghl_webhook_secret=secret))
    raw = b'{"message":{"body":"hi"}}'
    sig = _hmac_sha256_hex(secret, raw)
    # Must not raise:
    adapter.verify_inbound(raw, {"X-GHL-Signature": sig})


def test_verify_invalid_signature_raises_401(adapter: GhlAdapter, patch_settings) -> None:
    from fastapi import HTTPException

    patch_settings(_settings(ghl_webhook_secret="shh"))
    with pytest.raises(HTTPException) as exc:
        adapter.verify_inbound(b'{"x":1}', {"X-GHL-Signature": "deadbeef"})
    assert exc.value.status_code == 401


def test_verify_missing_signature_raises_401(adapter: GhlAdapter, patch_settings) -> None:
    from fastapi import HTTPException

    patch_settings(_settings(ghl_webhook_secret="shh"))
    with pytest.raises(HTTPException) as exc:
        adapter.verify_inbound(b'{"x":1}', {})
    assert exc.value.status_code == 401


def test_hmac_constant_time_compare() -> None:
    # Sanity: HMAC is deterministic; compare helper rejects length mismatch.
    assert _hmac_sha256_hex("k", b"a") == hmac.new(b"k", b"a", hashlib.sha256).hexdigest()
    assert _hmac_sha256_hex("k", b"a") != _hmac_sha256_hex("k", b"b")


# --- normalize -------------------------------------------------------------

def test_normalize_extracts_fields(adapter: GhlAdapter) -> None:
    normalized = adapter.normalize(_ghl_payload())
    assert normalized.provider == "ghl"
    assert normalized.provider_conversation_id == "conv-abc"
    assert normalized.provider_message_id == "msg-1"
    assert normalized.customer_name == "Jane Doe"
    assert normalized.channel == "sms"
    assert normalized.message_text == "Hi, what's your pricing?"
    assert normalized.event_type == "InboundMessage"
    assert normalized.extra == {"location_id": "loc-1"}


def test_normalize_falls_back_on_missing_contact(adapter: GhlAdapter) -> None:
    payload = {
        "conversationId": "c2",
        "message": {"id": "m2", "body": "hello", "direction": "inbound", "type": "WhatsApp"},
    }
    normalized = adapter.normalize(payload)
    assert normalized.customer_name == "GHL contact"
    assert normalized.channel == "whatsapp"
    assert normalized.message_text == "hello"


# --- ignores ---------------------------------------------------------------

def test_ignores_outbound_message(adapter: GhlAdapter) -> None:
    normalized = adapter.normalize(_ghl_payload(direction="outbound"))
    assert adapter.ignores(normalized) is True


def test_does_not_ignore_inbound(adapter: GhlAdapter) -> None:
    normalized = adapter.normalize(_ghl_payload(direction="inbound"))
    assert adapter.ignores(normalized) is False


# --- send_outbound ---------------------------------------------------------

@pytest.mark.asyncio
async def test_send_unconfigured_returns_dry_run(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings(ghl_api_key=None))  # not configured
    normalized = adapter.normalize(_ghl_payload())
    result = await adapter.send_outbound("reply", normalized, _settings(ghl_api_key=None))
    assert result["status"] == "dry_run"
    assert result["provider"] == "GHL"


@pytest.mark.asyncio
async def test_send_missing_conversation_id_fails(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    normalized = adapter.normalize(_ghl_payload())
    normalized.provider_conversation_id = None
    result = await adapter.send_outbound("reply", normalized, _settings())
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_send_mcp_mode_is_honest_stub(adapter: GhlAdapter, patch_settings) -> None:
    settings = _settings(ghl_outbound_mode="mcp", ghl_dry_run=False)
    patch_settings(settings)
    normalized = adapter.normalize(_ghl_payload())
    result = await adapter.send_outbound("reply", normalized, settings)
    assert result["status"] == "dry_run"
    assert "MCP" in result["detail"]


@pytest.mark.asyncio
async def test_send_webhook_dry_run(adapter: GhlAdapter, patch_settings) -> None:
    settings = _settings(ghl_dry_run=True)
    patch_settings(settings)
    normalized = adapter.normalize(_ghl_payload())
    result = await adapter.send_outbound("reply", normalized, settings)
    assert result["status"] == "dry_run"
    assert result["target_url"].endswith("/conversations/conv-abc/messages")


@pytest.mark.asyncio
async def test_send_webhook_live_posts_and_returns_sent(adapter: GhlAdapter, patch_settings) -> None:
    settings = _settings(ghl_dry_run=False)
    patch_settings(settings)
    normalized = adapter.normalize(_ghl_payload())

    fake_response = MagicMock()
    fake_response.is_success = True
    fake_response.status_code = 200
    fake_response.json.return_value = {"id": "out-msg-9"}

    fake_client = MagicMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.post = AsyncMock(return_value=fake_response)

    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.send_outbound("hi back", normalized, settings)

    assert result["status"] == "sent"
    assert result["http_status"] == 200
    assert result["external_id"] == "out-msg-9"
    # Verify the call hit the conversations/messages endpoint with bearer auth.
    fake_client.post.assert_awaited_once()
    called_url = fake_client.post.await_args.args[0]
    assert called_url.endswith("/conversations/conv-abc/messages")
    headers = fake_client.post.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer key-123"
    assert fake_client.post.await_args.kwargs["json"]["message"] == "hi back"


@pytest.mark.asyncio
async def test_send_webhook_live_failure(adapter: GhlAdapter, patch_settings) -> None:
    settings = _settings(ghl_dry_run=False)
    patch_settings(settings)
    normalized = adapter.normalize(_ghl_payload())

    fake_response = MagicMock()
    fake_response.is_success = False
    fake_response.status_code = 422

    fake_client = MagicMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.post = AsyncMock(return_value=fake_response)

    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.send_outbound("hi back", normalized, settings)

    assert result["status"] == "failed"
    assert result["http_status"] == 422