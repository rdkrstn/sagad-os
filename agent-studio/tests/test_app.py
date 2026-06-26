import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_studio.config import get_settings
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app
from agent_studio.realtime import create_realtime_token
from agent_studio.schemas import ConversationRecord
from agent_studio.store import store


client = TestClient(app)
SECRET_MARKERS = (
    "api_key",
    "access_token",
    "webhook_token",
    "authorization",
    "bearer ",
    "secret-token",
    "twenty-secret",
    "runtime-token",
)


def setup_function() -> None:
    store.clear()
    integration_config_store.clear()
    get_settings.cache_clear()


def assert_sprint2_retrieval_fields(
    payload: dict[str, object],
    *,
    expected_missing_knowledge: bool,
) -> None:
    assert isinstance(payload["selected_agent"], str)
    assert payload["selected_agent"]
    assert isinstance(payload["retrieval_confidence"], int | float)
    assert 0 <= payload["retrieval_confidence"] <= 1
    assert payload["missing_knowledge"] is expected_missing_knowledge

    diagnostic = payload["retrieval_diagnostic"]
    assert isinstance(diagnostic, dict)
    assert diagnostic

    metadata_filters = diagnostic.get("metadata_filters")
    if metadata_filters is None:
        query_plan = diagnostic.get("query_plan", {})
        assert isinstance(query_plan, dict)
        metadata_filters = query_plan.get("metadata_filters")
    assert isinstance(metadata_filters, dict)
    assert metadata_filters["approval_status"] == "approved"
    assert metadata_filters["intent"] == payload["intent"]
    assert metadata_filters["risk_level"] == payload["risk_level"]
    assert metadata_filters["selected_agent"] == payload["selected_agent"]

    selected_sources = diagnostic.get("selected_sources")
    assert isinstance(selected_sources, list)
    assert selected_sources
    first_source = selected_sources[0]
    assert isinstance(first_source, dict)
    assert first_source["title"]
    assert first_source["source_path"]
    assert isinstance(first_source["score"], int | float)

    reasons = diagnostic.get("reasons")
    assert isinstance(reasons, list)
    assert reasons

    skill_diagnostic = diagnostic.get("skill_diagnostic")
    assert isinstance(skill_diagnostic, dict)
    selected_skills = skill_diagnostic.get("selected_skills")
    assert isinstance(selected_skills, list)
    assert "retrieve_knowledge" in selected_skills
    assert "draft_reply" in selected_skills


def assert_no_secret_material(rendered_payload: str) -> None:
    lowered = rendered_payload.lower()
    for marker in SECRET_MARKERS:
        assert marker not in lowered


def assert_policy_metadata(
    tool_result: dict[str, object],
    *,
    supervisor_id: str,
    risk_level: str,
    approved: bool = True,
) -> None:
    data = tool_result["data"]
    assert isinstance(data, dict)
    policy_metadata = data.get("policy_metadata")
    assert isinstance(policy_metadata, dict)
    assert policy_metadata["approval_gate"] == "supervisor_approval"
    assert policy_metadata["requires_approval"] is True
    assert policy_metadata["approved"] is approved
    assert policy_metadata["supervisor_id"] == supervisor_id
    assert policy_metadata["risk_level"] == risk_level


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["knowledge_records"] >= 1
    assert payload["twenty_status"]["status"] == "disabled"


def test_skills_endpoint_returns_registry_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-token")
    monkeypatch.setenv("TWENTY_API_KEY", "twenty-secret")
    get_settings.cache_clear()

    response = client.get("/skills")

    assert response.status_code == 200
    payload = response.json()
    skills = payload["skills"]
    assert isinstance(skills, list)
    assert {
        "classify_message",
        "route_agent",
        "retrieve_knowledge",
        "draft_reply",
        "plan_tools",
    }.issubset({skill["name"] for skill in skills})
    for skill in skills:
        assert skill["description"]
        assert skill["category"]
        assert skill["risk_level"] in {"low", "medium", "high"}
        assert "tools" not in skill
    assert_no_secret_material(response.text)


def test_agents_endpoint_returns_agents() -> None:
    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) > 0
    assert "name" in agents[0]
    assert "intents" in agents[0]
    assert "allowed_tools" in agents[0]
    assert "system_prompt" in agents[0]

def test_tools_manifests_endpoint_returns_current_manifests_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("TWENTY_API_KEY", "twenty-secret")
    get_settings.cache_clear()

    response = client.get("/tools/manifests")

    assert response.status_code == 200
    payload = response.json()
    manifests = payload["tools"]
    assert isinstance(manifests, list)
    assert payload["manifests"] == manifests
    assert {manifest["tool_name"] for manifest in manifests} == {
        "knowledge.search",
        "crm.lookup_contact",
        "crm.create_note",
        "crm.create_task",
        "crm.update_lead_stage",
        "chatwoot.messages.send_approved",
        "chatwoot.conversations.resolve",
        "ghl.messages.send_approved",
    }
    for manifest in manifests:
        assert manifest["provider"]
        assert manifest["skill_name"]
        assert manifest["mode"] in {"read", "write", "dry_run"}
        assert manifest["risk_level"] in {"low", "medium", "high"}
        assert isinstance(manifest["input_schema"], dict)
    assert_no_secret_material(response.text)


def test_mcp_descriptors_endpoint_is_descriptor_only_and_does_not_call_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_network(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        raise AssertionError(f"MCP descriptor endpoint should not call network: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fail_network)
    monkeypatch.setattr(httpx.AsyncClient, "post", fail_network)

    response = client.get("/mcp/descriptors")

    assert response.status_code == 200
    payload = response.json()
    descriptors = payload["descriptors"]
    assert isinstance(descriptors, list)
    assert {descriptor["name"] for descriptor in descriptors} == {
        "knowledge.search",
        "crm.lookup_contact",
        "crm.create_note",
        "crm.create_task",
        "crm.update_lead_stage",
        "chatwoot.messages.send_approved",
        "chatwoot.conversations.resolve",
        "ghl.messages.send_approved",
    }
    for descriptor in descriptors:
        assert descriptor["enabled"] is True
        assert descriptor["policy_wrapped"] is True
        assert isinstance(descriptor["input_schema"], dict)
        assert "execute" not in descriptor
        assert "handler" not in descriptor
    rendered = response.text.lower()
    assert "base_url" not in rendered
    assert "target_url" not in rendered
    assert_no_secret_material(response.text)


def test_evals_endpoints_persist_fixture_runs() -> None:
    cases_response = client.get("/evals/cases")
    assert cases_response.status_code == 200
    cases_payload = cases_response.json()
    assert len(cases_payload["cases"]) == 5
    assert cases_payload["items"] == cases_payload["cases"]

    run_response = client.post("/evals/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["run"]["suite_name"] == "ai_ops_quality"
    assert run_payload["summary"]["case_count"] == 5
    assert run_payload["summary"]["failed_case_count"] == 0
    assert len(run_payload["results"]) == 5

    runs_response = client.get("/evals/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["runs"][0]["id"] == run_payload["run"]["id"]
    assert len(runs_payload["runs"][0]["results"]) == 5


def test_ai_ops_scorecard_returns_live_quality_metrics_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "secret-token")
    get_settings.cache_clear()
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 9801,
            "content": "I need help with a refund.",
            "conversation": {"id": 980},
            "sender": {"name": "Scorecard Customer"},
        },
    )
    assert created.status_code == 200

    response = client.get("/ai-ops/scorecard")

    assert response.status_code == 200
    payload = response.json()
    scorecard = payload["scorecard"]
    metrics = scorecard["metrics"]
    assert scorecard["status"] == "connected"
    assert metrics["totalConversations"] == 1
    assert metrics["aiDraftedResponses"] == 1
    assert metrics["approvalRequired"] >= 1
    assert scorecard["conversations"][0]["customer_name"] == "Scorecard Customer"
    assert_no_secret_material(response.text)


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
    assert_sprint2_retrieval_fields(payload, expected_missing_knowledge=False)
    assert "Basis:" in payload["draft_reply"]


def test_chatwoot_refund_cancellation_webhook_stays_gated_with_retrieval_diagnostics() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 992,
            "content": "I need to cancel my service and get a refund today.",
            "message_type": "incoming",
            "conversation": {"id": 43},
            "sender": {"name": "Morgan Case"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_name"] == "Morgan Case"
    assert payload["intent"] == "refund_or_cancellation"
    assert payload["risk_level"] == "high"
    assert payload["approval_status"] == "needs_approval"
    assert payload["send_status"] == "not_sent"
    assert payload["retrieved_knowledge"]
    assert_sprint2_retrieval_fields(payload, expected_missing_knowledge=False)


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


def test_chatwoot_followup_uses_memory_context_separate_from_knowledge(
    mock_chat_model: object,
) -> None:
    client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1011,
            "content": "hmmm pricing",
            "message_type": "incoming",
            "conversation": {"id": 101},
            "sender": {"name": "Memory Customer"},
        },
    )

    second_response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1012,
            "content": "I already said pricing",
            "message_type": "incoming",
            "conversation": {"id": 101},
            "sender": {"name": "Memory Customer"},
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["memory_context"]
    assert payload["retrieved_knowledge"]
    assert payload["memory_diagnostic"]["memory_available"] is True
    assert any("pricing" in item["content"].lower() for item in payload["memory_context"])

    # With ChatOpenAI, the mock_llm.invoke is called with LangChain messages
    mock_llm = mock_chat_model.return_value  # type: ignore[attr-defined]
    found_memory_call = False
    for call in mock_llm.invoke.call_args_list:
        lc_messages = call[0][0]
        system_prompt = lc_messages[0].content
        if "Conversation Memory" in system_prompt:
            assert "Selected Source Pack" in system_prompt
            assert "hmmm pricing" in system_prompt
            found_memory_call = True
            break
    assert found_memory_call, "Could not find LLM call containing Conversation Memory"


def test_chatwoot_email_webhook_maps_channel_and_keeps_provider() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1101,
            "content": "I emailed about my refund.",
            "message_type": "incoming",
            "conversation": {"id": 110},
            "inbox": {"id": 7, "name": "Support Email", "channel_type": "Channel::Email"},
            "sender": {"name": "Email Customer"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "email"
    assert payload["chatwoot_context"]["normalized_channel"] == "email"
    assert payload["messages"][0]["provider"] == "chatwoot"


def test_chatwoot_web_widget_webhook_maps_channel() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1102,
            "content": "Can I book service?",
            "message_type": "incoming",
            "conversation": {"id": 111},
            "inbox": {"id": 8, "name": "Website", "channel_type": "Channel::WebWidget"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "web_chat"
    assert payload["chatwoot_context"]["inbox"]["name"] == "Website"


def test_chatwoot_missing_source_falls_back_unknown() -> None:
    response = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1103,
            "content": "No source metadata here.",
            "message_type": "incoming",
            "conversation": {"id": 112},
        },
    )

    assert response.status_code == 200
    assert response.json()["channel"] == "unknown"


def test_chatwoot_thread_preserves_existing_normalized_channel() -> None:
    first = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1104,
            "content": "First email.",
            "message_type": "incoming",
            "conversation": {"id": 113},
            "inbox": {"channel_type": "Channel::Email"},
        },
    ).json()
    second = client.post(
        "/webhooks/chatwoot",
        json={
            "event": "message_created",
            "id": 1105,
            "content": "Second message without source metadata.",
            "message_type": "incoming",
            "conversation": {"id": 113},
        },
    ).json()

    assert second["id"] == first["id"]
    assert second["channel"] == "email"
    assert [message["provider"] for message in second["messages"]] == [
        "chatwoot",
        "chatwoot",
    ]


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


def test_approve_send_uses_dry_run_without_chatwoot_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_BASE_URL", "")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "")
    get_settings.cache_clear()

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


def test_approve_send_records_policy_metadata_in_chatwoot_tool_result() -> None:
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 3901,
            "content": "I need to cancel and get a refund.",
            "message_type": "incoming",
            "conversation": {"id": 390},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": True, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    tool_result = next(
        result
        for result in payload["tool_results"]
        if result["tool_name"] == "chatwoot.messages.send_approved"
    )
    assert_policy_metadata(
        tool_result,
        supervisor_id="qa-lead",
        risk_level=created["risk_level"],
    )


def test_approve_send_records_outbound_message_in_same_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_DRY_RUN", "true")
    get_settings.cache_clear()

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


def test_approve_send_failure_records_chatwoot_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_BASE_URL", "https://chat.example.test")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "bad-token")
    monkeypatch.setenv("CHATWOOT_DRY_RUN", "false")
    get_settings.cache_clear()

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            json={"errors": ["You need to sign in or sign up before continuing."]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 5001,
            "content": "How much is an AC tune-up?",
            "message_type": "incoming",
            "conversation": {"id": 500},
            "sender": {"name": "Send Failure Customer"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": True, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "send_failed"
    assert payload["send_status"] == "failed"
    assert payload["tool_results"][0]["provider"] == "Chatwoot"
    assert payload["tool_results"][0]["status"] == "failed"
    assert "HTTP 401" in payload["tool_results"][0]["detail"]
    assert payload["tool_results"][0]["data"]["http_status"] == 401
    assert "sign in or sign up" in payload["tool_results"][0]["data"]["response_excerpt"]

    events = client.get(
        "/diagnostics/events",
        params={"conversation_id": created["id"]},
    ).json()["events"]
    assert any(event["event_type"] == "chatwoot.send.failed" for event in events)


def test_get_conversation_fetches_chatwoot_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_BASE_URL", "https://chat.example.test")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "good-token")
    get_settings.cache_clear()

    async def mock_get(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 610,
                "channel": "Channel::Email",
                "can_reply": True,
                "unread_count": 3,
                "last_activity_at": 1_780_000_000,
                "source_id": "source-email-123",
                "status": "open",
                "priority": "high",
                "labels": ["refund"],
                "waiting_since": 1_780_000_030,
                "inbox": {
                    "id": 44,
                    "name": "Support Email",
                    "channel_type": "Channel::Email",
                    "provider": "email",
                },
                "meta": {"sender": {"last_seen_at": 1_780_000_010}},
                "assignee": {"last_seen_at": 1_780_000_020},
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    created = client.post(
        "/webhooks/chatwoot",
        json={"id": 6101, "content": "I emailed you.", "conversation": {"id": 610}},
    ).json()

    response = client.get(f"/conversations/{created['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "email"
    assert payload["chatwoot_context"]["fetch_status"] == "ready"
    assert payload["chatwoot_context"]["unread_count"] == 3
    assert payload["chatwoot_context"]["can_reply"] is True
    assert payload["chatwoot_context"]["source_id"] == "source-email-123"
    assert payload["chatwoot_context"]["inbox"]["name"] == "Support Email"


def test_get_conversation_details_failure_keeps_local_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_BASE_URL", "https://chat.example.test")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "bad-token")
    get_settings.cache_clear()

    async def mock_get(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(503, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    created = client.post(
        "/webhooks/chatwoot",
        json={"id": 6201, "content": "Local fallback.", "conversation": {"id": 620}},
    ).json()

    response = client.get(f"/conversations/{created['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created["id"]
    assert payload["chatwoot_context"]["fetch_status"] == "failed"
    assert "HTTP 503" in payload["chatwoot_context"]["fetch_error"]


def test_approve_send_blocks_when_chatwoot_cannot_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        raise AssertionError("Chatwoot send should not be called.")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden_post)
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6301,
            "content": "Can you reply?",
            "conversation": {"id": 630, "can_reply": False, "source_id": "closed-source"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/approve-send",
        json={"approved": True, "supervisor_id": "qa-lead"},
    )

    assert response.status_code == 409
    assert "cannot receive replies" in response.json()["detail"]


def test_resolve_conversation_blocks_when_chatwoot_dry_run() -> None:
    client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "public-inbox",
            "api_access_token": "secret-token",
            "enabled": True,
            "dry_run": True,
        },
    )
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6401,
            "content": "Thanks, that answers it.",
            "conversation": {"id": 640, "source_id": "source-640", "status": "open"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 409
    assert "dry-run" in response.json()["detail"].lower()


def test_resolve_conversation_requires_source_id_and_inbox_identifier() -> None:
    client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "api_access_token": "secret-token",
            "enabled": True,
            "dry_run": False,
        },
    )
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6501,
            "content": "Close this.",
            "conversation": {"id": 650, "status": "open"},
        },
    ).json()

    missing_source = client.post(
        f"/conversations/{created['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor"},
    )
    assert missing_source.status_code == 409
    assert "source" in missing_source.json()["detail"].lower()

    with_source = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6502,
            "content": "My source is available now.",
            "conversation": {"id": 651, "source_id": "source-651", "status": "open"},
        },
    ).json()
    missing_inbox = client.post(
        f"/conversations/{with_source['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor"},
    )
    assert missing_inbox.status_code == 409
    missing_inbox_detail = missing_inbox.json()["detail"]
    assert "CHATWOOT_INBOX_IDENTIFIER" in missing_inbox_detail
    assert "not the numeric inbox_id" in missing_inbox_detail


def test_resolve_conversation_records_successful_chatwoot_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "public-inbox",
            "api_access_token": "secret-token",
            "enabled": True,
            "dry_run": False,
        },
    )

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        assert url == "https://chat.example.test/api/v1/accounts/1/conversations/660/toggle_status"
        assert kwargs["headers"] == {"api_access_token": "secret-token"}
        assert kwargs.get("json") == {"status": "resolved"}
        return httpx.Response(
            200,
            json={"id": 660, "status": "resolved"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6601,
            "content": "You can close this now.",
            "conversation": {"id": 660, "source_id": "source-660", "status": "open"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chatwoot_context"]["status"] == "resolved"
    assert any(
        result["tool_name"] == "chatwoot.conversations.resolve"
        and result["status"] == "succeeded"
        for result in payload["tool_results"]
    )
    assert any(
        item["memory_type"] == "resolution_state"
        and "resolved" in item["content"].lower()
        for item in payload["memory_context"]
    )


def test_resolve_conversation_records_policy_metadata_in_chatwoot_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "public-inbox",
            "api_access_token": "secret-token",
            "enabled": True,
            "dry_run": False,
        },
    )

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": 661, "status": "resolved"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6611,
            "content": "You can close this now.",
            "conversation": {"id": 661, "source_id": "source-661", "status": "open"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor", "X-Sagad-User-Id": "qa-lead"},
    )

    assert response.status_code == 200
    payload = response.json()
    tool_result = next(
        result
        for result in payload["tool_results"]
        if result["tool_name"] == "chatwoot.conversations.resolve"
    )
    assert_policy_metadata(
        tool_result,
        supervisor_id="qa-lead",
        risk_level="medium",
    )


def test_resolve_conversation_records_failed_chatwoot_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.put(
        "/integration-configs/chatwoot",
        headers={"X-Sagad-Role": "owner"},
        json={
            "base_url": "https://chat.example.test",
            "account_id": "1",
            "inbox_id": "public-inbox",
            "api_access_token": "secret-token",
            "enabled": True,
            "dry_run": False,
        },
    )

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": "Not found"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 6701,
            "content": "Close this too.",
            "conversation": {"id": 670, "source_id": "source-670", "status": "open"},
        },
    ).json()

    response = client.post(
        f"/conversations/{created['id']}/resolve",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chatwoot_context"]["status"] == "open"
    assert any(
        result["tool_name"] == "chatwoot.conversations.resolve"
        and result["status"] == "failed"
        and result["data"]["http_status"] == 404
        for result in payload["tool_results"]
    )


def test_integration_configs_show_runtime_chatwoot_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATWOOT_BASE_URL", "https://chat.example.test")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "runtime-token")
    monkeypatch.setenv("CHATWOOT_WEBHOOK_TOKEN", "runtime-webhook")
    monkeypatch.setenv("CHATWOOT_DRY_RUN", "false")
    get_settings.cache_clear()

    response = client.get(
        "/integration-configs",
        headers={"X-Sagad-Role": "supervisor"},
    )

    assert response.status_code == 200
    chatwoot = next(
        item for item in response.json()["connections"] if item["provider"] == "chatwoot"
    )
    assert chatwoot["configured"] is True
    assert chatwoot["enabled"] is True
    assert chatwoot["status"] == "ready"
    assert chatwoot["base_url"] == "https://chat.example.test"
    assert chatwoot["has_api_access_token"] is True
    assert chatwoot["has_webhook_token"] is True
    assert "environment variables" in chatwoot["detail"]
    assert "runtime-token" not in response.text


def test_diagnostics_events_are_listed_after_webhook() -> None:
    created = client.post(
        "/webhooks/chatwoot",
        json={
            "id": 5101,
            "content": "I need support.",
            "message_type": "incoming",
            "conversation": {"id": 510},
            "sender": {"name": "Diagnostics Customer"},
        },
    ).json()

    response = client.get(
        "/diagnostics/events",
        params={"conversation_id": created["id"]},
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert any(event["event_type"] == "chatwoot.webhook.persisted" for event in events)
    assert all(event["conversation_id"] == created["id"] for event in events)


def test_twenty_disabled_health_state() -> None:
    response = client.get("/integrations/twenty/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "Twenty CRM"
    assert payload["status"] == "disabled"
    assert payload["external"] is True


def test_litellm_disabled_health_state() -> None:
    response = client.get("/integrations/litellm/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "LiteLLM Gateway"
    assert payload["status"] == "disabled"
    assert payload["kind"] == "tool_layer"


def test_litellm_enabled_without_base_url_reports_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_ENABLED", "true")
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    get_settings.cache_clear()

    response = client.get("/integrations/litellm/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "LiteLLM Gateway"
    assert payload["status"] == "unconfigured"
    assert "LITELLM_BASE_URL" in payload["detail"]


def test_health_ready_returns_preview_readiness() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "agent-studio"
    assert payload["knowledge_records"] >= 1


def test_integrations_use_generic_webhooks_not_n8n() -> None:
    response = client.get("/integrations")

    assert response.status_code == 200
    integrations = response.json()["integrations"]
    providers = [item["provider"] for item in integrations]
    assert "Generic Webhooks" in providers
    assert "LiteLLM Gateway" in providers
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
    assert_policy_metadata(
        payload["result"],
        supervisor_id="demo-supervisor",
        risk_level="medium",
    )


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


def test_update_lead_stage_uses_conversation_agent_and_blocks_support_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWENTY_ENABLED", "true")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_DRY_RUN", "true")
    get_settings.cache_clear()
    record = store.save(
        ConversationRecord(
            id="conv_support_policy",
            incoming_message="I need help with my service.",
            selected_agent="Support Agent",
            risk_level="low",
        )
    )

    response = client.post(
        "/tools/crm/update-lead-stage",
        json={
            "contact_id": "person_123",
            "lead_stage": "qualified",
            "conversation_id": record.id,
            "selected_agent": "Sales Agent",
            "approved": True,
            "supervisor_id": "qa-lead",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "blocked"
    assert "Support Agent is not allowed" in payload["result"]["detail"]
    policy_metadata = payload["result"]["data"]["policy_metadata"]
    assert policy_metadata["allowed"] is False
    assert policy_metadata["approved"] is True
    assert policy_metadata["supervisor_id"] == "qa-lead"
    assert policy_metadata["risk_level"] == "high"


def test_update_lead_stage_sales_agent_requires_and_accepts_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWENTY_ENABLED", "true")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_DRY_RUN", "true")
    get_settings.cache_clear()

    without_approval = client.post(
        "/tools/crm/update-lead-stage",
        json={
            "contact_id": "person_123",
            "lead_stage": "qualified",
            "selected_agent": "Sales Agent",
            "approved": False,
        },
    )
    assert without_approval.status_code == 403
    assert "approval" in without_approval.json()["detail"].lower()

    with_approval = client.post(
        "/tools/crm/update-lead-stage",
        json={
            "contact_id": "person_123",
            "lead_stage": "qualified",
            "selected_agent": "Sales Agent",
            "approved": True,
            "supervisor_id": "qa-lead",
        },
    )

    assert with_approval.status_code == 200
    payload = with_approval.json()
    assert payload["result"]["status"] == "dry_run"
    assert payload["plan"]["approved"] is True
    assert payload["result"]["data"]["policy_metadata"]["allowed"] is True
    assert_policy_metadata(
        payload["result"],
        supervisor_id="qa-lead",
        risk_level="high",
    )


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


def test_chatwoot_webhook_auto_sends_low_risk_high_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import patch, AsyncMock
    monkeypatch.setenv("CHATWOOT_DRY_RUN", "true")
    get_settings.cache_clear()
    final_state = {
        "chatwoot_conversation_id": "88",
        "chatwoot_message_id": "8801",
        "customer_name": "Test Customer",
        "channel": "chatwoot",
        "incoming_message": "Hello",
        "normalized_message": "Hello",
        "intent": "general_support",
        "risk_level": "low",
        "retrieved_knowledge": [],
        "draft_reply": "Hello! I can help you with that.",
        "qa_findings": [],
        "compliance_status": "pass",
        "retrieval_confidence": 0.90,
        "final_confidence_score": 0.90,
        "trace_url": "https://smith.langchain.com/trace",
    }
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post(
            "/webhooks/chatwoot",
            json={
                "id": 8801,
                "content": "Hello",
                "message_type": "incoming",
                "conversation": {"id": 88},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["approval_status"] == "sent"
        assert payload["send_status"] == "dry_run"
        assert len(payload["messages"]) == 2
        assert payload["messages"][1]["sender_type"] == "ai_agent"
        assert payload["messages"][1]["body"] == "Hello! I can help you with that."


def test_chatwoot_webhook_requires_approval_if_risk_is_high() -> None:
    from unittest.mock import patch, AsyncMock
    final_state = {
        "chatwoot_conversation_id": "88",
        "chatwoot_message_id": "8801",
        "customer_name": "Test Customer",
        "channel": "chatwoot",
        "incoming_message": "Hello",
        "normalized_message": "Hello",
        "intent": "general_support",
        "risk_level": "high",
        "retrieved_knowledge": [],
        "draft_reply": "Hello! I can help you with that.",
        "qa_findings": [],
        "compliance_status": "pass",
        "retrieval_confidence": 0.90,
        "final_confidence_score": 0.90,
        "trace_url": "https://smith.langchain.com/trace",
    }
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post(
            "/webhooks/chatwoot",
            json={
                "id": 8801,
                "content": "Hello",
                "message_type": "incoming",
                "conversation": {"id": 88},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["approval_status"] == "needs_approval"
        assert payload["send_status"] == "not_sent"


def test_chatwoot_webhook_requires_approval_if_confidence_is_low() -> None:
    from unittest.mock import patch, AsyncMock
    final_state = {
        "chatwoot_conversation_id": "88",
        "chatwoot_message_id": "8801",
        "customer_name": "Test Customer",
        "channel": "chatwoot",
        "incoming_message": "Hello",
        "normalized_message": "Hello",
        "intent": "general_support",
        "risk_level": "low",
        "retrieved_knowledge": [],
        "draft_reply": "Hello! I can help you with that.",
        "qa_findings": [],
        "compliance_status": "pass",
        "retrieval_confidence": 0.80,
        "final_confidence_score": 0.80,
        "trace_url": "https://smith.langchain.com/trace",
    }
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post(
            "/webhooks/chatwoot",
            json={
                "id": 8801,
                "content": "Hello",
                "message_type": "incoming",
                "conversation": {"id": 88},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["approval_status"] == "needs_approval"
        assert payload["send_status"] == "not_sent"


def test_chatwoot_webhook_requires_approval_if_compliance_not_pass() -> None:
    from unittest.mock import patch, AsyncMock
    final_state = {
        "chatwoot_conversation_id": "88",
        "chatwoot_message_id": "8801",
        "customer_name": "Test Customer",
        "channel": "chatwoot",
        "incoming_message": "Hello",
        "normalized_message": "Hello",
        "intent": "general_support",
        "risk_level": "low",
        "retrieved_knowledge": [],
        "draft_reply": "Hello! I can help you with that.",
        "qa_findings": [],
        "compliance_status": "needs_review",
        "retrieval_confidence": 0.90,
        "final_confidence_score": 0.90,
        "trace_url": "https://smith.langchain.com/trace",
    }
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post(
            "/webhooks/chatwoot",
            json={
                "id": 8801,
                "content": "Hello",
                "message_type": "incoming",
                "conversation": {"id": 88},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["approval_status"] == "needs_approval"
        assert payload["send_status"] == "not_sent"


def test_chatwoot_webhook_no_auto_send_if_draft_empty() -> None:
    from unittest.mock import patch, AsyncMock
    final_state = {
        "chatwoot_conversation_id": "88",
        "chatwoot_message_id": "8801",
        "customer_name": "Test Customer",
        "channel": "chatwoot",
        "incoming_message": "Hello",
        "normalized_message": "Hello",
        "intent": "general_support",
        "risk_level": "low",
        "retrieved_knowledge": [],
        "draft_reply": "   ",
        "qa_findings": [],
        "compliance_status": "pass",
        "retrieval_confidence": 0.90,
        "final_confidence_score": 0.90,
        "trace_url": "https://smith.langchain.com/trace",
    }
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post(
            "/webhooks/chatwoot",
            json={
                "id": 8801,
                "content": "Hello",
                "message_type": "incoming",
                "conversation": {"id": 88},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["approval_status"] == "needs_approval"
        assert payload["send_status"] == "not_sent"

