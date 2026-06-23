"""Channel adapters — provider-pluggable inbound/outbound for the universal webhook.

Each adapter wraps a messaging provider (Chatwoot, GoHighLevel, …) behind a common
interface so `POST /webhooks/{provider}` can verify, normalize, and send without
duplicating provider logic. Existing `chatwoot.py` stays the implementation core; the
Chatwoot adapter here is a thin wrapper, not a copy.
"""

from agent_studio.adapters.base import ChannelAdapter, NormalizedInbound, SendResult, OutboundMode
from agent_studio.adapters.registry import get_adapter, registered_providers

__all__ = [
    "ChannelAdapter",
    "NormalizedInbound",
    "SendResult",
    "OutboundMode",
    "get_adapter",
    "registered_providers",
]