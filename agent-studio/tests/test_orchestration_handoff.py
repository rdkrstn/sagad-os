"""Supervisor/handoff orchestration tests (Phase 3).

The graph now inserts a rule-based ``supervisor`` node between the sub-agents and
``supervisor_draft``. When a sub-agent's report requests a handoff (``recommended_action ==
"HANDOFF"`` with a ``handoff_to`` agent key), the supervisor transfers control to that
sub-agent, records the path in ``delegation_chain`` and the per-agent transcript in
``agent_messages``, and bounds the total delegations by ``MAX_DELEGATIONS``.

These tests stub ``_build_chat_model`` with a handoff-aware mock LLM so no real model is called.
The default (no-handoff) flow is unchanged and still covered by ``test_graph_hierarchy.py``.
"""

from __future__ import annotations

import json
from typing import Mapping
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent_studio.graph import MAX_DELEGATIONS, graph


def _handoff_report(agent: str, target: str | None) -> str:
    if target is None:
        return json.dumps(
            {
                "agent": agent,
                "analysis": f"{agent} handled the request",
                "recommended_action": "DRAFT_REPLY",
                "tool_requests": [],
                "draft_hint": "Done.",
                "confidence": 0.9,
                "risk_flags": [],
            }
        )
    return json.dumps(
        {
            "agent": agent,
            "analysis": f"{agent} delegating",
            "recommended_action": "HANDOFF",
            "handoff_to": target,
            "tool_requests": [],
            "draft_hint": "",
            "confidence": 0.8,
            "risk_flags": [],
        }
    )


def _build_handoff_llm(
    handoff_map: Mapping[str, str | None],
    *,
    draft_text: str = "Final draft after handoff.",
) -> MagicMock:
    """Mock LLM whose sub-agent responses hand off per ``handoff_map`` (agent_key -> target|None).

    Agent keys match the ``routed_agent``/``handoff_to`` values: sales_agent, refund_resolver,
    general_support. The classifier routes everything to general_support; supervisor_draft
    returns ``draft_text``.
    """
    mock_llm = MagicMock()

    def side_effect(messages):
        sys_msg = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        user_msg = next((m.content for m in messages if isinstance(m, HumanMessage)), "")

        # Classifier: route to general_support so the first sub-agent is run_support_agent.
        if "Classifier" in sys_msg or "classifier_agent" in sys_msg:
            return AIMessage(
                content='{"intent":"general_support","risk_level":"medium","routed_agent":"general_support"}'
            )
        # Supervisor_draft (checked before sub-agents: its prompt embeds the report JSON which
        # contains agent keys like "refund_resolver"). Use the full "You are the Supervisor
        # Agent" phrase so sub-agent prompts that merely mention a supervisor don't match here.
        if "You are the Supervisor Agent" in sys_msg or "supervisor_agent" in sys_msg:
            return AIMessage(content=draft_text)
        if "Sales Agent" in sys_msg or "sales_agent" in sys_msg:
            return AIMessage(content=_handoff_report("sales_agent", handoff_map.get("sales_agent")))
        if "Refund Resolver" in sys_msg or "refund_resolver" in sys_msg:
            return AIMessage(content=_handoff_report("refund_resolver", handoff_map.get("refund_resolver")))
        if "General Support" in sys_msg or "general_support" in sys_msg:
            return AIMessage(content=_handoff_report("general_support", handoff_map.get("general_support")))
        return AIMessage(content="Default mocked LLM response.")

    mock_llm.invoke.side_effect = side_effect
    mock_llm.bind_tools.return_value = mock_llm
    return mock_llm


def _invoke(handoff_map: Mapping[str, str | None], **kwargs) -> dict:
    mock_llm = _build_handoff_llm(handoff_map, **kwargs)
    with patch("agent_studio.graph._build_chat_model", return_value=mock_llm):
        return graph.invoke({"incoming_message": "I have a complex issue"})


# ---------------------------------------------------------------------------------------
# Single handoff: support -> refund_resolver
# ---------------------------------------------------------------------------------------


def test_supervisor_delegates_support_to_refund() -> None:
    res = _invoke({"general_support": "refund_resolver"})
    # The supervisor transferred control from support to refund_resolver.
    assert res["delegation_chain"] == ["refund_resolver"]
    assert res["routed_agent"] == "refund_resolver"
    # Per-agent transcript recorded both the support and refund reports, in order.
    agents = [m["agent"] for m in res["agent_messages"]]
    assert agents == ["general_support", "refund_resolver"]
    # The run still produces a finalized draft via supervisor_draft (supervisor_draft may append
    # a "Basis: ..." citation line, so we assert the prefix).
    assert res["draft_reply"].startswith("Final draft after handoff.")
    assert res["approval_status"] == "needs_approval"


def test_handoff_clears_handoff_to_on_finalize() -> None:
    res = _invoke({"general_support": "refund_resolver"})
    # Once finalized, handoff_to is cleared (no pending transfer).
    assert res.get("handoff_to") is None


# ---------------------------------------------------------------------------------------
# Bounded delegation: a cycle support -> refund -> sales -> support must stop at the cap
# ---------------------------------------------------------------------------------------


def test_max_delegations_cap_stops_runaway_cycle() -> None:
    # Every agent hands off to the next, forming a cycle. The cap must terminate the run.
    cycle = {
        "general_support": "refund_resolver",
        "refund_resolver": "sales_agent",
        "sales_agent": "general_support",
    }
    res = _invoke(cycle, draft_text="Final draft after delegation cap.")
    # The run terminated (no infinite loop) and produced a draft.
    assert "draft_reply" in res
    assert res["draft_reply"].startswith("Final draft after delegation cap.")
    # Delegations are bounded by MAX_DELEGATIONS.
    assert len(res["delegation_chain"]) <= MAX_DELEGATIONS
    assert len(res["delegation_chain"]) == MAX_DELEGATIONS


# ---------------------------------------------------------------------------------------
# Default (no handoff) path is unchanged
# ---------------------------------------------------------------------------------------


def test_no_handoff_default_path_unchanged() -> None:
    # No agent requests a handoff -> delegation_chain stays empty, single agent transcript.
    res = _invoke({"general_support": None}, draft_text="Plain final draft.")
    assert res["delegation_chain"] == []
    assert res.get("handoff_to") is None
    assert [m["agent"] for m in res["agent_messages"]] == ["general_support"]
    assert res["draft_reply"].startswith("Plain final draft.")


# ---------------------------------------------------------------------------------------
# Unknown handoff target is ignored (finalizes instead of crashing)
# ---------------------------------------------------------------------------------------


def test_unknown_handoff_target_finalizes() -> None:
    res = _invoke({"general_support": "nonexistent_agent"}, draft_text="Fallback draft.")
    # Unknown target is not in the handoff table -> supervisor finalizes rather than crashing.
    assert res["delegation_chain"] == []
    assert res["draft_reply"].startswith("Fallback draft.")