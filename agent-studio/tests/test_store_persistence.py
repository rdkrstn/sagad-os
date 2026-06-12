import os
from pathlib import Path

import pytest

from agent_studio.config import Settings
from agent_studio.schemas import ConversationRecord, MemoryHit, ToolPlan, ToolResult
from agent_studio.store import (
    InMemoryConversationStore,
    PostgresConversationStore,
    StoreContext,
    build_store,
)


def test_build_store_uses_in_memory_without_database_url() -> None:
    conversation_store = build_store(Settings(database_url=None))

    assert isinstance(conversation_store, InMemoryConversationStore)


def test_store_context_uses_organization_id_boundary() -> None:
    context = StoreContext(
        organization_id="ca41b97f-f546-453b-8b75-62068f23a414",
        user_id="1",
        role="supervisor",
    )

    assert context.organization_id == "ca41b97f-f546-453b-8b75-62068f23a414"
    assert not hasattr(context, "org_id")


def test_foundation_migration_defines_auth_pgvector_and_sagad_tables() -> None:
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "0001_sagad_foundation.sql"
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "CREATE TABLE IF NOT EXISTS verification_token" in migration
    assert "CREATE TABLE IF NOT EXISTS users" in migration
    assert "CREATE TABLE IF NOT EXISTS sessions" in migration
    assert "CREATE TABLE IF NOT EXISTS organizations" in migration
    assert "CREATE TABLE IF NOT EXISTS profiles" in migration
    assert "CREATE TABLE IF NOT EXISTS conversation_messages" in migration
    assert "CREATE TABLE IF NOT EXISTS integration_connections" in migration
    assert "CREATE TABLE IF NOT EXISTS integration_secret_versions" in migration
    assert "CREATE TABLE IF NOT EXISTS knowledge_chunk_embeddings" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration


def test_ingestion_migration_defines_sources_jobs_errors_and_rls() -> None:
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "0002_knowledge_ingestion.sql"
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS knowledge_sources" in migration
    assert "CREATE TABLE IF NOT EXISTS knowledge_ingestion_jobs" in migration
    assert "CREATE TABLE IF NOT EXISTS knowledge_ingestion_errors" in migration
    assert "ADD COLUMN IF NOT EXISTS source_id" in migration
    assert "ADD COLUMN IF NOT EXISTS last_ingestion_job_id" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration


def test_memory_migration_defines_conversation_memory_items_and_rls() -> None:
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "0005_conversation_memory.sql"
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS conversation_memory_items" in migration
    assert "memory_type" in migration
    assert "embedding vector(1536)" in migration
    assert "conversation_memory_items_org_thread_idx" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "conversation_memory_items_org_isolation" in migration


def test_quality_migration_defines_eval_tables_quality_fields_and_rls() -> None:
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "0006_ai_ops_quality_layer.sql"
    migration = migration_path.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS eval_tags" in migration
    assert "ADD COLUMN IF NOT EXISTS trace_attributes" in migration
    assert "ADD COLUMN IF NOT EXISTS diagnostic_payload" in migration
    assert "ADD COLUMN IF NOT EXISTS decision_reason" in migration
    assert "ADD COLUMN IF NOT EXISTS guardrail_findings" in migration
    assert "ADD COLUMN IF NOT EXISTS confidence_breakdown" in migration
    assert "ADD COLUMN IF NOT EXISTS final_confidence_score" in migration
    assert "ADD COLUMN IF NOT EXISTS quality_score" in migration
    assert "ADD COLUMN IF NOT EXISTS quality_label" in migration
    assert "ADD COLUMN IF NOT EXISTS quality_signals" in migration
    assert "ADD COLUMN IF NOT EXISTS quality_notes" in migration
    assert "ADD COLUMN IF NOT EXISTS quality_evaluated_at" in migration
    assert "CREATE TABLE IF NOT EXISTS eval_runs" in migration
    assert "CREATE TABLE IF NOT EXISTS eval_results" in migration
    assert "eval_runs_org_started_idx" in migration
    assert "eval_results_run_case_idx" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "eval_runs_org_isolation" in migration
    assert "eval_results_org_isolation" in migration


def test_in_memory_store_persists_and_ranks_memory_items() -> None:
    conversation_store = InMemoryConversationStore()
    conversation = conversation_store.save(
        ConversationRecord(
            id="conv-memory",
            chatwoot_conversation_id="42",
            incoming_message="hmmm pricing",
            normalized_message="hmmm pricing",
            intent="pricing_lead",
            draft_reply="Which service do you need pricing for?",
        ),
    )

    conversation_store.append_memory_items(
        conversation.id,
        [
            MemoryHit(
                memory_type="unresolved_ask",
                content="Customer asked about pricing.",
                source="conversation",
                score=0.8,
            ),
            MemoryHit(
                memory_type="prior_intent",
                content="Customer driver: pricing or quote.",
                source="conversation",
                score=0.7,
            ),
        ],
    )

    hits = conversation_store.list_memory_items(
        conversation.id,
        query="I already said pricing",
        limit=2,
    )

    assert len(hits) == 2
    assert hits[0].score >= hits[1].score
    assert any("pricing" in hit.content.lower() for hit in hits)


def test_in_memory_store_records_eval_runs_results_and_quality_fields() -> None:
    conversation_store = InMemoryConversationStore()
    saved = conversation_store.save(
        ConversationRecord(
            id="conv-quality",
            incoming_message="Can you help with billing?",
            normalized_message="Can you help with billing?",
            intent="support",
            draft_reply="I can help with billing.",
        ),
    )

    updated = conversation_store.update_conversation_quality(
        saved.id,
        eval_tags=["sprint4", "fixture"],
        trace_attributes={"span": "agent_studio.qa.review"},
        diagnostic_payload={"latency_ms": 120},
        decision_reason="Ready for supervisor approval.",
        guardrail_findings=[
            {
                "label": "Knowledge basis",
                "status": "pass",
                "detail": "Draft cites approved source.",
            },
        ],
        confidence_breakdown={"retrieval": 0.9, "guardrail": 0.84},
        final_confidence_score=0.87,
        quality_score=0.87,
        quality_label="pass",
        quality_signals={"grounded": True, "policy_risk": "low"},
        quality_notes="Draft is grounded and ready for supervisor review.",
    )
    run = conversation_store.record_eval_run(
        {
            "id": "evalrun_quality_smoke",
            "name": "Sprint 4 quality smoke",
            "suite_name": "ai_ops_quality",
            "status": "running",
            "metadata": {"source": "pytest"},
        },
    )
    result = conversation_store.record_eval_result(
        {
            "id": "evalresult_quality_smoke_1",
            "eval_run_id": run["id"],
            "conversation_id": saved.id,
            "case_name": "billing_reply_grounding",
            "status": "passed",
            "score": 0.87,
            "input": {"message": saved.incoming_message},
            "expected": {"requires_grounded_reply": True},
            "actual": {"draft_reply": saved.draft_reply},
            "metrics": {"grounded": 1.0},
        },
    )
    summary_run = conversation_store.record_eval_run(
        {
            "run_id": "evalrun_builtin_summary",
            "case_count": 5,
            "passed_case_count": 4,
            "failed_case_count": 1,
            "overall_score": 0.8,
            "passed": False,
        },
    )
    summary_result = conversation_store.record_eval_result(
        {
            "id": "evalresult_builtin_summary_1",
            "eval_run_id": summary_run["id"],
            "case_id": "missing_knowledge_escalates",
            "name": "Unknown edge case escalates",
            "passed": False,
            "score": 0.5,
            "scores": [{"dimension": "retrieval", "score": 0.0}],
        },
    )

    loaded = conversation_store.get(saved.id)
    runs = conversation_store.list_eval_runs()
    runs_by_id = {item["id"]: item for item in runs}
    results = conversation_store.list_eval_results(run["id"])

    assert updated is not None
    assert loaded is not None
    assert getattr(loaded, "eval_tags") == ["sprint4", "fixture"]
    assert getattr(loaded, "trace_attributes") == {"span": "agent_studio.qa.review"}
    assert getattr(loaded, "diagnostic_payload") == {"latency_ms": 120}
    assert getattr(loaded, "decision_reason") == "Ready for supervisor approval."
    assert getattr(loaded, "guardrail_findings")[0].label == "Knowledge basis"
    assert getattr(loaded, "confidence_breakdown") == {"retrieval": 0.9, "guardrail": 0.84}
    assert getattr(loaded, "final_confidence_score") == 0.87
    assert getattr(loaded, "quality_score") == 0.87
    assert getattr(loaded, "quality_label") == "pass"
    assert getattr(loaded, "quality_signals") == {
        "grounded": True,
        "policy_risk": "low",
    }
    assert getattr(loaded, "quality_notes") == "Draft is grounded and ready for supervisor review."
    assert getattr(loaded, "quality_evaluated_at") is not None
    assert runs_by_id[summary_run["id"]] == summary_run
    assert runs_by_id[run["id"]] == run
    assert results == [result]
    assert summary_run["id"] == "evalrun_builtin_summary"
    assert summary_run["status"] == "failed"
    assert summary_run["total_cases"] == 5
    assert summary_run["passed_cases"] == 4
    assert summary_run["failed_cases"] == 1
    assert summary_run["average_score"] == 0.8
    assert summary_result["case_name"] == "Unknown edge case escalates"
    assert summary_result["status"] == "failed"
    assert summary_result["metrics"] == {
        "scores": [{"dimension": "retrieval", "score": 0.0}],
    }


@pytest.mark.skipif(
    not os.getenv("AGENT_STUDIO_TEST_DATABASE_URL"),
    reason="Postgres persistence test requires AGENT_STUDIO_TEST_DATABASE_URL.",
)
def test_postgres_store_persists_conversation_tools_and_audit() -> None:
    context = StoreContext(user_id="1", role="supervisor")
    conversation_store = build_store(
        Settings(database_url=os.environ["AGENT_STUDIO_TEST_DATABASE_URL"]),
    )
    assert isinstance(conversation_store, PostgresConversationStore)
    conversation_store.clear()

    conversation = ConversationRecord(
        incoming_message="Can you quote an AC tune-up?",
        normalized_message="Can you quote an AC tune-up?",
        intent="pricing_lead",
        draft_reply="What city are you in?",
    )

    saved = conversation_store.save(conversation, context=context)
    conversation_store.record_approval(
        saved,
        supervisor_id="1",
        approved=True,
        edited_reply="Approved quote follow-up.",
        context=context,
    )
    plan = ToolPlan(
        tool_name="crm.lookup_contact",
        action="Lookup contact in external Twenty CRM.",
        requires_approval=False,
        approved=True,
        dry_run=True,
        args={"query": "Avery", "conversation_id": saved.id},
    )
    result = ToolResult(
        plan_id=plan.id,
        tool_name=plan.tool_name,
        status="dry_run",
        detail="Twenty lookup was dry-run only.",
    )
    conversation_store.record_tool_execution(
        plan,
        result,
        conversation_id=saved.id,
        context=context,
    )

    loaded = conversation_store.get(saved.id, context=context)

    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.incoming_message == "Can you quote an AC tune-up?"
    assert loaded.tool_plans == [plan]
    assert loaded.tool_results == [result]
