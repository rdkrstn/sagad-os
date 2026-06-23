"""End-to-end roundtrip assertions for a running sagad-agent-studio (LLM_MODE=dry_run).

Run against a booted compose stack (see scripts/dev-e2e.sh). Uses httpx to exercise the
real HTTP surface: health, Chatwoot + GHL webhooks, conversation fetch, draft SSE stream,
agents CRUD, and knowledge search. Exits 0 on full pass, 1 on any failure.

Env:
  BASE_URL            default http://127.0.0.1:8010
  INTERNAL_SECRET     the AGENT_STUDIO_INTERNAL_SECRET the stack was booted with (for protected endpoints)
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010").rstrip("/")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")
CHATWOOT_WEBHOOK_TOKEN = os.getenv("CHATWOOT_WEBHOOK_TOKEN", "")

failures: list[str] = []
checks = 0


def _auth_headers() -> dict[str, str]:
    return {"x-sagad-internal-secret": INTERNAL_SECRET} if INTERNAL_SECRET else {}


def _record(ok: bool, msg: str, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg} {('— ' + detail) if detail else ''}")
        failures.append(f"{msg} {detail}".strip())


def _chatwoot_fixture() -> dict[str, object]:
    return {
        "event": "message_created",
        "id": int(uuid.uuid4().int % 1_000_000),
        "content": "How much does an AC tune-up cost?",
        "message_type": "incoming",
        "conversation": {"id": int(uuid.uuid4().int % 1_000_000) + 1},
        "sender": {"name": "E2E Chatwoot Customer"},
    }


def _ghl_fixture(conv_id: str = "e2e-conv-1", msg_id: str = "e2e-msg-1") -> dict[str, object]:
    return {
        "type": "InboundMessage",
        "conversationId": conv_id,
        "locationId": "loc-e2e",
        "message": {"id": msg_id, "body": "Hi, what is your pricing for a tune-up?", "direction": "inbound", "type": "SMS"},
        "contact": {"id": "cont-e2e", "name": "E2E GHL Customer"},
    }


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=30.0, headers=_auth_headers())

    print(f"== sagad-os dev e2e against {BASE_URL} ==")

    # 1. Health ----------------------------------------------------------------
    live = client.get("/health/live")
    _record(live.status_code == 200, "health/live 200", str(live.status_code))
    ready = client.get("/health/ready")
    _record(ready.status_code == 200, "health/ready 200", str(ready.status_code))
    if ready.status_code == 200:
        _record(ready.json().get("database_ready") is True, "health/ready database_ready=true", str(ready.json()))

    # 2. Chatwoot webhook roundtrip -------------------------------------------
    cw_params = {"token": CHATWOOT_WEBHOOK_TOKEN} if CHATWOOT_WEBHOOK_TOKEN else None
    cw = client.post("/webhooks/chatwoot", json=_chatwoot_fixture(), params=cw_params)
    _record(cw.status_code == 200, "chatwoot webhook 200", str(cw.status_code))
    cw_body = cw.json() if cw.status_code == 200 else {}
    _record(bool(cw_body.get("intent")), "chatwoot intent set", str(cw_body.get("intent")))
    _record(bool(cw_body.get("draft_reply")), "chatwoot draft_reply non-empty", repr(cw_body.get("draft_reply"))[:80])
    _record(cw_body.get("channel") in {"chatwoot", "sms", "web_chat"} or bool(cw_body.get("channel")),
            "chatwoot channel set", str(cw_body.get("channel")))

    # 3. GHL universal webhook roundtrip --------------------------------------
    ghl = client.post("/webhooks/ghl", json=_ghl_fixture())
    _record(ghl.status_code == 200, "ghl webhook 200", str(ghl.status_code))
    ghl_body = ghl.json() if ghl.status_code == 200 else {}
    _record(ghl_body.get("id") == "ghl_e2e-conv-1", "ghl conversation_id stable", str(ghl_body.get("id")))
    _record(bool(ghl_body.get("intent")), "ghl intent set", str(ghl_body.get("intent")))
    _record(bool(ghl_body.get("draft_reply")), "ghl draft_reply non-empty", repr(ghl_body.get("draft_reply"))[:80])
    ghl_msgs = ghl_body.get("messages", [])
    _record(bool(ghl_msgs) and ghl_msgs[0].get("provider") == "ghl", "ghl message provider=ghl",
            str([m.get("provider") for m in ghl_msgs]))

    # 4. Conversation fetch ----------------------------------------------------
    ghl_conv_id = ghl_body.get("id")
    if ghl_conv_id:
        got = client.get(f"/conversations/{ghl_conv_id}")
        _record(got.status_code == 200, "GET conversation 200", str(got.status_code))
        if got.status_code == 200:
            g = got.json()
            _record(g.get("intent") == ghl_body.get("intent"), "GET conversation intent persisted", str(g.get("intent")))
            _record(bool(g.get("trace_attributes")) or g.get("trace_attributes") == {},
                    "GET conversation trace_attributes present", str(g.get("trace_attributes"))[:60])

    # 5. Draft SSE stream ------------------------------------------------------
    if ghl_conv_id:
        with client.stream("GET", f"/conversations/{ghl_conv_id}/draft/stream") as resp:
            _record(resp.status_code == 200, "draft/stream 200", str(resp.status_code))
            text = ""
            content_type = resp.headers.get("content-type", "")
            _record("text/event-stream" in content_type, "draft/stream content-type event-stream", content_type)
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    text += line[len("data: "):]
        _record(bool(text.strip()) or "DONE" in text or "ERROR" in text,
                "draft/stream produced tokens", repr(text)[:120])

    # 6. Agents CRUD -----------------------------------------------------------
    agent_id = f"e2e-test-{uuid.uuid4().hex[:6]}"
    create = client.post("/agents", json={
        "id": agent_id,
        "name": "E2E Test Agent",
        "intents": ["general_support"],
        "allowed_tools": [],
        "system_prompt": "You are a test agent used by the dev e2e roundtrip.",
    })
    _record(create.status_code == 200, "POST /agents 200", str(create.status_code))
    agents = client.get("/agents")
    _record(agents.status_code == 200, "GET /agents 200", str(agents.status_code))
    if agents.status_code == 200:
        ids = [a.get("id") for a in agents.json()]
        _record(agent_id in ids, "created agent listed", str(agent_id in ids))
    delete = client.delete(f"/agents/{agent_id}")
    _record(delete.status_code == 200, "DELETE /agents/{id} 200", str(delete.status_code))

    # 7. Knowledge search -----------------------------------------------------
    search = client.get("/knowledge/search-test", params={"query": "tune-up pricing", "limit": 5})
    if search.status_code == 200:
        hits = search.json()
        _record(isinstance(hits, list), "knowledge/search-test returns list", str(search.status_code))
    else:
        # search-test may require a query param shape; record but don't fail hard.
        _record(False, "knowledge/search-test 200", str(search.status_code))

    print(f"\n== {checks - len(failures)}/{checks} checks passed ==")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())