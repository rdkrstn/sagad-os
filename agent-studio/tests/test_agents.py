from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from agent_studio.agents import AgentRegistry
from agent_studio.graph import select_markdown_agent, supervisor_draft
from agent_studio.state import AgentStudioState

def test_agent_registry_parsing(tmp_path):
    # Create a temporary agent markdown file
    agent_file = tmp_path / "test_agent.md"
    agent_file.write_text("""---
name: test_agent
intents: ["test_intent"]
allowed_tools: ["crm.lookup_contact"]
---
You are a test agent.
""", encoding="utf-8")

    registry = AgentRegistry(agents_dir=str(tmp_path))
    agent = registry.get_agent("test_intent")
    
    assert agent is not None
    assert agent.name == "test_agent"
    assert agent.intents == ["test_intent"]
    assert agent.allowed_tools == ["crm.lookup_contact"]
    assert agent.system_prompt == "You are a test agent."


@patch("agent_studio.graph._build_chat_model")
def test_supervisor_draft_with_langchain(mock_build):
    mock_llm = MagicMock()
    mock_response = AIMessage(content="This is a mocked supervisor response.")
    mock_llm.invoke.return_value = mock_response
    mock_llm.bind_tools.return_value = mock_llm
    mock_build.return_value = mock_llm

    state: AgentStudioState = {
        "incoming_message": "hello",
        "normalized_message": "hello",
        "sub_agent_report": {"agent": "general_support", "analysis": "greeting"},
    }

    result = supervisor_draft(state)

    assert "This is a mocked supervisor response" in result["draft_reply"]


def test_refund_intent_selects_refund_resolver_agent():
    state: AgentStudioState = {
        "incoming_message": "I need a refund.",
        "normalized_message": "I need a refund.",
        "intent": "refund_or_cancellation",
        "risk_level": "high",
    }

    result = select_markdown_agent(state)

    assert result["selected_agent"] == "refund_resolver"
    assert result["customer_driver"] == "refund or cancellation"


def test_pricing_intent_selects_sales_agent():
    state: AgentStudioState = {
        "incoming_message": "I already said pricing.",
        "normalized_message": "I already said pricing.",
        "intent": "pricing_lead",
        "risk_level": "low",
    }

    result = select_markdown_agent(state)

    assert result["selected_agent"] == "sales_agent"
    assert result["customer_driver"] == "pricing or quote"


def test_agent_config_has_id(tmp_path):
    agent_file = tmp_path / "test_bot.md"
    agent_file.write_text("""---
name: test_bot
intents: ["greeting"]
allowed_tools: []
---
Hello bot.
""", encoding="utf-8")
    registry = AgentRegistry(agents_dir=str(tmp_path))
    agent = registry.get_agent("greeting")
    assert agent is not None
    assert agent.id == "test_bot"


def test_save_agent(tmp_path):
    registry = AgentRegistry(agents_dir=str(tmp_path))
    saved = registry.save_agent(
        agent_id="billing_agent",
        name="Billing Agent",
        intents=["billing_inquiry"],
        allowed_tools=["crm.lookup_contact"],
        system_prompt="You are a billing agent.",
    )
    assert saved.id == "billing_agent"
    assert saved.name == "Billing Agent"
    assert (tmp_path / "billing_agent.md").exists()

    # Verify it was loaded into the registry
    agent = registry.get_agent("billing_inquiry")
    assert agent is not None
    assert agent.name == "Billing Agent"


def test_save_agent_rename(tmp_path):
    registry = AgentRegistry(agents_dir=str(tmp_path))
    registry.save_agent(
        agent_id="old_agent",
        name="Old Agent",
        intents=["old_intent"],
        allowed_tools=[],
        system_prompt="Old prompt.",
    )
    assert (tmp_path / "old_agent.md").exists()

    registry.save_agent(
        agent_id="new_agent",
        name="New Agent",
        intents=["new_intent"],
        allowed_tools=[],
        system_prompt="New prompt.",
        original_id="old_agent",
    )
    assert not (tmp_path / "old_agent.md").exists()
    assert (tmp_path / "new_agent.md").exists()


def test_delete_agent(tmp_path):
    registry = AgentRegistry(agents_dir=str(tmp_path))
    registry.save_agent(
        agent_id="temp_agent",
        name="Temp Agent",
        intents=["temp_intent"],
        allowed_tools=[],
        system_prompt="Temporary.",
    )
    assert (tmp_path / "temp_agent.md").exists()

    deleted = registry.delete_agent("temp_agent")
    assert deleted is True
    assert not (tmp_path / "temp_agent.md").exists()
    assert registry.get_agent("temp_intent") is None


def test_delete_nonexistent_agent(tmp_path):
    registry = AgentRegistry(agents_dir=str(tmp_path))
    deleted = registry.delete_agent("nonexistent")
    assert deleted is False
