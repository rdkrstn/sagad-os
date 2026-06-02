import httpx

from agent_studio.config import Settings


class ChatwootSendResult(dict[str, str]):
    pass


async def send_approved_reply(
    *,
    settings: Settings,
    chatwoot_conversation_id: str | None,
    content: str,
) -> ChatwootSendResult:
    if not settings.chatwoot_send_enabled:
        return ChatwootSendResult(status="dry_run", detail="Chatwoot credentials are not configured.")

    if not chatwoot_conversation_id:
        return ChatwootSendResult(status="failed", detail="Missing Chatwoot conversation ID.")

    base_url = str(settings.chatwoot_base_url).rstrip("/")
    account_id = settings.chatwoot_account_id
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{chatwoot_conversation_id}/messages"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            url,
            headers={"api_access_token": str(settings.chatwoot_api_access_token)},
            json={"content": content, "message_type": "outgoing"},
        )

    if response.is_success:
        return ChatwootSendResult(status="sent", detail="Approved reply sent to Chatwoot.")

    return ChatwootSendResult(
        status="failed",
        detail=f"Chatwoot send failed with HTTP {response.status_code}.",
    )
