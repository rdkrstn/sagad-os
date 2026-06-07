import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_litellm_completion():
    with patch("agent_studio.graph.litellm.completion") as mock_completion:
        # Create a mock response object matching litellm's ModelResponse
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Thanks. I can help route this to the right team. Are you looking for pricing or booking help, or support with an existing service?"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        
        mock_completion.return_value = mock_response
        yield mock_completion
