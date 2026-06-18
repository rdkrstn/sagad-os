import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import httpx

from agent_studio.config import Settings, get_settings
from agent_studio.twenty import TwentyAdapter, twenty_status
from agent_studio.chatwoot import (
    chatwoot_context_from_payload,
    fetch_conversation_details,
    send_approved_reply,
    resolve_conversation,
)


# =====================================================================
# TWENTY CRM ADAPTER TESTS
# =====================================================================

def test_twenty_status_disabled():
    settings = Settings(twenty_enabled=False)
    status = twenty_status(settings)
    assert status.status == "disabled"
    assert status.writes_enabled is False


def test_twenty_status_unconfigured():
    settings = Settings(twenty_enabled=True, twenty_base_url=None)
    status = twenty_status(settings)
    assert status.status == "unconfigured"
    assert status.writes_enabled is False


def test_twenty_status_dry_run():
    # If API key and URL are set but dry_run is true
    settings = Settings(
        twenty_enabled=True,
        twenty_base_url="http://twenty.example.com",
        twenty_api_key="secret-key",
        twenty_dry_run=True,
    )
    status = twenty_status(settings)
    assert status.status == "dry_run"
    assert status.writes_enabled is False


def test_twenty_status_ready():
    settings = Settings(
        twenty_enabled=True,
        twenty_base_url="http://twenty.example.com",
        twenty_api_key="secret-key",
        twenty_dry_run=False,
        twenty_allow_writes=True,
    )
    status = twenty_status(settings)
    assert status.status == "ready"
    assert status.writes_enabled is True


@pytest.mark.asyncio
async def test_twenty_lookup_contact_blocked():
    settings = Settings(twenty_enabled=False)
    adapter = TwentyAdapter(settings)
    context, plan, result = await adapter.lookup_contact("John Doe")
    assert context is None
    assert result.status == "blocked"
    assert "unavailable until" in result.detail


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_twenty_lookup_contact_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "people": {
                "edges": [
                    {
                        "node": {
                            "id": "person-123",
                            "name": "Jane Smith",
                            "emails": {"primaryEmail": "jane.smith@example.com"},
                            "phones": {"primaryPhoneNumber": "+15551234567"},
                            "company": {"name": "Example Corp"},
                            "tags": ["vip", "leads"],
                        }
                    }
                ]
            }
        }
    }
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.twenty_configured:
        settings.twenty_base_url = "http://twenty.example.com"
        settings.twenty_api_key = "secret-key"
    settings.twenty_enabled = True
    adapter = TwentyAdapter(settings)

    context, plan, result = await adapter.lookup_contact("Jane Smith")

    assert context is not None
    assert context.contact_id == "person-123"
    assert context.display_name == "Jane Smith"
    assert context.company_name == "Example Corp"
    assert context.email_masked == "ja***@example.com"
    assert context.phone_masked == "*** *** 4567"
    assert context.tags == ["vip", "leads"]
    assert result.status == "succeeded"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.twenty_base_url).rstrip('/')}/graphql"
    assert args[0] == expected_url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {settings.twenty_api_key}",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_twenty_create_note_dry_run():
    settings = Settings(
        twenty_enabled=True,
        twenty_base_url="http://twenty.example.com",
        twenty_api_key="secret-key",
        twenty_dry_run=True,
    )
    adapter = TwentyAdapter(settings)

    plan, result = await adapter.create_note(
        contact_id="person-123",
        note="Meeting notes here.",
        conversation_id="conv-1",
        approved=True,
    )

    assert result.status == "dry_run"
    assert "dry-run only" in result.detail
    assert result.data["args"]["contact_id"] == "person-123"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_twenty_create_note_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"createNote": {"id": "note-999"}}}
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.twenty_configured:
        settings.twenty_base_url = "http://twenty.example.com"
        settings.twenty_api_key = "secret-key"
    settings.twenty_enabled = True
    settings.twenty_dry_run = False
    settings.twenty_allow_writes = True
    adapter = TwentyAdapter(settings)

    plan, result = await adapter.create_note(
        contact_id="person-123",
        note="This is a live note.",
        conversation_id="conv-1",
        approved=True,
    )

    assert result.status == "succeeded"
    assert result.data == {"data": {"createNote": {"id": "note-999"}}}

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.twenty_base_url).rstrip('/')}/graphql"
    assert args[0] == expected_url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {settings.twenty_api_key}",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_twenty_create_task_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"createTask": {"id": "task-111"}}}
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.twenty_configured:
        settings.twenty_base_url = "http://twenty.example.com"
        settings.twenty_api_key = "secret-key"
    settings.twenty_enabled = True
    settings.twenty_dry_run = False
    settings.twenty_allow_writes = True
    adapter = TwentyAdapter(settings)

    plan, result = await adapter.create_task(
        contact_id="person-123",
        title="Follow up task",
        due_at=datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc),
        owner_id="owner-222",
        conversation_id="conv-1",
        approved=True,
    )

    assert result.status == "succeeded"
    assert result.data == {"data": {"createTask": {"id": "task-111"}}}

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.twenty_base_url).rstrip('/')}/graphql"
    assert args[0] == expected_url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {settings.twenty_api_key}",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_twenty_update_lead_stage_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"updatePerson": {"id": "person-123"}}}
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.twenty_configured:
        settings.twenty_base_url = "http://twenty.example.com"
        settings.twenty_api_key = "secret-key"
    settings.twenty_enabled = True
    settings.twenty_dry_run = False
    settings.twenty_allow_writes = True
    adapter = TwentyAdapter(settings)

    plan, result = await adapter.update_lead_stage(
        contact_id="person-123",
        lead_stage="PROPOSAL",
        conversation_id="conv-1",
        approved=True,
    )

    assert result.status == "succeeded"
    assert plan.risk_level == "high"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.twenty_base_url).rstrip('/')}/graphql"
    assert args[0] == expected_url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {settings.twenty_api_key}",
        "Content-Type": "application/json",
    }


# =====================================================================
# CHATWOOT MESSAGING ADAPTER TESTS
# =====================================================================

def test_chatwoot_context_from_payload_parsing():
    payload = {
        "conversation": {
            "unread_count": 3,
            "can_reply": True,
            "source_id": "message-source-abc",
            "status": "open",
            "priority": "medium",
            "labels": ["support", "billing"],
            "meta": {
                "sender": {
                    "last_seen_at": "2026-06-15T12:00:00Z"
                }
            },
            "inbox": {
                "id": "12",
                "name": "Local Inbox",
                "channel_type": "Channel::WebWidget",
            }
        }
    }

    context = chatwoot_context_from_payload(payload, normalized_channel="web_chat")

    assert context.normalized_channel == "web_chat"
    assert context.unread_count == 3
    assert context.can_reply is True
    assert context.source_id == "message-source-abc"
    assert context.status == "open"
    assert context.priority == "medium"
    assert context.labels == ["support", "billing"]
    assert context.inbox is not None
    assert context.inbox.id == "12"
    assert context.inbox.channel_type == "Channel::WebWidget"


@pytest.mark.asyncio
async def test_chatwoot_fetch_conversation_details_unconfigured():
    settings = Settings(chatwoot_base_url=None)
    context = await fetch_conversation_details(
        settings=settings,
        chatwoot_conversation_id="cw-456",
        fallback_channel="email",
    )
    assert context.fetch_status == "unconfigured"
    assert context.normalized_channel == "email"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_chatwoot_fetch_conversation_details_success(mock_get):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {
        "payload": {
            "unread_count": 1,
            "can_reply": True,
            "source_id": "src-777",
            "inbox": {
                "id": "2",
                "channel_type": "Channel::Email",
            }
        }
    }
    mock_get.return_value = mock_response

    settings = get_settings()
    if not settings.chatwoot_configured:
        settings.chatwoot_base_url = "http://chatwoot.example.com"
        settings.chatwoot_account_id = "1"
        settings.chatwoot_api_access_token = "token123"

    context = await fetch_conversation_details(
        settings=settings,
        chatwoot_conversation_id="cw-456",
        fallback_channel="email",
    )

    assert context.fetch_status == "ready"
    assert context.unread_count == 1
    assert context.can_reply is True
    assert context.source_id == "src-777"
    assert context.normalized_channel == "email"

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    expected_url = f"{str(settings.chatwoot_base_url).rstrip('/')}/api/v1/accounts/{settings.chatwoot_account_id}/conversations/cw-456"
    assert args[0] == expected_url
    assert kwargs["headers"] == {"api_access_token": str(settings.chatwoot_api_access_token)}


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_chatwoot_send_approved_reply_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"id": "msg-888"}
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.chatwoot_configured:
        settings.chatwoot_base_url = "http://chatwoot.example.com"
        settings.chatwoot_account_id = "1"
        settings.chatwoot_api_access_token = "token123"
    settings.chatwoot_dry_run = False

    result = await send_approved_reply(
        settings=settings,
        chatwoot_conversation_id="cw-456",
        content="Hello, your refund has been processed.",
    )

    assert result["status"] == "sent"
    assert result["external_id"] == "msg-888"
    assert "Approved reply sent" in result["detail"]

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.chatwoot_base_url).rstrip('/')}/api/v1/accounts/{settings.chatwoot_account_id}/conversations/cw-456/messages"
    assert args[0] == expected_url
    assert kwargs["headers"] == {"api_access_token": str(settings.chatwoot_api_access_token)}
    assert kwargs["json"] == {"content": "Hello, your refund has been processed.", "message_type": "outgoing"}


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_chatwoot_resolve_conversation_success(mock_post):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"id": "cw-456", "status": "resolved"}
    mock_post.return_value = mock_response

    settings = get_settings()
    if not settings.chatwoot_configured:
        settings.chatwoot_base_url = "http://chatwoot.example.com"
        settings.chatwoot_account_id = "1"
        settings.chatwoot_api_access_token = "token123"
    settings.chatwoot_dry_run = False

    result = await resolve_conversation(
        settings=settings,
        chatwoot_conversation_id="cw-456",
    )

    assert result["status"] == "resolved"
    assert "conversation resolved" in result["detail"]

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    expected_url = f"{str(settings.chatwoot_base_url).rstrip('/')}/api/v1/accounts/{settings.chatwoot_account_id}/conversations/cw-456/toggle_status"
    assert args[0] == expected_url
    assert kwargs["headers"] == {"api_access_token": str(settings.chatwoot_api_access_token)}
    assert kwargs["json"] == {"status": "resolved"}
