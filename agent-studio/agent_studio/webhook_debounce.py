"""Webhook debouncing — coalesce a burst of inbound messages into one graph run.

Opt-in via `WEBHOOK_DEBOUNCE_ENABLED` (default false, preserving the synchronous
`ConversationRecord` behavior the existing Chatwoot tests rely on). When enabled,
`POST /webhooks/{provider}` returns `202 Accepted` immediately and a background
flush task runs `graph.ainvoke` once per `{provider}_{conversation_id}` key after
the debounce window. Each new message within the window resets the timer, so a
rapid burst becomes a single classification + draft + (optional) auto-send.

Results are observable via `GET /conversations/{id}` and `GET /diagnostics/events`,
exactly as in the synchronous path.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from agent_studio.adapters.base import NormalizedInbound

_logger = logging.getLogger(__name__)

#: Signature of the per-key flush callback. `key` is `{provider}_{conversation_id}`;
#: `messages` is the buffered burst (in arrival order). The callback runs the graph
#: once and persists the resulting conversation record.
ProcessCallback = Callable[[str, list[NormalizedInbound]], Awaitable[None]]


class DebounceCoordinator:
    def __init__(self, debounce_ms: int, process_fn: ProcessCallback) -> None:
        self._debounce_ms = max(0, int(debounce_ms))
        self._process = process_fn
        self._buffers: dict[str, list[NormalizedInbound]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def schedule(self, key: str, message: NormalizedInbound) -> None:
        """Buffer `message` under `key` and (re)arm the debounce timer."""
        async with self._lock:
            self._buffers.setdefault(key, []).append(message)
            existing = self._tasks.get(key)
            if existing is not None:
                existing.cancel()
            self._tasks[key] = asyncio.create_task(self._flush(key))

    async def _flush(self, key: str) -> None:
        try:
            await asyncio.sleep(self._debounce_ms / 1000.0)
        except asyncio.CancelledError:
            # A newer message re-armed the timer; this flush is superseded.
            return
        async with self._lock:
            messages = self._buffers.pop(key, [])
            self._tasks.pop(key, None)
        if not messages:
            return
        try:
            await self._process(key, messages)
        except Exception:  # pragma: no cover — background task must not crash the loop
            _logger.exception("debounce.process_failed key=%s", key)

    async def flush_all(self) -> None:
        """Cancel all pending timers and process buffered messages immediately (for tests/teardown)."""
        async with self._lock:
            keys = list(self._buffers.keys())
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        for key in keys:
            async with self._lock:
                messages = self._buffers.pop(key, [])
            if messages:
                await self._process(key, messages)

    @property
    def pending_keys(self) -> int:
        return len(self._buffers)