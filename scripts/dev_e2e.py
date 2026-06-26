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
    # Read-only CRM context: GHL is unconfigured in the credential-free e2e stack, so
    # fetch_crm_context degrades to None -- but the field must be present and inbound must
    # still succeed (proves the never-blocks/degrade path on the real HTTP surface). The
    # contact+opportunity content path is covered by tests/test_ghl_adapter.py (stubbed httpx).
    _record("crm_context" in ghl_body, "ghl crm_context field present (degrades to None unconfigured)",
            str(ghl_body.get("crm_context")))

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
    # Use an already-normalized id (save_agent maps [^a-z0-9_] -> _), so the id
    # we POST is exactly the id that ends up in GET /agents and in DELETE path.
    agent_id = f"e2e_test_{uuid.uuid4().hex[:6]}"
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
    # /knowledge/search-test is a POST taking a KnowledgeSearchTestRequest body
    # (query, intent, risk_level, limit) and returning {"hits": [...]}.
    search = client.post("/knowledge/search-test", json={
        "query": "tune-up pricing",
        "intent": "pricing_lead",
        "risk_level": "low",
        "limit": 5,
    })
    if search.status_code == 200:
        hits = search.json().get("hits", [])
        _record(isinstance(hits, list), "knowledge/search-test returns hits list", str(search.status_code))
    else:
        _record(False, "knowledge/search-test 200", str(search.status_code))

    # 8. RevOps ticket queue + PATCH -----------------------------------------
    # Exercises the new ticket fields end-to-end on real Postgres: PATCH the GHL conversation
    # created in step 3, then verify the assignment persists and the queue filters work.
    if ghl_conv_id:
        _record(
            ghl_body.get("ticket_status") == "open",
            "ghl conversation defaults to open ticket",
            str(ghl_body.get("ticket_status")),
        )
        patch = client.patch(f"/conversations/{ghl_conv_id}/ticket", json={
            "assignee": "e2e-supervisor",
            "priority": "high",
            "ticket_status": "in_progress",
            "pipeline_stage": "triage",
        })
        _record(patch.status_code == 200, "PATCH /conversations/{id}/ticket 200", str(patch.status_code))
        if patch.status_code == 200:
            p = patch.json()
            _record(p.get("assignee") == "e2e-supervisor", "PATCH set assignee", str(p.get("assignee")))
            _record(p.get("ticket_status") == "in_progress", "PATCH set ticket_status", str(p.get("ticket_status")))
            _record(p.get("priority") == "high", "PATCH set priority", str(p.get("priority")))
        # Queue filters hit the new SQL WHERE clauses.
        in_progress = client.get("/conversations?ticket_status=in_progress").json().get("conversations", [])
        _record(
            any(c.get("id") == ghl_conv_id for c in in_progress),
            "queue filter ticket_status=in_progress includes conversation",
            str([c.get("id") for c in in_progress]),
        )
        by_assignee = client.get("/conversations?assignee=e2e-supervisor").json().get("conversations", [])
        _record(
            any(c.get("id") == ghl_conv_id for c in by_assignee),
            "queue filter assignee includes conversation",
            str([c.get("id") for c in by_assignee]),
        )
        # Persisted on a fresh GET (not just the PATCH response).
        fresh = client.get(f"/conversations/{ghl_conv_id}").json()
        _record(fresh.get("assignee") == "e2e-supervisor", "GET conversation after PATCH keeps assignee",
                str(fresh.get("assignee")))

    # 9. RevOps tiered auto-send (safe lane) ----------------------------------
    # The stack is booted with REVOPS_AUTOSEND_INTENTS=pricing_lead + a permissive confidence
    # threshold (see dev-e2e.sh). The pricing fixture classifies deterministically to
    # intent=pricing_lead, risk=low in dry_run, so the safe lane promotes needs_review -> "pass"
    # and the reply auto-sends (dry_run) without a supervisor round-trip. This proves the
    # dormant-dead-code fix works end-to-end on real Postgres + the real graph.
    tiered = client.post("/webhooks/ghl", json=_ghl_fixture(conv_id="e2e-conv-tiered", msg_id="e2e-msg-tiered"))
    _record(tiered.status_code == 200, "tiered ghl webhook 200", str(tiered.status_code))
    if tiered.status_code == 200:
        t = tiered.json()
        _record(t.get("intent") == "pricing_lead", "tiered intent=pricing_lead", str(t.get("intent")))
        _record(t.get("risk_level") == "low", "tiered risk_level=low", str(t.get("risk_level")))
        _record(t.get("compliance_status") == "pass", "tiered promoted compliance_status=pass",
                str(t.get("compliance_status")))
        _record(t.get("approval_status") == "sent", "tiered auto-send approval_status=sent",
                str(t.get("approval_status")))
        _record(t.get("send_status") == "dry_run", "tiered auto-send send_status=dry_run",
                str(t.get("send_status")))
        t_msgs = t.get("messages", [])
        _record(len(t_msgs) == 2, "tiered produced customer + ai_agent messages", str(len(t_msgs)))
        if len(t_msgs) == 2:
            _record(t_msgs[1].get("sender_type") == "ai_agent", "tiered auto-send message is ai_agent",
                    str(t_msgs[1].get("sender_type")))

    # 10. GHL manual approve-send (provider dispatch) -------------------------
    # A high-risk refund message queues at needs_approval (the safe lane only promotes
    # risk=low), so it is eligible for a supervisor approve-send. The approve-send endpoint
    # dispatches a GHL-sourced record (provider_conversation_id set, no Chatwoot context)
    # through GhlAdapter.send_outbound. GHL is unconfigured in this credential-free stack, so
    # the send is an honest dry_run -- proving the dispatch + policy + audit path end-to-end.
    refund = client.post("/webhooks/ghl", json={
        "type": "InboundMessage",
        "conversationId": "e2e-conv-approve",
        "locationId": "loc-e2e",
        "message": {"id": "e2e-msg-approve", "body": "I want to cancel my membership and get a full refund.",
                    "direction": "inbound", "type": "SMS"},
        "contact": {"id": "cont-approve", "name": "E2E Refund Customer"},
    })
    _record(refund.status_code == 200, "refund ghl webhook 200", str(refund.status_code))
    if refund.status_code == 200:
        r = refund.json()
        refund_id = r.get("id")
        _record(r.get("approval_status") == "needs_approval", "refund conversation queued for approval",
                str(r.get("approval_status")))
        _record(r.get("provider_conversation_id") == "e2e-conv-approve", "refund provider_conversation_id set",
                str(r.get("provider_conversation_id")))
        approve = client.post(f"/conversations/{refund_id}/approve-send", json={
            "approved": True,
            "supervisor_id": "e2e-supervisor",
        })
        _record(approve.status_code == 200, "GHL approve-send 200", str(approve.status_code))
        if approve.status_code == 200:
            a = approve.json()
            _record(a.get("approval_status") == "sent", "GHL approve-send approval_status=sent",
                    str(a.get("approval_status")))
            _record(a.get("send_status") == "dry_run", "GHL approve-send send_status=dry_run",
                    str(a.get("send_status")))
            a_ai = [m for m in a.get("messages", []) if m.get("sender_type") == "ai_agent"]
            _record(bool(a_ai) and a_ai[-1].get("provider") == "ghl", "GHL approve-send appended ai_agent ghl msg",
                    str([m.get("provider") for m in a.get("messages", [])]))

    # 11. GHL poller-enabled boot stays healthy --------------------------------
    # The stack is booted with GHL_POLL_ENABLED=true (see dev-e2e.sh). GHL is unconfigured in this
    # credential-free stack, so the poller's per-cycle no-creds skip keeps it a no-op (the real
    # poller roundtrip is pytest-covered with stubbed httpx in tests/test_ghl_poller.py). This
    # check proves the lifespan poller wiring never destabilizes the container: after all the
    # above work (with the poller looping in the background), the app is still live + ready.
    live2 = client.get("/health/live")
    _record(live2.status_code == 200, "poller-enabled boot: health/live still 200", str(live2.status_code))
    ready2 = client.get("/health/ready")
    _record(ready2.status_code == 200, "poller-enabled boot: health/ready still 200", str(ready2.status_code))
    if ready2.status_code == 200:
        _record(ready2.json().get("database_ready") is True, "poller-enabled boot: database_ready still true",
                str(ready2.json().get("database_ready")))

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