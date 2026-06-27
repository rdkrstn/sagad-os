"""GHL DB-backed integration-config tests (InMemory store, no Postgres required).

Covers the Phase 2 surface: ghl upsert + display status, missing-field detection, the live
GHL test probe (mocked httpx), disable, and configured_settings DB-over-env override with env
fallback. These run against the default InMemory store (DATABASE_URL unset).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.integration_config import InMemoryIntegrationConfigStore, configured_settings
from agent_studio.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _in_memory_store(monkeypatch: pytest.MonkeyPatch):
    """Force the InMemory integration-config store for every test.

    The real env loads a DATABASE_URL via config.load_dotenv(); in sandboxes without a live
    Postgres the Postgres store's clear()/upsert would time out. These tests exercise the
    in-memory code path, so swap the store in both the integration_config and main namespaces
    (routes use main's import; configured_settings/display use the module-global).
    """
    store = InMemoryIntegrationConfigStore()
    monkeypatch.setattr("agent_studio.integration_config.integration_config_store", store)
    monkeypatch.setattr("agent_studio.main.integration_config_store", store)
    get_settings.cache_clear()
    yield store


_GHL_CONFIG = {
    "base_url": "https://services.leadconnectorhq.com",
    "api_key": "ghl-key-123",
    "location_id": "loc-abc",
    "outbound_mode": "webhook",
    "signature_scheme": "hmac",
    "enabled": True,
    "dry_run": False,
    "poll_enabled": True,
    "poll_interval_seconds": 15,
    "webhook_secret": "wh-secret",
}


def _ghl_connection() -> dict:
    response = client.get("/integration-configs", headers={"X-Sagad-Role": "owner"})
    assert response.status_code == 200
    for row in response.json()["connections"]:
        if row["provider"] == "ghl":
            return row
    raise AssertionError("GHL connection not returned by /integration-configs")


def test_ghl_upsert_then_display_shows_ready() -> None:
    response = client.put(
        "/integration-configs/ghl",
        headers={"X-Sagad-Role": "owner"},
        json=_GHL_CONFIG,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["configured"] is True
    assert body["enabled"] is True
    assert body["has_api_key"] is True
    assert body["has_webhook_secret"] is True
    assert body["location_id"] == "loc-abc"
    assert body["outbound_mode"] == "webhook"
    assert body["poll_enabled"] is True
    assert body["poll_interval_seconds"] == 15

    listed = _ghl_connection()
    assert listed["status"] == "ready"
    assert listed["provider"] == "ghl"
    assert listed["kind"] == "channel"
    assert listed["name"] == "GoHighLevel"


def test_ghl_upsert_missing_location_is_unconfigured() -> None:
    config = dict(_GHL_CONFIG)
    config["location_id"] = None
    response = client.put(
        "/integration-configs/ghl",
        headers={"X-Sagad-Role": "owner"},
        json=config,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unconfigured"
    assert body["configured"] is False
    assert "location_id" in body["missing"]


def test_ghl_test_probe_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    client.put("/integration-configs/ghl", headers={"X-Sagad-Role": "owner"}, json=_GHL_CONFIG)

    def mock_get(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    response = client.post(
        "/integration-configs/ghl/test",
        headers={"X-Sagad-Role": "owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "HTTP 200" in body["detail"]


def test_ghl_test_probe_auth_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client.put("/integration-configs/ghl", headers={"X-Sagad-Role": "owner"}, json=_GHL_CONFIG)

    def mock_get(self, url, **kwargs):
        return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    response = client.post(
        "/integration-configs/ghl/test",
        headers={"X-Sagad-Role": "owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "401" in body["detail"]


def test_ghl_test_unconfigured_when_creds_missing() -> None:
    response = client.post(
        "/integration-configs/ghl/test",
        headers={"X-Sagad-Role": "owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unconfigured"


def test_ghl_disable_flips_status() -> None:
    client.put("/integration-configs/ghl", headers={"X-Sagad-Role": "owner"}, json=_GHL_CONFIG)
    response = client.post(
        "/integration-configs/ghl/disable",
        headers={"X-Sagad-Role": "owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["enabled"] is False


def test_configured_settings_overrides_env_for_ghl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GHL_API_KEY", "env-key")
    monkeypatch.setenv("GHL_BASE_URL", "https://env.example")
    monkeypatch.setenv("GHL_LOCATION_ID", "env-loc")
    monkeypatch.setenv("GHL_DRY_RUN", "true")
    get_settings.cache_clear()

    config = dict(_GHL_CONFIG)
    config["api_key"] = "db-key"
    config["location_id"] = "db-loc"
    config["dry_run"] = False
    client.put("/integration-configs/ghl", headers={"X-Sagad-Role": "owner"}, json=config)

    settings = configured_settings(get_settings(), context=None)
    assert settings.ghl_api_key == "db-key"
    assert settings.ghl_location_id == "db-loc"
    assert settings.ghl_dry_run is False
    assert settings.ghl_poll_enabled is True
    assert settings.ghl_poll_interval_seconds == 15


def test_configured_settings_falls_back_to_env_when_no_ghl_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GHL_API_KEY", "env-key")
    monkeypatch.setenv("GHL_LOCATION_ID", "env-loc")
    monkeypatch.setenv("GHL_DRY_RUN", "true")
    get_settings.cache_clear()

    settings = configured_settings(get_settings(), context=None)
    assert settings.ghl_api_key == "env-key"
    assert settings.ghl_location_id == "env-loc"
    assert settings.ghl_dry_run is True


def test_ghl_upsert_requires_admin_role() -> None:
    response = client.put("/integration-configs/ghl", headers={"X-Sagad-Role": "viewer"}, json=_GHL_CONFIG)
    assert response.status_code == 403
