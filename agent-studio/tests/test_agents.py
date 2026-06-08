import os
import pytest
from unittest.mock import patch, MagicMock
from agent_studio.agents import AgentRegistry, AgentConfig
from agent_studio.graph import draft_reply, select_markdown_agent
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

@patch("agent_studio.graph.litellm.completion")
def test_draft_reply_with_litellm(mock_completion):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a mocked response."
    mock_response.choices[0].message.tool_calls = None
    mock_completion.return_value = mock_response

    state: AgentStudioState = {
        "incoming_message": "hello",
        "normalized_message": "hello",
        "intent": "general_support",
        "risk_level": "low"
    }

    result = draft_reply(state)

    assert result["draft_reply"] == "This is a mocked response."
    
    # Check that litellm was called correctly
    mock_completion.assert_called_once()
    kwargs = mock_completion.call_args.kwargs
    assert "messages" in kwargs
    
    # general_support should map to crm.lookup_contact tool
    assert "tools" in kwargs
    tools = kwargs["tools"]
    assert tools is not None
    assert tools[0]["function"]["name"] == "crm.lookup_contact"


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
