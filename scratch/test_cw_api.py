import os
import asyncio
import httpx
from agent_studio.config import get_settings

async def main():
    settings = get_settings()
    print("Base URL:", settings.chatwoot_base_url)
    print("Account ID:", settings.chatwoot_account_id)
    print("Token length:", len(settings.chatwoot_api_access_token) if settings.chatwoot_api_access_token else 0)
    print("Webhook Token:", settings.chatwoot_webhook_token)
    
    if not settings.chatwoot_configured:
        print("Chatwoot is not configured!")
        return
        
    base_url = str(settings.chatwoot_base_url).rstrip("/")
    url = f"{base_url}/api/v1/accounts/{settings.chatwoot_account_id}/conversations"
    headers = {"api_access_token": str(settings.chatwoot_api_access_token)}
    
    print("Querying url:", url)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            print("Status:", response.status_code)
            if response.status_code == 200:
                data = response.json()
                print("Conversations count:", len(data.get("payload", [])))
                if data.get("payload"):
                    first = data["payload"][0]
                    print("First Conversation ID:", first.get("id"))
                    print("First Conversation status:", first.get("status"))
                    print("First Conversation inbox:", first.get("inbox_id"))
            else:
                print("Response:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
