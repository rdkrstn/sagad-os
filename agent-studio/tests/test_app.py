import httpx
import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.main import app
from agent_studio.store import store


client = TestClient(app)


def setup_function() -> None:
    store.clear()
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

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": True, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"


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
