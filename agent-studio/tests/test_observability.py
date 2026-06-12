from agent_studio.observability import (
    EventTypes,
    ProviderErrorCategory,
    SpanNames,
    aggregate_ai_ops_metrics,
    categorize_provider_error,
    sanitize_payload,
    span_name_for,
)
from agent_studio.schemas import ConversationRecord, DiagnosticEvent, ToolResult


def test_observability_taxonomy_and_span_names_are_stable() -> None:
    assert EventTypes.PROVIDER_ERROR == "provider.error"
    assert EventTypes.DRAFT_CREATED == "draft.created"
    assert SpanNames.DRAFT_GENERATION == "agent_studio.draft.generate"

    assert span_name_for("draft_reply") == SpanNames.DRAFT_GENERATION
    assert span_name_for("chatwoot.webhook.persisted") == SpanNames.WEBHOOK_INGEST
    assert span_name_for("conversation-510-sensitive") == SpanNames.UNKNOWN


def test_sanitize_payload_redacts_secrets_provider_bodies_and_pii() -> None:
    payload = {
        "api_key": "sk-live-secret-value",
        "headers": {"Authorization": "Bearer provider-token-123"},
        "webhook_secret": "whsec_123456789",
        "provider_response_body": {
            "customer": "Avery Person",
            "email": "avery.person@example.com",
            "phone": "+1 (415) 555-0135",
        },
        "notes": "Email avery.person@example.com or call +1 (415) 555-0135.",
        "transcript": [
            {"role": "customer", "content": "My email is avery.person@example.com"},
            {"role": "agent", "content": "I can help."},
        ],
        "long_text": "x" * 80,
    }

    sanitized = sanitize_payload(payload, max_string_length=32)
    rendered = str(sanitized)

    assert "sk-live-secret-value" not in rendered
    assert "provider-token-123" not in rendered
    assert "whsec_123456789" not in rendered
    assert "avery.person@example.com" not in rendered
    assert "415) 555-0135" not in rendered
    assert "Avery Person" not in rendered
    assert sanitized["api_key"] == "[redacted]"
    assert sanitized["provider_response_body"] == "[redacted_provider_response]"
    assert sanitized["transcript"] == "[redacted_transcript]"
    assert str(sanitized["long_text"]).endswith("...[clipped]")


def test_categorize_provider_error_from_status_and_message() -> None:
    assert categorize_provider_error({"status_code": 401}).category == ProviderErrorCategory.AUTH
    assert categorize_provider_error({"status_code": 429}).category == ProviderErrorCategory.RATE_LIMITED
    assert categorize_provider_error({"status_code": 503}).retryable is True
    assert (
        categorize_provider_error({"message": "request timed out after 30s"}).category
        == ProviderErrorCategory.TIMEOUT
    )
    assert (
        categorize_provider_error({"message": "missing API key"}).category
        == ProviderErrorCategory.CONFIGURATION
    )


def test_aggregate_ai_ops_metrics_from_record_like_objects() -> None:
    conversations = [
        ConversationRecord(
            id="conv-1",
            incoming_message="Need pricing.",
            normalized_message="Need pricing.",
            intent="pricing_lead",
            risk_level="low",
            retrieval_confidence=0.8,
            missing_knowledge=False,
            approval_status="approved",
            send_status="sent",
            draft_reply="What service do you need pricing for?",
            trace_url="https://langsmith.example/r/1",
            tool_results=[
                ToolResult(
                    plan_id="plan-1",
                    tool_name="crm.lookup_contact",
                    status="succeeded",
                    detail="Lookup completed.",
                ),
            ],
        ),
        ConversationRecord(
            id="conv-2",
            incoming_message="Cancel my order.",
            normalized_message="Cancel my order.",
            intent="refund_or_cancellation",
            risk_level="high",
            retrieval_confidence=0.4,
            missing_knowledge=True,
            approval_status="needs_approval",
            send_status="not_sent",
        ),
    ]
    events = [
        DiagnosticEvent(
            conversation_id="conv-1",
            event_type=EventTypes.PROVIDER_ERROR,
            status="error",
            summary="Provider failed.",
            payload={"status_code": 429, "provider": "Chatwoot"},
        ),
        {
            "conversation_id": "conv-2",
            "event_type": EventTypes.RETRIEVAL_NO_MATCH,
            "status": "warning",
            "summary": "No confident source.",
            "payload": {},
        },
    ]

    metrics = aggregate_ai_ops_metrics(conversations, events)

    assert metrics["conversation_count"] == 2
    assert metrics["approval_status_counts"] == {"approved": 1, "needs_approval": 1}
    assert metrics["risk_level_counts"] == {"high": 1, "low": 1}
    assert metrics["missing_knowledge_count"] == 1
    assert metrics["avg_retrieval_confidence"] == 0.6
    assert metrics["drafted_count"] == 1
    assert metrics["trace_linked_count"] == 1
    assert metrics["tool_result_status_counts"] == {"succeeded": 1}
    assert metrics["diagnostic_event_type_counts"][EventTypes.PROVIDER_ERROR] == 1
    assert metrics["provider_error_category_counts"] == {
        ProviderErrorCategory.RATE_LIMITED: 1,
    }
