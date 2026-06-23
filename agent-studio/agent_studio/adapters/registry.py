"""Adapter registry — maps a provider slug to its `ChannelAdapter`.

`POST /webhooks/{provider}` dispatches here. Chatwoot keeps its dedicated
`/webhooks/chatwoot` route (and its 14 tests) untouched; the universal route serves
new providers (ghl today, others later). Adding a provider = add an adapter + register it.
"""

from __future__ import annotations

from agent_studio.adapters.base import ChannelAdapter
from agent_studio.adapters.ghl import GhlAdapter

_REGISTRY: dict[str, ChannelAdapter] = {
    "ghl": GhlAdapter(),
}


def get_adapter(provider: str) -> ChannelAdapter | None:
    return _REGISTRY.get(provider.strip().lower())


def registered_providers() -> list[str]:
    return sorted(_REGISTRY.keys())