import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from agent_studio.embeddings import deterministic_embedding

from fastapi.testclient import TestClient
from agent_studio.config import get_settings

# Patch EmbeddingService.embed_text at import time to prevent live OpenAI API calls during test collection
patch("agent_studio.embeddings.EmbeddingService.embed_text", side_effect=deterministic_embedding).start()

# Patch TestClient.request to automatically inject the configured internal secret and webhook token from settings if set
original_request = TestClient.request

def custom_request(self, method, url, *args, **kwargs):
    settings = get_settings()
    
    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
        kwargs["headers"] = headers
    else:
        if isinstance(headers, list):
            headers = dict(headers)
            kwargs["headers"] = headers
    
    # 1. Inject internal secret if configured
    if settings.agent_studio_internal_secret and "x-sagad-internal-secret" not in headers:
        headers["x-sagad-internal-secret"] = settings.agent_studio_internal_secret
        
    # 2. Inject webhook token if calling chatwoot webhook
    if "/webhooks/chatwoot" in str(url) and settings.chatwoot_webhook_token:
        params = kwargs.get("params")
        if params is None:
            params = {}
            kwargs["params"] = params
        else:
            if isinstance(params, list):
                params = dict(params)
                kwargs["params"] = params
            elif isinstance(params, str):
                # If params is a query string, we don't modify it easily, but usually it's a dict/list
                pass
        
        if isinstance(params, dict):
            token_in_params = "token" in params
            token_in_headers = "x-chatwoot-token" in headers or "x-chatwoot-token".lower() in {k.lower() for k in headers}
            if not token_in_params and not token_in_headers:
                params["token"] = settings.chatwoot_webhook_token
            
    return original_request(self, method, url, *args, **kwargs)


TestClient.request = custom_request


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
