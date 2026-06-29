from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from agent_studio.agents import AgentRegistry
from agent_studio.graph import (
    _build_chat_model_for_agent,
    select_markdown_agent,
    supervisor_draft,
)
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


def test_agent_metadata_defaults_empty(tmp_path):
    """Agents whose .md predates the new fields load with empty-string defaults."""
    agent_file = tmp_path / "legacy.md"
    agent_file.write_text(
        '---\nname: legacy\nintents: ["legacy_intent"]\nallowed_tools: []\n---\nBody.\n',
        encoding="utf-8",
    )
    registry = AgentRegistry(agents_dir=str(tmp_path))
    agent = registry.get_agent("legacy_intent")
    assert agent is not None
    assert agent.description == ""
    assert agent.model == ""
    assert agent.tier == ""
    assert agent.voice == ""


def test_save_agent_persists_and_reloads_metadata(tmp_path):
    """save_agent writes the optional metadata to frontmatter and reloads it back."""
    registry = AgentRegistry(agents_dir=str(tmp_path))
    saved = registry.save_agent(
        agent_id="billing_agent",
        name="Billing Agent",
        intents=["billing_inquiry"],
        allowed_tools=["crm.lookup_contact"],
        system_prompt="You are a billing agent.",
        description="Handles billing questions and payment issues.",
        model="openai/gpt-4o-mini",
        tier="managed",
        voice="warm, concise",
    )
    assert saved.description == "Handles billing questions and payment issues."
    assert saved.model == "openai/gpt-4o-mini"
    assert saved.tier == "managed"
    assert saved.voice == "warm, concise"

    # The metadata is written to the .md frontmatter.
    content = (tmp_path / "billing_agent.md").read_text(encoding="utf-8")
    assert "description:" in content
    assert "model:" in content
    assert "tier:" in content
    assert "voice:" in content

    # And a fresh registry reloads it.
    reloaded = AgentRegistry(agents_dir=str(tmp_path)).get_agent("billing_inquiry")
    assert reloaded is not None
    assert reloaded.description == "Handles billing questions and payment issues."
    assert reloaded.model == "openai/gpt-4o-mini"
    assert reloaded.tier == "managed"
    assert reloaded.voice == "warm, concise"


def test_save_agent_omits_empty_metadata(tmp_path):
    """Empty metadata is not written, keeping the .md minimal."""
    registry = AgentRegistry(agents_dir=str(tmp_path))
    registry.save_agent(
        agent_id="plain_agent",
        name="Plain Agent",
        intents=["plain_intent"],
        allowed_tools=[],
        system_prompt="Body.",
    )
    content = (tmp_path / "plain_agent.md").read_text(encoding="utf-8")
    assert "description:" not in content
    assert "model:" not in content
    assert "tier:" not in content
    assert "voice:" not in content


def test_build_chat_model_for_agent_delegates_when_no_override():
    """With no per-agent model override, the helper delegates to _build_chat_model."""
    agent = MagicMock()
    agent.model = ""
    with patch("agent_studio.graph._build_chat_model") as mock_build:
        mock_build.return_value = "delegated"
        result = _build_chat_model_for_agent(agent, "extractor")
    mock_build.assert_called_once_with("extractor")
    assert result == "delegated"


def test_build_chat_model_for_agent_override_uses_agent_model(monkeypatch):
    """A set model override is used with the resolved provider credentials."""
    agent = MagicMock()
    agent.model = "openai/gpt-4o-mini"

    monkeypatch.delenv("LLM_MODE", raising=False)

    cfg = MagicMock()
    cfg.configured = True
    cfg.model = "openai/default-model"
    cfg.api_base = "https://gateway.example.com"
    cfg.api_key = "secret"

    # _build_chat_model_for_agent imports these names locally, so patch the source modules.
    monkeypatch.setattr("agent_studio.model_config.resolve_chat_config", lambda *a, **k: cfg)
    monkeypatch.setattr(
        "agent_studio.integration_config.configured_settings",
        lambda settings, context=None: settings,
    )

    wrapper = _build_chat_model_for_agent(agent, "extractor")
    assert wrapper.model == "openai/gpt-4o-mini"


def test_agent_registry_singleton_shared_between_api_and_graph():
    """POST /agents (main.agent_registry) and the graph (get_agent_registry) must share the
    SAME registry instance, so save_agent's in-place reload_agents() makes edits visible to the
    running pipeline without a process restart. If this invariant breaks, agent edits silently
    never reach the graph until the server is restarted.
    """
    from agent_studio.main import agent_registry
    from agent_studio.graph import get_agent_registry

    assert agent_registry is get_agent_registry()
