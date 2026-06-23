"""Unit tests for the DebounceCoordinator (no FastAPI, no graph)."""

from __future__ import annotations

import asyncio

import pytest

from agent_studio.adapters.base import NormalizedInbound
from agent_studio.webhook_debounce import DebounceCoordinator


def _msg(text: str, conv: str = "c1") -> NormalizedInbound:
    return NormalizedInbound(
        provider="ghl",
        provider_conversation_id=conv,
        provider_message_id=text,
        customer_name="X",
        channel="ghl",
        message_text=text,
        event_type="InboundMessage",
        raw_payload={},
    )


@pytest.mark.asyncio
async def test_debounce_coalesces_burst_into_one_process() -> None:
    processed: list[tuple[str, list[str]]] = []

    async def proc(key: str, messages: list[NormalizedInbound]) -> None:
        processed.append((key, [m.message_text for m in messages]))

    coord = DebounceCoordinator(debounce_ms=80, process_fn=proc)
    await coord.schedule("k", _msg("a"))
    await coord.schedule("k", _msg("b"))
    await coord.schedule("k", _msg("c"))

    # Within the window nothing has flushed yet.
    assert processed == []
    await asyncio.sleep(0.18)

    assert len(processed) == 1
    key, texts = processed[0]
    assert key == "k"
    assert texts == ["a", "b", "c"]
    assert coord.pending_keys == 0


@pytest.mark.asyncio
async def test_debounce_timer_resets_on_new_message() -> None:
    processed: list[int] = []

    async def proc(key: str, messages: list[NormalizedInbound]) -> None:
        processed.append(len(messages))

    coord = DebounceCoordinator(debounce_ms=80, process_fn=proc)
    await coord.schedule("k", _msg("a"))
    await asyncio.sleep(0.05)
    await coord.schedule("k", _msg("b"))  # resets the timer
    await asyncio.sleep(0.05)  # would have fired by now if the first timer had held
    assert processed == []
    await asyncio.sleep(0.10)
    assert processed == [2]


@pytest.mark.asyncio
async def test_flush_all_processes_immediately() -> None:
    processed: list[tuple[str, int]] = []

    async def proc(key: str, messages: list[NormalizedInbound]) -> None:
        processed.append((key, len(messages)))

    coord = DebounceCoordinator(debounce_ms=10_000, process_fn=proc)
    await coord.schedule("k1", _msg("a"))
    await coord.schedule("k2", _msg("b"))
    assert coord.pending_keys == 2

    await coord.flush_all()
    assert sorted(p[0] for p in processed) == ["k1", "k2"]
    assert coord.pending_keys == 0


@pytest.mark.asyncio
async def test_separate_keys_processed_independently() -> None:
    processed: list[str] = []

    async def proc(key: str, messages: list[NormalizedInbound]) -> None:
        processed.append(key)

    coord = DebounceCoordinator(debounce_ms=60, process_fn=proc)
    await coord.schedule("k1", _msg("a"))
    await coord.schedule("k2", _msg("b", conv="c2"))
    await asyncio.sleep(0.12)
    assert sorted(processed) == ["k1", "k2"]