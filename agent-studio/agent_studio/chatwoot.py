from typing import Literal, NotRequired, TypedDict

import httpx

from agent_studio.config import Settings


class ChatwootSendResult(TypedDict):
    status: Literal["sent", "dry_run", "failed"]
    detail: str
    provider: str
    action: str
    target_url: NotRequired[str]
    http_status: NotRequired[int]
    response_excerpt: NotRequired[str]
    error_type: NotRequired[str]
    external_id: NotRequired[str]


def _response_excerpt(response: httpx.Response, limit: int = 500) -> str:
    text = response.text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


async def send_approved_reply(
    *,
    settings: Settings,
    chatwoot_conversation_id: str | None,
    content: str,
) -> ChatwootSendResult:
    if not settings.chatwoot_configured:
        return ChatwootSendResult(
            status="dry_run",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            detail="Chatwoot credentials are not fully configured; approved send stayed in dry-run.",
        )

    if not chatwoot_conversation_id:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            detail="Missing Chatwoot conversation ID.",
        )

    base_url = str(settings.chatwoot_base_url).rstrip("/")
    account_id = settings.chatwoot_account_id
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{chatwoot_conversation_id}/messages"

    if settings.chatwoot_dry_run:
        return ChatwootSendResult(
            status="dry_run",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            detail="Chatwoot credentials are configured, but dry-run is enabled.",
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers={"api_access_token": str(settings.chatwoot_api_access_token)},
                json={"content": content, "message_type": "outgoing"},
            )
    except httpx.TimeoutException as exc:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            error_type=exc.__class__.__name__,
            detail="Chatwoot send timed out before a response was received.",
        )
    except httpx.RequestError as exc:
        return ChatwootSendResult(
            status="failed",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            error_type=exc.__class__.__name__,
            detail=f"Chatwoot send failed before receiving an HTTP response: {exc.__class__.__name__}.",
        )

    if response.is_success:
        external_id: str | None = None
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            id_value = body.get("id")
            external_id = str(id_value) if id_value is not None else None
        result = ChatwootSendResult(
            status="sent",
            provider="Chatwoot",
            action="chatwoot.messages.send_approved",
            target_url=url,
            http_status=response.status_code,
            detail="Approved reply sent to Chatwoot.",
        )
        if external_id:
            result["external_id"] = external_id
        return result

    return ChatwootSendResult(
        status="failed",
        provider="Chatwoot",
        action="chatwoot.messages.send_approved",
        target_url=url,
        http_status=response.status_code,
        response_excerpt=_response_excerpt(response),
        detail=f"Chatwoot send failed with HTTP {response.status_code}.",
    )
