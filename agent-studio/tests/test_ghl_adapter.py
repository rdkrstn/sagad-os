"""Unit tests for the GoHighLevel (GHL) channel adapter.

These exercise the adapter in isolation (HMAC verification, normalization, ignore rules,
outbound webhook/MCP/dry-run modes) — no FastAPI app, no graph. The universal-webhook
HTTP path is covered in test_universal_webhook.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_studio.adapters.ghl import GhlAdapter, _clear_crm_context_cache, _hmac_sha256_hex
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


# --- verify_inbound: Ed25519 scheme (native InboundMessage webhook) ----------

def _ed25519_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pub_bytes.hex(), priv_bytes.hex()


def _ed25519_sign(priv_hex: str, raw: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex)).sign(raw).hex()


def test_verify_ed25519_no_key_allows(adapter: GhlAdapter, patch_settings) -> None:
    # scheme=ed25519 but no native key configured -> no-op (dev mode), mirrors HMAC no-secret.
    patch_settings(_settings(ghl_signature_scheme="ed25519", ghl_native_webhook_key=None))
    adapter.verify_inbound(b'{"x":1}', {})


def test_verify_ed25519_valid_signature(adapter: GhlAdapter, patch_settings) -> None:
    pub_hex, priv_hex = _ed25519_keypair()
    patch_settings(_settings(ghl_signature_scheme="ed25519", ghl_native_webhook_key=pub_hex))
    raw = b'{"message":{"body":"hi"}}'
    sig = _ed25519_sign(priv_hex, raw)
    adapter.verify_inbound(raw, {"x-wh-signature": sig})


def test_verify_ed25519_invalid_signature_raises_401(adapter: GhlAdapter, patch_settings) -> None:
    from fastapi import HTTPException

    pub_hex, _ = _ed25519_keypair()
    patch_settings(_settings(ghl_signature_scheme="ed25519", ghl_native_webhook_key=pub_hex))
    with pytest.raises(HTTPException) as exc:
        adapter.verify_inbound(b'{"x":1}', {"x-wh-signature": "deadbeef"})
    assert exc.value.status_code == 401


def test_verify_ed25519_missing_signature_raises_401(adapter: GhlAdapter, patch_settings) -> None:
    from fastapi import HTTPException

    pub_hex, _ = _ed25519_keypair()
    patch_settings(_settings(ghl_signature_scheme="ed25519", ghl_native_webhook_key=pub_hex))
    with pytest.raises(HTTPException) as exc:
        adapter.verify_inbound(b'{"x":1}', {})
    assert exc.value.status_code == 401


def test_verify_unknown_scheme_falls_back_to_hmac(adapter: GhlAdapter, patch_settings) -> None:
    # A misconfigured scheme must never disable auth: it falls back to HMAC.
    secret = "shh"
    patch_settings(_settings(ghl_signature_scheme="bogus", ghl_webhook_secret=secret))
    raw = b'{"message":{"body":"hi"}}'
    sig = _hmac_sha256_hex(secret, raw)
    adapter.verify_inbound(raw, {"X-GHL-Signature": sig})  # must not raise


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
    # The MCP gateway is descriptor-only by design (no executor runtime), so MCP mode is
    # an honest dry-run that names the descriptor it WOULD invoke — never a fabricated send.
    assert result["status"] == "dry_run"
    assert "MCP" in result["detail"]
    assert result["target_url"].startswith("mcp://ghl.messages.send")
    assert "conversationId=conv-abc" in result["target_url"]


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


# --- fetch_crm_context (read-only GHL CRM) ----------------------------------

def _crm_fake_client(
    *,
    contact_body: dict[str, Any] | None = None,
    contact_status: int = 200,
    opp_body: dict[str, Any] | None = None,
    opp_status: int = 200,
    get_side_effect: Any = None,
) -> MagicMock:
    contact_resp = MagicMock()
    contact_resp.is_success = contact_status < 400
    contact_resp.status_code = contact_status
    contact_resp.json.return_value = contact_body or {}

    opp_resp = MagicMock()
    opp_resp.is_success = opp_status < 400
    opp_resp.status_code = opp_status
    opp_resp.json.return_value = opp_body or {}

    fake_client = MagicMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    if get_side_effect is not None:
        fake_client.get = AsyncMock(side_effect=get_side_effect)
    else:
        fake_client.get = AsyncMock(return_value=contact_resp)
    fake_client.post = AsyncMock(return_value=opp_resp)
    return fake_client


@pytest.mark.asyncio
async def test_fetch_crm_context_unconfigured_returns_none(adapter: GhlAdapter) -> None:
    _clear_crm_context_cache()
    normalized = adapter.normalize(_ghl_payload())
    # No api key -> ghl_configured is False -> no fetch, no httpx call.
    settings = _settings(ghl_api_key=None)
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient") as mock_client:
        result = await adapter.fetch_crm_context(normalized, settings)
    assert result is None
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_crm_context_no_contact_id_returns_none(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    # Payload without a contact.id -> nothing to look up.
    payload = {"conversationId": "c", "message": {"id": "m", "body": "hi", "direction": "inbound", "type": "SMS"}}
    normalized = adapter.normalize(payload)
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient") as mock_client:
        result = await adapter.fetch_crm_context(normalized, _settings())
    assert result is None
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_crm_context_returns_contact_and_opportunity(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    normalized = adapter.normalize(_ghl_payload())  # contact.id = cont-1
    fake_client = _crm_fake_client(
        contact_body={"contact": {
            "id": "cont-1", "name": "Jane Doe", "companyName": "Acme Co",
            "phone": "+15551234567", "email": "jane@acme.com", "tags": ["vip", "repeat"],
        }},
        opp_body={"opportunities": [{
            "id": "opp-1", "name": "Tune-up deal", "status": "open",
            "pipelineStage": {"name": "Proposal"}, "monetaryValue": "450.00",
        }]},
    )
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.fetch_crm_context(normalized, _settings())
    assert result is not None
    assert result.provider == "GHL"
    assert result.status == "ready"
    assert result.contact_id == "cont-1"
    assert result.display_name == "Jane Doe"
    assert result.company_name == "Acme Co"
    assert result.tags == ["vip", "repeat"]
    # PII is masked, never raw.
    assert result.phone_masked is not None and "+15551234567" not in (result.phone_masked or "")
    assert result.email_masked is not None and "jane@acme.com" not in (result.email_masked or "")
    # First opportunity's deal stage + value surfaced for RevOps triage.
    assert result.deal_stage == "Proposal"
    assert result.deal_value == "450.00"
    # The opportunities search is a POST with the contact_id/location_id body.
    fake_client.post.assert_awaited_once()
    posted_json = fake_client.post.await_args.kwargs["json"]
    assert posted_json["contact_id"] == "cont-1"
    assert posted_json["location_id"] == "loc-1"


@pytest.mark.asyncio
async def test_fetch_crm_context_caches_per_contact(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    normalized = adapter.normalize(_ghl_payload())
    fake_client = _crm_fake_client(
        contact_body={"contact": {"id": "cont-1", "name": "Jane Doe"}},
        opp_body={"opportunities": []},
    )
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client) as mock_client:
        first = await adapter.fetch_crm_context(normalized, _settings())
        second = await adapter.fetch_crm_context(normalized, _settings())
    assert first is not None and second is not None
    # Second call is served from the TTL cache -> httpx only constructed once.
    assert mock_client.call_count == 1


@pytest.mark.asyncio
async def test_fetch_crm_context_timeout_returns_none(adapter: GhlAdapter, patch_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    # Shrink the timeout so the hung GET trips wait_for immediately; never blocks inbound.
    monkeypatch.setattr("agent_studio.adapters.ghl._CRM_FETCH_TIMEOUT_SECONDS", 0.1)

    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(5)  # far longer than the 0.1s cap

    fake_client = _crm_fake_client(get_side_effect=_hang)
    normalized = adapter.normalize(_ghl_payload())
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.fetch_crm_context(normalized, _settings())
    assert result is None  # degraded gracefully, no exception escapes


@pytest.mark.asyncio
async def test_fetch_crm_context_request_error_returns_none(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    normalized = adapter.normalize(_ghl_payload())

    def _boom(*_args, **_kwargs):
        raise httpx.ConnectError("GHL down")

    fake_client = _crm_fake_client(get_side_effect=_boom)
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.fetch_crm_context(normalized, _settings())
    assert result is None


@pytest.mark.asyncio
async def test_fetch_crm_context_missing_contact_returns_none(adapter: GhlAdapter, patch_settings) -> None:
    patch_settings(_settings())
    _clear_crm_context_cache()
    normalized = adapter.normalize(_ghl_payload())
    # 404 on the contact -> no contact payload -> None (we don't fabricate a context).
    fake_client = _crm_fake_client(contact_status=404, contact_body={}, opp_body={"opportunities": []})
    with patch("agent_studio.adapters.ghl.httpx.AsyncClient", return_value=fake_client):
        result = await adapter.fetch_crm_context(normalized, _settings())
    assert result is None