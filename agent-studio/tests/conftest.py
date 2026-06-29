import os

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

from fastapi.testclient import TestClient
from agent_studio.config import get_settings

# Force every store singleton to resolve InMemory for the test suite. The repo `.env` (loaded
# above by `agent_studio.config` and `agent_studio/__init__` via load_dotenv) sets DATABASE_URL
# to a Postgres that isn't running in CI/local sandboxes; without this, the module-level
# singletons (integration_config_store, model_provider_config_store) and the lazy store proxy
# build as Postgres backends and time out (5s) on first use — breaking any test that touches
# configured_settings(), the /integration-configs/*/test probe, /health/ready, setup_function's
# store.clear(), or the /webhooks/ghl path.
#
# We SET DATABASE_URL to an empty string rather than popping it: a transitive dependency
# (litellm, imported via embeddings -> model_config) calls load_dotenv() at import time, and
# load_dotenv(override=False) will *re-set* a variable that is absent (it only skips vars that
# are already present). Popping therefore loses the race; an empty string is already "present"
# so it survives, and database_configured() (bool(db_url and db_url.strip())) returns False ->
# all stores build InMemory. test_store_persistence.py's Postgres test is skipif
# AGENT_STUDIO_TEST_DATABASE_URL (a separate, unset var), so it stays skipped and unaffected.
os.environ["DATABASE_URL"] = ""
get_settings.cache_clear()

from agent_studio.embeddings import deterministic_embedding

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
