import os
from pathlib import Path

import pytest

from agent_studio.config import Settings
from agent_studio.schemas import ConversationRecord, ToolPlan, ToolResult
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
    assert "CREATE TABLE IF NOT EXISTS knowledge_chunk_embeddings" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration


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
