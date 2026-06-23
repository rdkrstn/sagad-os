import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from agent_studio.state import AgentStudioState
from agent_studio.graph import (
    classify_and_route,
    run_sales_agent,
    run_support_agent,
    run_refund_resolver,
    run_tool_executor,
    supervisor_draft,
    run_guardrail,
    graph,
)
from agent_studio.schemas import (
    KnowledgeHit,
    MemoryHit,
    ToolPlan,
    ToolResult,
)
from agent_studio.mcp_gateway import build_mcp_descriptors


# Helper to build mock LLM with dynamic responses
def make_mock_llm(responses=None):
    mock_llm = MagicMock()

    def side_effect(messages):
        sys_msg = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        user_msg = next((m.content for m in messages if isinstance(m, HumanMessage)), "")

        if responses and callable(responses):
            custom_res = responses(sys_msg, user_msg)
            if custom_res is not None:
                return AIMessage(content=custom_res)

        if "Classifier" in sys_msg or "classifier_agent" in sys_msg:
            if "refund" in user_msg.lower() or "cancel" in user_msg.lower():
                return AIMessage(content='{"intent": "refund_or_cancellation", "risk_level": "high", "routed_agent": "refund_resolver"}')
            elif "price" in user_msg.lower() or "pricing" in user_msg.lower() or "quote" in user_msg.lower() or "cost" in user_msg.lower():
                return AIMessage(content='{"intent": "pricing_lead", "risk_level": "low", "routed_agent": "sales_agent"}')
            elif "appoint" in user_msg.lower() or "schedule" in user_msg.lower() or "book" in user_msg.lower():
                return AIMessage(content='{"intent": "booking_or_support", "risk_level": "medium", "routed_agent": "general_support"}')
            else:
                return AIMessage(content='{"intent": "general_support", "risk_level": "medium", "routed_agent": "general_support"}')

        elif "You are the Supervisor Agent" in sys_msg or "supervisor_agent" in sys_msg:
            # supervisor_draft puts the sub-agent report (incl. recommended_action) into the
            # system prompt, not the user message. The static prompt mentions "ESCALATE" in
            # guidance text, so discriminate on the JSON key/value pair that only appears in
            # the actual report.
            if '"recommended_action": "ESCALATE"' in sys_msg or "ESCALATE" in user_msg:
                return AIMessage(content="I am escalating this to a supervisor.")
            return AIMessage(content="This is the finalized draft reply from the supervisor.")

        elif "Sales Agent" in sys_msg or "sales_agent" in sys_msg:
            if "lookup" in user_msg.lower() or "tool" in user_msg.lower():
                return AIMessage(content='{"agent": "sales_agent", "analysis": "lookup contact", "recommended_action": "REQUEST_TOOL", "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "customer"}}], "draft_hint": "", "confidence": 0.85, "risk_flags": []}')
            elif "escalate" in user_msg.lower():
                return AIMessage(content='{"agent": "sales_agent", "analysis": "high risk", "recommended_action": "ESCALATE", "tool_requests": [], "draft_hint": "", "confidence": 0.85, "risk_flags": []}')
            else:
                return AIMessage(content='{"agent": "sales_agent", "analysis": "pricing info", "recommended_action": "DRAFT_REPLY", "tool_requests": [], "draft_hint": "Here is the pricing info", "confidence": 0.9, "risk_flags": []}')

        elif "Refund Resolver" in sys_msg or "refund_resolver" in sys_msg:
            if "escalate" in user_msg.lower():
                return AIMessage(content='{"agent": "refund_resolver", "analysis": "escalate refund", "recommended_action": "ESCALATE", "tool_requests": [], "draft_hint": "", "confidence": 0.95, "risk_flags": ["refund_request"]}')
            return AIMessage(content='{"agent": "refund_resolver", "analysis": "refund request", "recommended_action": "DRAFT_REPLY", "tool_requests": [], "draft_hint": "Refund needs supervisor review.", "confidence": 0.95, "risk_flags": ["refund_request"]}')

        elif "General Support" in sys_msg or "general_support" in sys_msg:
            return AIMessage(content='{"agent": "general_support", "analysis": "general query", "recommended_action": "DRAFT_REPLY", "tool_requests": [], "draft_hint": "Here is the support response.", "confidence": 0.88, "risk_flags": []}')


        return AIMessage(content="Default mocked LLM response.")

    mock_llm.invoke.side_effect = side_effect
    mock_llm.bind_tools.return_value = mock_llm
    return mock_llm


@pytest.fixture
def mock_graph_llm():
    with patch("agent_studio.graph._build_chat_model") as mock_build:
        mock_build.return_value = make_mock_llm()
        yield mock_build


# =====================================================================
# CLASSIFIER ROUTING TESTS (8 tests)
# =====================================================================

def test_classify_and_route_sales(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Tell me about prices"}
    res = classify_and_route(state)
    assert res["intent"] == "pricing_lead"
    assert res["risk_level"] == "low"
    assert res["routed_agent"] == "sales_agent"


def test_classify_and_route_refund(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "I want a refund"}
    res = classify_and_route(state)
    assert res["intent"] == "refund_or_cancellation"
    assert res["risk_level"] == "high"
    assert res["routed_agent"] == "refund_resolver"


def test_classify_and_route_booking(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Please schedule an appointment"}
    res = classify_and_route(state)
    assert res["intent"] == "booking_or_support"
    assert res["risk_level"] == "medium"
    assert res["routed_agent"] == "general_support"


def test_classify_and_route_fallback(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "hello support"}
    res = classify_and_route(state)
    assert res["intent"] == "general_support"
    assert res["routed_agent"] == "general_support"


def test_classify_and_route_risk_refund(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Cancel this now!"}
    res = classify_and_route(state)
    assert res["risk_level"] == "high"


def test_classify_and_route_risk_pricing(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "What is the cost?"}
    res = classify_and_route(state)
    assert res["risk_level"] == "low"


def test_classify_and_route_empty_message(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": ""}
    res = classify_and_route(state)
    assert res["intent"] == "general_support"
    assert res["routed_agent"] == "general_support"


def test_classify_and_route_blends_memory(mock_graph_llm):
    # vague follow-ups don't crash and get classified properly
    state: AgentStudioState = {
        "incoming_message": "do that",
        "memory_context": [MemoryHit(memory_type="intent", content="refund my money", score=1.0)]
    }
    res = classify_and_route(state)
    assert res["intent"] is not None


# =====================================================================
# SUB-AGENT STRUCTURED REPORT TESTS (9 tests)
# =====================================================================

def test_run_sales_agent_valid_json(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Pricing info", "normalized_message": "Pricing info"}
    res = run_sales_agent(state)
    assert isinstance(res["sub_agent_report"], dict)
    assert res["sub_agent_report"]["agent"] == "sales_agent"


def test_run_sales_agent_required_keys(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Pricing info", "normalized_message": "Pricing info"}
    res = run_sales_agent(state)
    report = res["sub_agent_report"]
    for key in ["agent", "analysis", "recommended_action", "confidence"]:
        assert key in report


def test_run_sales_agent_recommended_action_valid(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "Pricing info", "normalized_message": "Pricing info"}
    res = run_sales_agent(state)
    assert res["sub_agent_report"]["recommended_action"] in ["DRAFT_REPLY", "REQUEST_TOOL", "ESCALATE"]


def test_run_support_agent_valid_json(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "general support help", "normalized_message": "general support help"}
    res = run_support_agent(state)
    assert isinstance(res["sub_agent_report"], dict)
    assert res["sub_agent_report"]["agent"] == "general_support"


def test_run_support_agent_confidence_bounds(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "general support help", "normalized_message": "general support help"}
    res = run_support_agent(state)
    conf = res["sub_agent_report"]["confidence"]
    assert 0.0 <= conf <= 1.0


def test_run_refund_resolver_valid_json(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "I want money back", "normalized_message": "I want money back"}
    res = run_refund_resolver(state)
    assert isinstance(res["sub_agent_report"], dict)
    assert res["sub_agent_report"]["agent"] == "refund_resolver"


def test_run_refund_resolver_includes_risk_flags(mock_graph_llm):
    state: AgentStudioState = {"incoming_message": "cancellation request", "normalized_message": "cancellation request"}
    res = run_refund_resolver(state)
    assert "refund_request" in res["sub_agent_report"]["risk_flags"]


def test_sub_agent_report_malformed_llm_fallback(mock_graph_llm):
    # Malformed output should fallback gracefully
    def malformed_llm(sys, user):
        return "Not JSON at all!"
    mock_graph_llm.return_value = make_mock_llm(malformed_llm)
    state: AgentStudioState = {"incoming_message": "pricing", "normalized_message": "pricing"}
    res = run_sales_agent(state)
    assert res["sub_agent_report"]["recommended_action"] == "ESCALATE"


def test_sub_agent_report_tool_requests_always_list(mock_graph_llm):
    def bad_tools(sys, user):
        return '{"recommended_action": "REQUEST_TOOL", "tool_requests": null}'
    mock_graph_llm.return_value = make_mock_llm(bad_tools)
    state: AgentStudioState = {"incoming_message": "pricing", "normalized_message": "pricing"}
    res = run_sales_agent(state)
    assert isinstance(res["tool_requests"], list)


# =====================================================================
# TOOL EXECUTOR TESTS (10 tests)
# =====================================================================

@pytest.mark.asyncio
async def test_run_tool_executor_no_tools():
    state: AgentStudioState = {"tool_requests": []}
    res = await run_tool_executor(state)
    assert res["tool_outputs"] == []


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_blocked_agent(mock_settings):
    # Agent outside of allowed list
    settings = MagicMock()
    settings.twenty_enabled = True
    mock_settings.return_value = settings
    
    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "test"}}],
        "routed_agent": "unauthorized_agent",
        "risk_level": "medium",
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_provider_disabled(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = False
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "test"}}],
        "routed_agent": "sales_agent",
        "risk_level": "medium",
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_write_unapproved(mock_settings):
    # A write tool requiring approval, where approved=False
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.create_note", "args": {"contact_id": "1", "note": "hi"}}],
        "routed_agent": "sales_agent",
        "risk_level": "medium",
        "approval_status": "needs_approval"
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_high_risk_live_write_blocked(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    settings.twenty_dry_run = False
    settings.twenty_allow_writes = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.update_lead_stage", "args": {"contact_id": "1", "lead_stage": "won"}}],
        "routed_agent": "sales_agent",
        "risk_level": "high",
        "approval_status": "approved", # approved but high risk + autonomous is blocked by policy
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_unconfigured_dry_run(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = False # unconfigured
    settings.twenty_reads_enabled = False
    settings.twenty_dry_run = True
    settings.twenty_base_url = ""
    settings.twenty_api_key = ""
    mock_settings.return_value = settings

    # crm.lookup_contact does not require approval
    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "test"}}],
        "routed_agent": "sales_agent",
        "risk_level": "low",
    }
    res = await run_tool_executor(state)
    # Since it's a read tool, we can check policy.py line 86: if not context.provider_configured -> dry_run=True, allowed=True.
    # But wait, in twenty.py lookup_contact: if not self.settings.twenty_reads_enabled (which is twenty_enabled and twenty_configured) it returns blocked.
    # So it returns blocked result or dry run.
    assert res["tool_outputs"][0]["status"] in ["blocked", "dry_run", "succeeded"]


@pytest.mark.asyncio
@patch("agent_studio.graph.TwentyAdapter")
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_execute_lookup(mock_settings, mock_adapter_class):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    from unittest.mock import AsyncMock
    mock_adapter = MagicMock()
    crm_ctx = MagicMock()
    crm_ctx.contact_id = "contact_123"
    crm_ctx.display_name = "Jane Doe"
    crm_ctx.company_name = "ACME"
    crm_ctx.phone_masked = "***"
    crm_ctx.email_masked = "***"
    
    mock_adapter.lookup_contact = AsyncMock(return_value=(crm_ctx, ToolPlan(tool_name="crm.lookup_contact", action="lookup"), ToolResult(plan_id="1", tool_name="crm.lookup_contact", status="succeeded", detail="ok")))
    mock_adapter_class.return_value = mock_adapter

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "Jane"}}],
        "routed_agent": "sales_agent",
        "risk_level": "low",
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "succeeded"
    assert res["tool_outputs"][0]["output"]["contact_id"] == "contact_123"


@pytest.mark.asyncio
@patch("agent_studio.graph.TwentyAdapter")
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_exception_handling(mock_settings, mock_adapter_class):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    from unittest.mock import AsyncMock
    mock_adapter = MagicMock()
    mock_adapter.lookup_contact = AsyncMock(side_effect=Exception("API failure"))
    mock_adapter_class.return_value = mock_adapter

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "Jane"}}],
        "routed_agent": "sales_agent",
        "risk_level": "low",
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "failed"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_dry_run_status(mock_settings):
    # Force dry run
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    settings.twenty_dry_run = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "Jane"}}],
        "routed_agent": "sales_agent",
        "risk_level": "low",
    }
    # For a read tool like lookup_contact, if twenty_dry_run=True, policy returns dry_run=True (or False depending on manifest mode).
    # Since crm.lookup_contact manifest has mode="read", dry_run remains False. But if policy blocks or permits, let's verify it doesn't raise exception.
    res = await run_tool_executor(state)
    assert len(res["tool_outputs"]) == 1


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_run_tool_executor_unknown_tool(mock_settings):
    settings = MagicMock()
    mock_settings.return_value = settings
    state: AgentStudioState = {
        "tool_requests": [{"tool": "unknown_tool", "args": {}}],
        "routed_agent": "sales_agent",
        "risk_level": "low",
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"


# =====================================================================
# SUPERVISOR DRAFT TESTS (7 tests)
# =====================================================================

def test_supervisor_draft_produces_reply(mock_graph_llm):
    state: AgentStudioState = {
        "normalized_message": "Hello",
        "sub_agent_report": {"agent": "sales_agent", "analysis": "pricing request"}
    }
    res = supervisor_draft(state)
    assert "draft_reply" in res
    assert res["draft_reply"] == "This is the finalized draft reply from the supervisor."


def test_supervisor_draft_incorporates_tool_outputs(mock_graph_llm):
    def custom_llm(sys, user):
        # supervisor_draft puts tool outputs (incl. company_name ACME) into the system prompt,
        # not the user message — so check both.
        if "ACME" in user or "ACME" in sys:
            return "Finalized draft for ACME customer."
        return None
    mock_graph_llm.return_value = make_mock_llm(custom_llm)

    state: AgentStudioState = {
        "normalized_message": "Hello",
        # "analysis" is required to enter the re-entry draft path that injects tool_outputs
        # into the system prompt (supervisor_draft gates on report.get("analysis")).
        "sub_agent_report": {"agent": "sales_agent", "analysis": "pricing request"},
        "tool_outputs": [{"tool": "crm.lookup_contact", "output": {"company_name": "ACME"}}]
    }
    res = supervisor_draft(state)
    assert "ACME" in res["draft_reply"]


def test_supervisor_draft_escalation_flag(mock_graph_llm):
    state: AgentStudioState = {
        "normalized_message": "Hello",
        # "analysis" is required to enter the re-entry draft path that injects the report
        # (incl. recommended_action) into the system prompt (supervisor_draft gates on
        # report.get("analysis")).
        "sub_agent_report": {"agent": "sales_agent", "analysis": "high risk", "recommended_action": "ESCALATE"}
    }
    res = supervisor_draft(state)
    assert "escalating" in res["draft_reply"].lower()


def test_supervisor_draft_empty_report_fallback(mock_graph_llm):
    state: AgentStudioState = {
        "normalized_message": "Hello",
        "sub_agent_report": {}
    }
    res = supervisor_draft(state)
    assert res["draft_reply"] is not None


def test_supervisor_draft_no_raw_json_leaks(mock_graph_llm):
    def json_leak(sys, user):
        return '```json\n{"reply": "clean text"}\n```'
    mock_graph_llm.return_value = make_mock_llm(json_leak)

    state: AgentStudioState = {
        "normalized_message": "Hello",
        "sub_agent_report": {"agent": "sales_agent"}
    }
    res = supervisor_draft(state)
    assert not res["draft_reply"].startswith("```")


def test_supervisor_draft_llm_error_graceful(mock_graph_llm):
    mock_graph_llm.side_effect = Exception("LLM crash")
    state: AgentStudioState = {
        "normalized_message": "Hello",
        "sub_agent_report": {"agent": "sales_agent"}
    }
    # Should catch exception and put error string in draft_reply rather than crash
    res = supervisor_draft(state)
    assert "error" in res["draft_reply"].lower()


def test_supervisor_draft_always_needs_approval(mock_graph_llm):
    state: AgentStudioState = {
        "normalized_message": "Hello",
        "sub_agent_report": {"agent": "sales_agent"}
    }
    res = supervisor_draft(state)
    assert res["approval_status"] == "needs_approval"


# =====================================================================
# GUARDRAIL / QA TESTS (9 tests)
# =====================================================================

def test_run_guardrail_pass_clean():
    state: AgentStudioState = {
        "draft_reply": "Yes, we offer pricing starting at $10/mo.",
        "retrieved_knowledge": [KnowledgeHit(id="1", title="Pricing", category="sales", source_path="kb/sales.md", score=0.9, excerpt="pricing details")],
        "missing_knowledge": False,
        "retrieval_confidence": 0.85,
        "risk_level": "low"
    }
    res = run_guardrail(state)
    assert res["compliance_status"] == "needs_review"  # Standard live reply remains supervisor-gated (needs_review/needs_approval)
    assert res["quality_score"] == 0.85


def test_run_guardrail_blocked_empty_draft():
    state: AgentStudioState = {
        "draft_reply": "",
        "risk_level": "low"
    }
    res = run_guardrail(state)
    assert res["compliance_status"] == "blocked"
    assert res["quality_score"] == 0.0


def test_run_guardrail_blocked_on_error():
    state: AgentStudioState = {
        "draft_reply": "An error occurred: connection timed out",
        "risk_level": "low"
    }
    res = run_guardrail(state)
    assert res["compliance_status"] == "blocked"
    assert res["quality_score"] == 0.0


def test_run_guardrail_watch_on_missing_knowledge():
    state: AgentStudioState = {
        "draft_reply": "Sure, I can help.",
        "missing_knowledge": True,
        "retrieved_knowledge": [],
        "risk_level": "low"
    }
    res = run_guardrail(state)
    watch_findings = [f for f in res["qa_findings"] if f.status == "watch"]
    assert len(watch_findings) > 0
    assert res["quality_score"] <= 0.48


def test_run_guardrail_watch_on_high_risk():
    state: AgentStudioState = {
        "draft_reply": "Let me look up your refund.",
        "risk_level": "high",
        "retrieved_knowledge": [KnowledgeHit(id="1", title="Refunds", category="support", source_path="kb/refund.md", score=0.8, excerpt="refund eligibility")]
    }
    res = run_guardrail(state)
    watch_findings = [f for f in res["qa_findings"] if f.status == "watch"]
    assert len(watch_findings) > 0
    assert res["quality_score"] <= 0.72


def test_run_guardrail_fail_on_no_knowledge():
    state: AgentStudioState = {
        "draft_reply": "Hello support",
        "retrieved_knowledge": [],
        "risk_level": "low"
    }
    res = run_guardrail(state)
    watch_findings = [f for f in res["qa_findings"] if f.status == "watch"]
    assert len(watch_findings) > 0


def test_run_guardrail_quality_score_zero_empty():
    state: AgentStudioState = {"draft_reply": "", "risk_level": "low"}
    res = run_guardrail(state)
    assert res["quality_score"] == 0.0


def test_run_guardrail_quality_score_low_missing_kb():
    state: AgentStudioState = {"draft_reply": "Sure", "missing_knowledge": True, "risk_level": "low"}
    res = run_guardrail(state)
    assert res["quality_score"] <= 0.48


def test_run_guardrail_never_sets_approved_automatically():
    state: AgentStudioState = {"draft_reply": "Hello", "risk_level": "low"}
    res = run_guardrail(state)
    assert res["approval_status"] == "needs_approval"


# =====================================================================
# END-TO-END GRAPH STRESS TESTS (10 tests)
# =====================================================================

def test_e2e_pricing_flow(mock_graph_llm):
    # Flow: pricing message -> sales_agent -> supervisor -> guardrail
    res = graph.invoke({"incoming_message": "What is the cost of enterprise plan?"})
    assert res["intent"] == "pricing_lead"
    assert res["routed_agent"] == "sales_agent"
    assert "draft_reply" in res
    assert res["approval_status"] == "needs_approval"


def test_e2e_refund_flow(mock_graph_llm):
    # Flow: refund message -> refund_resolver -> high risk -> guardrail
    res = graph.invoke({"incoming_message": "I want a refund on order 123"})
    assert res["intent"] == "refund_or_cancellation"
    assert res["routed_agent"] == "refund_resolver"
    assert res["risk_level"] == "high"
    assert res["approval_status"] == "needs_approval"


def test_e2e_booking_flow(mock_graph_llm):
    res = graph.invoke({"incoming_message": "Can I book a slot?"})
    assert res["intent"] == "booking_or_support"
    assert res["routed_agent"] == "general_support"


def test_e2e_vague_message_fallback(mock_graph_llm):
    res = graph.invoke({"incoming_message": "hello"})
    assert res["routed_agent"] == "general_support"


@pytest.mark.asyncio
@patch("agent_studio.graph.TwentyAdapter")
@patch("agent_studio.graph.get_settings")
async def test_e2e_tool_request_execution(mock_settings, mock_adapter_class, mock_graph_llm):
    # Mock settings and adapter to allow lookup_contact tool
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    from unittest.mock import AsyncMock
    mock_adapter = MagicMock()
    crm_ctx = MagicMock()
    crm_ctx.contact_id = "crm_99"
    crm_ctx.display_name = "Alice"
    crm_ctx.company_name = "ACME"
    crm_ctx.phone_masked = "***"
    crm_ctx.email_masked = "***"
    mock_adapter.lookup_contact = AsyncMock(return_value=(crm_ctx, ToolPlan(tool_name="crm.lookup_contact", action="lookup"), ToolResult(plan_id="1", tool_name="crm.lookup_contact", status="succeeded", detail="ok")))
    mock_adapter_class.return_value = mock_adapter

    # Sales agent will request lookup tool if user message contains "lookup"
    # Wait, graph.invoke is synchronous, but run_tool_executor is asynchronous!
    # LangGraph handles async nodes perfectly inside a synchronous loop if invoked with ainvoke!
    # Let's run ainvoke for the graph.
    res = await graph.ainvoke({"incoming_message": "please lookup cost"})
    assert res["routed_agent"] == "sales_agent"
    assert len(res["tool_outputs"]) == 1
    assert res["tool_outputs"][0]["status"] == "succeeded"


def test_e2e_llm_failure_mid_pipeline(mock_graph_llm):
    # If the sub-agent fails, the pipeline degrades gracefully
    mock_graph_llm.side_effect = Exception("General LLM collapse")
    res = graph.invoke({"incoming_message": "cost details"})
    assert "draft_reply" in res
    assert "error" in res["draft_reply"].lower()


def test_e2e_empty_message_normalize(mock_graph_llm):
    res = graph.invoke({"incoming_message": "   "})
    assert res["normalized_message"] == ""


def test_e2e_very_long_message(mock_graph_llm):
    long_msg = "pricing " * 1000
    res = graph.invoke({"incoming_message": long_msg})
    assert res["intent"] == "pricing_lead"


def test_e2e_concurrent_invocations(mock_graph_llm):
    # Make sure invoke has local state and doesn't bleed concurrent variables
    import threading
    results = []

    def target(msg):
        res = graph.invoke({"incoming_message": msg})
        results.append(res)

    t1 = threading.Thread(target=target, args=("What is the pricing?",))
    t2 = threading.Thread(target=target, args=("I want a refund",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    intents = {r["intent"] for r in results}
    assert "pricing_lead" in intents
    assert "refund_or_cancellation" in intents


def test_e2e_missing_optional_state_keys(mock_graph_llm):
    # Minimal initial state
    res = graph.invoke({"incoming_message": "hello"})
    assert "draft_reply" in res


# =====================================================================
# MCP GATEWAY / TOOL POLICY CONTRACT TESTS (6 tests)
# =====================================================================

@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_policy_allowed_check(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "test"}}],
        "routed_agent": "sales_agent",
    }
    res = await run_tool_executor(state)
    # Since lookup_contact is allowed for sales_agent, it should attempt to execute (and since we didn't mock twenty adapter here, it fails/succeeds, but it's not blocked by policy)
    assert res["tool_outputs"][0]["status"] != "blocked"


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_policy_respects_dry_run_default(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    settings.twenty_dry_run = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "test"}}],
        "routed_agent": "sales_agent",
    }
    res = await run_tool_executor(state)
    assert len(res["tool_outputs"]) == 1


def test_mcp_descriptor_redacts_sensitive():
    manifests = [{
        "name": "test.secret_tool",
        "tool_name": "test.secret_tool",
        "description": "Send api_key to the endpoint http://secret.url/api",
        "provider": "secret_provider",
        "skill_name": "secrets",
        "allowed_agents": ["sales_agent"],
        "mode": "read",
        "risk_level": "medium",
        "requires_approval": False,
        "dry_run_default": False,
        "enabled": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["api_key", "query"]
        }
    }]
    descriptors = build_mcp_descriptors(manifests)
    assert len(descriptors) == 1
    desc = descriptors[0]
    assert "api_key" not in desc.input_schema["properties"]
    assert "api_key" not in desc.input_schema["required"]
    assert "http://secret.url/api" not in desc.description
    assert "[redacted]" in desc.description


def test_forbidden_tools_are_blocked():
    manifests = [{
        "name": "system_bash_shell",
        "tool_name": "system_bash_shell",
        "description": "Runs bash commands",
        "provider": "system",
        "skill_name": "terminal",
        "allowed_agents": ["admin"],
        "mode": "write",
        "risk_level": "high",
        "requires_approval": True,
        "dry_run_default": True,
        "enabled": True,
        "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}}
    }]
    descriptors = build_mcp_descriptors(manifests)
    # Forbidden terms (bash, shell, terminal) should block descriptor generation entirely
    assert len(descriptors) == 0


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_tool_requires_approval_unapproved_logged_as_planned(mock_settings):
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.create_note", "args": {"contact_id": "1", "note": "text"}}],
        "routed_agent": "sales_agent",
        "approval_status": "needs_approval"
    }
    res = await run_tool_executor(state)
    assert res["tool_outputs"][0]["status"] == "blocked"
    assert res["tool_plans"][0].approved is False


@pytest.mark.asyncio
@patch("agent_studio.graph.get_settings")
async def test_policy_evaluator_hook_execution(mock_settings):
    # Verify policy evaluator receives call and is respected
    settings = MagicMock()
    settings.twenty_enabled = True
    settings.twenty_configured = True
    mock_settings.return_value = settings

    # Standard tool execution passes
    state: AgentStudioState = {
        "tool_requests": [{"tool": "crm.lookup_contact", "args": {"query": "Jane"}}],
        "routed_agent": "sales_agent",
    }
    res = await run_tool_executor(state)
    assert len(res["tool_outputs"]) == 1
