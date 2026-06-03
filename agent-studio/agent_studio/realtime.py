from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import WebSocket


@dataclass(frozen=True)
class RealtimeClaims:
    organization_id: str
    user_id: str
    role: str
    expires_at: int


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def create_realtime_token(
    *,
    secret: str,
    organization_id: str,
    user_id: str,
    role: str,
    ttl_seconds: int = 60,
) -> str:
    payload = {
        "organization_id": organization_id,
        "user_id": user_id,
        "role": role,
        "expires_at": int(time.time()) + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64_encode(payload_bytes)}.{_b64_encode(signature)}"


def verify_realtime_token(*, secret: str, token: str) -> RealtimeClaims | None:
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64_decode(payload_part)
        signature = _b64_decode(signature_part)
    except (ValueError, TypeError):
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return None

    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None

    organization_id = payload.get("organization_id")
    user_id = payload.get("user_id")
    role = payload.get("role")
    if not all(isinstance(value, str) and value for value in [organization_id, user_id, role]):
        return None

    return RealtimeClaims(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        expires_at=expires_at,
    )


class RealtimeConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, organization_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(organization_id, set()).add(websocket)

    def disconnect(self, organization_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(organization_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(organization_id, None)

    async def broadcast(
        self,
        organization_id: str | None,
        event: dict[str, Any],
    ) -> None:
        targets: list[tuple[str, WebSocket]] = []
        if organization_id:
            targets = [(organization_id, socket) for socket in self._connections.get(organization_id, set())]
        else:
            targets = [
                (scoped_organization_id, socket)
                for scoped_organization_id, sockets in self._connections.items()
                for socket in sockets
            ]

        disconnected: list[tuple[str, WebSocket]] = []
        for scoped_organization_id, socket in targets:
            try:
                await socket.send_json(event)
            except RuntimeError:
                disconnected.append((scoped_organization_id, socket))

        for scoped_organization_id, socket in disconnected:
            self.disconnect(scoped_organization_id, socket)


realtime_manager = RealtimeConnectionManager()
