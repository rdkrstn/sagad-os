"""Common types + base class for channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, TypedDict


# How an adapter may deliver an outbound reply. Per-adapter config selects one.
OutboundMode = str  # "webhook" | "mcp"


class SendResult(TypedDict, total=False):
    """Result of an outbound send. Mirrors the shape of `ChatwootSendResult`."""

    status: str  # "sent" | "dry_run" | "failed" | "blocked"
    provider: str
    action: str
    target_url: str
    http_status: int
    external_id: str
    response_excerpt: str
    error_type: str
    detail: str


@dataclass
class NormalizedInbound:
    """Canonical inbound message produced by an adapter's `normalize()`.

    The universal webhook handler builds the graph `initial_state` from this shape
    plus `conversation_history` (loaded from the store) and `memory_context`.
    """

    provider: str
    provider_conversation_id: str | None
    provider_message_id: str | None
    customer_name: str
    channel: str
    message_text: str
    event_type: str | None
    raw_payload: dict[str, object]
    # Provider-specific context carried through to the conversation record
    # (e.g. Chatwoot's `chatwoot_context`, GHL's `location_id`).
    extra: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(ABC):
    """A messaging provider behind the universal webhook.

    Adapters are stateless w.r.t. request state; they receive the raw body/headers
    for verification and the parsed payload for normalization. Credentials come
    from `Settings` (env-driven), not the adapter, so one adapter instance serves
    all requests.
    """

    #: lowercase provider slug — matches `IntegrationProvider` + the URL path
    name: str
    #: outbound delivery modes this adapter supports
    outbound_modes: list[str]

    @abstractmethod
    def verify_inbound(self, raw_body: bytes, headers: Mapping[str, str]) -> None:
        """Verify the inbound request signature/token. Raise HTTPException(401) on failure."""

    @abstractmethod
    def normalize(self, raw_payload: dict[str, object]) -> NormalizedInbound:
        """Parse + normalize a provider payload into `NormalizedInbound`."""

    def ignores(self, normalized: NormalizedInbound) -> bool:
        """Return True for events that are not inbound customer messages (outgoing/private/etc.)."""
        return False

    @abstractmethod
    async def send_outbound(
        self,
        reply: str,
        normalized: NormalizedInbound,
        settings: Any,
    ) -> SendResult:
        """Deliver an approved/auto reply back through the provider."""