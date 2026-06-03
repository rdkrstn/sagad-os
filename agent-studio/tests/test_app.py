import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_studio.config import get_settings
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app
from agent_studio.realtime import create_realtime_token
from agent_studio.store import store


client = TestClient(app)


def setup_function() -> None:
    store.clear()
    integration_config_store.clear()
    get_settings.cache_clear()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["knowledge_records"] >= 1
    assert payload["twenty_status"]["status"] == "disabled"


def test_chatwoot_webhook_creates_approval_conversation() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 991,
            "content": "How much does an AC tune-up cost?",
            "conversation": {"id": 42},
            "sender": {"name": "Avery Hill"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_name"] == "Avery Hill"
    assert payload["intent"] == "pricing_lead"
    assert payload["approval_status"] == "needs_approval"
    assert payload["retrieved_knowledge"]
    assert "Basis:" in payload["draft_reply"]


def test_chatwoot_webhook_threads_same_conversation_messages() -> None:
    first = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1001,
            "content": "How much does service cost?",
            "message_type": "incoming",
            "conversation": {"id": 42},
            "sender": {"name": "Thread Customer"},
        },
    ).json()

    second_response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1002,
            "content": "Actually cancel that and refund me.",
            "message_type": "incoming",
            "conversation": {"id": 42},
            "sender": {"name": "Thread Customer"},
        },
    )

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["id"] == first["id"]
    assert second["incoming_message"] == "Actually cancel that and refund me."
    assert second["intent"] == "refund_or_cancellation"
    assert second["approval_status"] == "needs_approval"
    assert second["send_status"] == "not_sent"
    assert [message["body"] for message in second["messages"]] == [
        "How much does service cost?",
        "Actually cancel that and refund me.",
    ]

    listed = client.get("/conversations").json()["conversations"]
    assert len(listed) == 1
    assert listed[0]["id"] == first["id"]


def test_chatwoot_webhook_retry_is_idempotent_by_message_id() -> None:
    payload = {
        "event": "message_created",
        "id": 2001,
        "content": "I need help with booking.",
        "message_type": "incoming",
        "conversation": {"id": 88},
        "sender": {"name": "Retry Customer"},
    }

    first = client.post("/webhooks/chatwoot", json=payload).json()
    second = client.post("/webhooks/chatwoot", json=payload).json()

    assert second["id"] == first["id"]
    assert [message["external_message_id"] for message in second["messages"]] == ["2001"]
    listed = client.get("/conversations").json()["conversations"]
    assert len(listed) == 1


def test_chatwoot_outgoing_private_message_is_ignored() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 3001,
            "content": "Operator reply should not draft.",
            "message_type": "outgoing",
            "private": True,
            "conversation": {"id": 99},
            "sender": {"name": "Operator"},
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert client.get("/conversations").json()["conversations"] == []


def test_conversation_websocket_accepts_valid_realtime_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGAD_REALTIME_SECRET", "test-realtime-secret")
    get_settings.cache_clear()
    token = create_realtime_token(
        secret="test-realtime-secret",
        organization_id="org-test",
        user_id="1",
        role="supervisor",
        ttl_seconds=30,
    )

    with client.websocket_connect(f"/ws/conversations?token={token}") as websocket:
        payload = websocket.receive_json()

    assert payload["type"] == "heartbeat"
    assert payload["organization_id"] == "org-test"


def test_conversation_websocket_rejects_invalid_realtime_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGAD_REALTIME_SECRET", "test-realtime-secret")
    get_settings.cache_clear()

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/conversations?token=bad-token"):
            pass


def test_reject_does_not_send() -> None:
    created = client.post(
        "/webhooks/chatwoot",
        json={"content": "Cancel it and give me a refund.", "conversation": {"id": 77}},
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": False, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "rejected"
    assert payload["send_status"] == "not_sent"


def test_approve_send_uses_dry_run_without_chatwoot_credentials() -> None:
    created = client.post(
        "/webhooks/chatwoot",
        json={"content": "Hello", "conversation": {"id": 88}},
    ).json()
    assert created["intent"] == "general_support"
    assert "pricing or booking help" in created["draft_reply"]

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": True, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"


def test_approve_send_records_outbound_message_in_same_thread() -> None:
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 4001,
            "content": "Hello",
            "message_type": "incoming",
            "conversation": {"id": 400},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={
            "approved": True,
            "supervisor_id": "qa-lead",
            "edited_reply": "Thanks. What do you need help with?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created["id"]
    assert [message["sender_type"] for message in payload["messages"]] == [
        "customer",
        "ai_agent",
    ]
    assert [message["body"] for message in payload["messages"]] == [
        "Hello",
        "Thanks. What do you need help with?",
    ]
    assert len(client.get("/conversations").json()["conversations"]) == 1


def test_twenty_disabled_health_state() -> None:
    response = client.get("/integrations/twenty/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "Twenty CRM"
    assert payload["status"] == "disabled"
    assert payload["external"] is True


def test_integrations_use_generic_webhooks_not_n8n() -> None:
    response = client.get("/integrations")

    assert response.status_code == 200
    integrations = response.json()["integrations"]
    providers = [item["provider"] for item in integrations]
    assert "Generic Webhooks" in providers
    assert "n8n" not in providers
    webhook = next(item for item in integrations if item["provider"] == "Generic Webhooks")
    assert webhook["kind"] == "webhook"


def test_integration_configs_are_viewable_without_secrets() -> None:
    response = client.get(
        "/integration-configs",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 200
    payload = response.json()
    providers = {item["provider"] for item in payload["connections"]}
    assert providers == {"chatwoot", "twenty"}
    assert "secret-token" not in response.text
    assert "twenty-secret" not in response.text


def test_integration_config_write_requires_owner_or_admin() -> None:
    response = client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "supervisor"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "api_access_token": "secret-token",
            "webhook_token": "secret-webhook",
            "enabled": True,
            "dry_run": False,
        },
    )

    assert response.status_code == 403
    assert "owner or admin" in response.json()["detail"].lower()


def test_owner_can_save_chatwoot_config_without_secret_leak() -> None:
    response = client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "7",
            "api_access_token": "secret-token",
            "webhook_token": "secret-webhook",
            "enabled": True,
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "chatwoot"
    assert payload["status"] == "ready"
    assert payload["configured"] is True
    assert payload["has_api_access_token"] is True
    assert payload["has_webhook_token"] is True
    assert "secret-token" not in response.text
    assert "secret-webhook" not in response.text


def test_owner_can_save_twenty_config_without_secret_leak() -> None:
    response = client.put(
        "/integration-configs/twenty",
        headers={"X-Sagad-Role": "admin"},
        json={
            "base_url": "https://crm.example.test",
            "api_mode": "graphql",
            "api_key": "twenty-secret",
            "enabled": True,
            "dry_run": True,
            "allow_writes": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "twenty"
    assert payload["status"] == "dry_run"
    assert payload["configured"] is True
    assert payload["has_api_key"] is True
    assert payload["writes_enabled"] is False
    assert "twenty-secret" not in response.text


def test_integration_config_test_reports_missing_config() -> None:
    response = client.post(
        "/integration-configs/twenty/test",
        headers={"X-Sagad-Role": "admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "twenty"
    assert payload["status"] == "unconfigured"
    assert "base url" in payload["detail"].lower()


def test_integration_config_test_requires_owner_or_admin() -> None:
    response = client.post(
        "/integration-configs/twenty/test",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 403
    assert "owner or admin" in response.json()["detail"].lower()


def test_integration_config_partial_update_preserves_existing_values() -> None:
    created = client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "7",
            "api_access_token": "secret-token",
            "webhook_token": "secret-webhook",
            "enabled": True,
            "dry_run": False,
        },
    )
    assert created.status_code == 200

    updated = client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "inbox_id": "9",
            "enabled": True,
            "dry_run": False,
        },
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["base_url"] == "https://chat.example.test"
    assert payload["account_id"] == "1"
    assert payload["inbox_id"] == "9"
    assert payload["has_api_access_token"] is True
    assert payload["has_webhook_token"] is True
    assert "secret-token" not in updated.text


def test_twenty_dry_run_write_does_not_call_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWENTY_ENABLED", "true")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_DRY_RUN", "true")
    get_settings.cache_clear()

    async def fail_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        raise AssertionError(f"network should not be called: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)

    response = client.post(
        "/tools/crm/create-note",
        json={
            "contact_id": "person_123",
            "note": "Supervisor approved note.",
            "approved": True,
            "supervisor_id": "demo-supervisor",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "dry_run"
    assert payload["plan"]["provider"] == "Twenty CRM"


def test_twenty_write_rejects_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWENTY_ENABLED", "true")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_DRY_RUN", "true")
    get_settings.cache_clear()

    response = client.post(
        "/tools/crm/create-task",
        json={
            "contact_id": "person_123",
            "title": "Call customer back",
            "approved": False,
        },
    )

    assert response.status_code == 403
    assert "approval" in response.json()["detail"].lower()


def test_twenty_live_read_maps_contact_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWENTY_ENABLED", "true")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_DRY_RUN", "false")
    get_settings.cache_clear()

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": {
                    "people": {
                        "edges": [
                            {
                                "node": {
                                    "id": "person_123",
                                    "name": "Avery Hill",
                                    "emails": {"primaryEmail": "avery@example.com"},
                                    "phones": {"primaryPhoneNumber": "+15550194"},
                                    "company": {"name": "Suncrest Home Services"},
                                    "tags": ["lead", "hvac"],
                                },
                            },
                        ],
                    },
                },
            }

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> MockResponse:
        assert url == "https://twenty.example.test/graphql"
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = client.post(
        "/tools/crm/lookup-contact",
        json={"query": "Avery Hill"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "succeeded"
    assert payload["crm_context"]["provider"] == "Twenty CRM"
    assert payload["crm_context"]["contact_id"] == "person_123"
    assert payload["crm_context"]["display_name"] == "Avery Hill"
