import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

@pytest.fixture(autouse=True)
def mock_chat_model():
    with patch("agent_studio.graph._build_chat_model") as mock_build:
        # Create a mock LLM that returns an AIMessage
        mock_llm = MagicMock()
        mock_response = AIMessage(
            content="Thanks. I can help route this to the right team. Are you looking for pricing or booking help, or support with an existing service?"
        )
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        mock_build.return_value = mock_llm
        yield mock_build
