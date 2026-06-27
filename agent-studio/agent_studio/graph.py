import os
import re
import json
from functools import lru_cache
import litellm
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk
from langgraph.graph import END, START, StateGraph

from agent_studio.agents import AgentRegistry
from agent_studio.memory_workflow import build_memory_pack
from agent_studio.retrieval import get_retriever
from agent_studio.schemas import ConversationMessageRecord, KnowledgeHit, MemoryHit, QaFinding
from agent_studio.skill_registry import skill_registry
from agent_studio.state import AgentStudioState
from agent_studio.tool_policy import evaluate_tool_policy, ToolPolicyContext
from agent_studio.twenty import TwentyAdapter
from agent_studio.config import get_settings

try:
    from agent_studio.retrieval_workflow import build_query_plan, build_retrieval_pack
except ImportError as exc:
    build_query_plan = None
    build_retrieval_pack = None
    RETRIEVAL_WORKFLOW_IMPORT_ERROR: str | None = str(exc)
else:
    RETRIEVAL_WORKFLOW_IMPORT_ERROR = None


@lru_cache
def get_agent_registry() -> AgentRegistry:
    """Lazily load and cache the agent registry.

    Avoids filesystem scanning at import time so the module can be imported
    for type-checking or health checks without loading every agent .md file.
    """
    return AgentRegistry()


# The LiteLLMLangChainWrapper constructs a fresh instance per node call, so
# its ``self.tools`` mutation in ``bind_tools`` is never shared across threads
# or nodes.  Do not cache or reuse a wrapper across concurrent invocations.



class LiteLLMLangChainWrapper:
    def __init__(self, model: str, api_base: str | None = None, api_key: str | None = None):
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.tools = None

    def bind_tools(self, tools, tool_choice=None):
        self.tools = tools
        return self

    def _convert_messages(self, messages):
        litellm_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                litellm_messages.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                litellm_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                litellm_messages.append({"role": "assistant", "content": m.content})
            elif hasattr(m, "content"):
                litellm_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, dict):
                litellm_messages.append(m)
        return litellm_messages

    def invoke(self, messages):
        litellm_messages = self._convert_messages(messages)
        kwargs = {
            "model": self.model,
            "messages": litellm_messages,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "none"

        response = litellm.completion(**kwargs)
        response_message = response.choices[0].message
        content = response_message.content or ""
        
        tool_calls = []
        if getattr(response_message, "tool_calls", None):
            for tc in response_message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if tc.function.arguments else {},
                    "id": tc.id,
                })
        
        return AIMessage(content=content, tool_calls=tool_calls)

    async def astream(self, messages):
        litellm_messages = self._convert_messages(messages)
        kwargs = {
            "model": self.model,
            "messages": litellm_messages,
            "stream": True,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "none"

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield AIMessageChunk(content=content)


class DryRunChatModel:
    """Deterministic stub chat model for CI / local e2e without LLM credentials.

    Enabled via ``LLM_MODE=dry_run``. Inspects the system prompt to emit canned responses
    that drive the graph forward end-to-end: classifier JSON routing by keyword, sub-agent
    JSON analysis, a supervisor agent.* tool call on the first pass, a plain-text draft on
    re-entry, and a streaming draft for ``/conversations/{id}/draft/stream``. No network,
    no API key, no GPU — so the compose e2e roundtrip is fully deterministic in CI.
    """

    def __init__(self, model: str = "dry-run") -> None:
        self.model = model
        self.tools: list[dict[str, object]] | None = None
        self.tool_choice: object | None = None

    def bind_tools(self, tools, tool_choice=None):
        self.tools = tools or []
        self.tool_choice = tool_choice
        return self

    @staticmethod
    def _messages_text(messages) -> tuple[str, str]:
        sys_msg = next((m.content for m in messages if isinstance(m, SystemMessage)), "") or ""
        user_msg = next((m.content for m in messages if isinstance(m, HumanMessage)), "") or ""
        return sys_msg, user_msg

    def _respond(self, messages):
        sys_msg, user_msg = self._messages_text(messages)
        low = (user_msg or "").lower()
        is_draft_stream = "Respond directly with the message content" in sys_msg
        is_supervisor = "Supervisor Agent" in sys_msg or "supervisor_agent" in sys_msg

        # Supervisor node — checked first because its system prompt embeds the sub-agent
        # report (which contains sub-agent keywords like "sales_agent").
        if is_supervisor:
            # First pass: agent tools are bound — emit one agent.* tool call so the pipeline
            # progresses to a sub-agent, then back to the supervisor for the draft.
            if self.tools:
                for tool in self.tools:
                    name = (
                        tool["function"]["name"]
                        if isinstance(tool, dict) and "function" in tool
                        else getattr(tool, "name", "")
                    )
                    if name.startswith("agent."):
                        return AIMessage(
                            content="",
                            tool_calls=[{"name": name, "args": {"message": user_msg or "hello"}, "id": "dryrun-tool-1"}],
                        )
            # Re-entry (draft synthesis) or draft-stream endpoint — plain text only.
            if is_draft_stream:
                return AIMessage(content="Here is the finalized draft for your request. Let me know if you need anything else.")
            return AIMessage(content="This is the finalized draft reply from the supervisor.")

        # Classifier node.
        if "Classifier Agent" in sys_msg or "classifier_agent" in sys_msg:
            if "refund" in low or "cancel" in low:
                return AIMessage(content='{"intent":"refund_or_cancellation","risk_level":"high","routed_agent":"refund_resolver"}')
            if any(w in low for w in ("price", "pricing", "quote", "cost", "plan")):
                return AIMessage(content='{"intent":"pricing_lead","risk_level":"low","routed_agent":"sales_agent"}')
            if any(w in low for w in ("appoint", "schedule", "book")):
                return AIMessage(content='{"intent":"booking_or_support","risk_level":"medium","routed_agent":"general_support"}')
            return AIMessage(content='{"intent":"general_support","risk_level":"medium","routed_agent":"general_support"}')

        # Sub-agent nodes return a structured JSON report.
        if "Sales Agent" in sys_msg or "sales_agent" in sys_msg:
            return AIMessage(content='{"agent":"sales_agent","analysis":"pricing info","recommended_action":"DRAFT_REPLY","tool_requests":[],"draft_hint":"Here is the pricing info.","confidence":0.9,"risk_flags":[]}')
        if "Refund Resolver" in sys_msg or "refund_resolver" in sys_msg:
            return AIMessage(content='{"agent":"refund_resolver","analysis":"refund request","recommended_action":"DRAFT_REPLY","tool_requests":[],"draft_hint":"Refund needs supervisor review.","confidence":0.95,"risk_flags":["refund_request"]}')
        if "General Support" in sys_msg or "general_support" in sys_msg:
            return AIMessage(content='{"agent":"general_support","analysis":"general query","recommended_action":"DRAFT_REPLY","tool_requests":[],"draft_hint":"Here is the support response.","confidence":0.88,"risk_flags":[]}')

        # Draft-stream endpoint for a non-supervisor agent (plain text only).
        if is_draft_stream:
            return AIMessage(content="Here is the finalized draft for your request. Let me know if you need anything else.")

        # Default fallback.
        return AIMessage(content="This is the finalized draft reply from the supervisor.")

    def invoke(self, messages):
        return self._respond(messages)

    async def ainvoke(self, messages):
        return self._respond(messages)

    async def astream(self, messages):
        response = self._respond(messages)
        text = response.content or ""
        # Stream word-by-word so /conversations/{id}/draft/stream emits real SSE tokens.
        for token in text.split():
            yield AIMessageChunk(content=token + " ")


def _build_chat_model(node_type: str | None = None):
    """Build a chat model from the resolved provider config.

    Resolution lives in :mod:`agent_studio.model_config` (one source of truth for chat +
    embeddings). When ``LLM_MODE=dry_run`` is set, or the active provider is ``none`` /
    missing credentials, returns a :class:`DryRunChatModel` so the graph runs deterministically
    with no network and no credentials. Per-node model overrides (CLASSIFIER_MODEL etc.) are
    applied by the resolver.
    """
    from agent_studio.config import get_settings
    from agent_studio.integration_config import configured_settings
    from agent_studio.model_config import resolve_chat_config

    if os.getenv("LLM_MODE", "").lower() == "dry_run":
        return DryRunChatModel(model="dry-run")
    # configured_settings merges DB model-provider config (SuperAdmin console) over env, so the
    # resolver sees the writable config. context=None resolves the default org (single-tenant).
    settings = configured_settings(get_settings(), context=None)
    cfg = resolve_chat_config(settings, node_type=node_type)
    if not cfg.configured:
        return DryRunChatModel(model="dry-run")
    return LiteLLMLangChainWrapper(model=cfg.model, api_base=cfg.api_base, api_key=cfg.api_key)



TOOL_SCHEMAS = {
    "crm.lookup_contact": {
        "type": "function",
        "function": {
            "name": "crm.lookup_contact",
            "description": "Look up a contact in the CRM",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the contact",
                    },
                },
                "required": ["query"],
            },
        },
    },
}

CUSTOMER_DRIVERS_BY_INTENT = {
    "refund_or_cancellation": "refund or cancellation",
    "pricing_lead": "pricing or quote",
    "booking_or_support": "booking or support",
    "general_support": "general support",
}


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _field_list(value: object, name: str) -> list[object]:
    found = _field(value, name, [])
    if found is None:
        return []
    if isinstance(found, str):
        return [found]
    return list(found)


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded_score(score: float) -> float:
    if score <= 0:
        return 0.0
    if score <= 1:
        return score
    return min(1.0, score / (score + 4.0))


def _resolve_markdown_agent(intent: str, selected_agent: str | None = None):
    registry = get_agent_registry()
    agent = registry.get_agent(intent)
    if agent:
        return agent
    if selected_agent:
        agent = registry.get_agent(selected_agent)
        if agent:
            return agent
    return registry.get_agent("general_support")


def _customer_driver(intent: str, message: str) -> str:
    if intent != "general_support":
        return CUSTOMER_DRIVERS_BY_INTENT.get(intent, intent.replace("_", " "))
    if any(term in message for term in ["refund", "cancel", "complaint"]):
        return "refund or cancellation"
    if any(term in message for term in ["price", "pricing", "quote", "cost"]):
        return "pricing or quote"
    if any(term in message for term in ["appointment", "schedule", "book", "reschedule"]):
        return "booking or support"
    return "general support"


def _source_to_knowledge_hit(source: object) -> KnowledgeHit:
    return KnowledgeHit(
        id=str(_field(source, "id", "")),
        title=str(_field(source, "title", "Untitled source")),
        category=str(_field(source, "category", "general")),
        source_path=str(_field(source, "source_path", "")),
        score=_coerce_float(_field(source, "score", _field(source, "rerank_score", 0.0))),
        excerpt=str(_field(source, "excerpt", "")),
    )


def _source_diagnostic(source: object) -> dict[str, object]:
    return {
        "id": str(_field(source, "id", "")),
        "title": str(_field(source, "title", "")),
        "category": str(_field(source, "category", "")),
        "source_path": str(_field(source, "source_path", "")),
        "score": _coerce_float(_field(source, "score", 0.0)),
        "rerank_score": _coerce_float(_field(source, "rerank_score", 0.0)),
        "reasons": [str(reason) for reason in _field_list(source, "reasons")],
    }


def _plan_diagnostic(plan: object) -> dict[str, object]:
    return {
        "raw_query": str(_field(plan, "raw_query", "")),
        "normalized_query": str(_field(plan, "normalized_query", "")),
        "intent": str(_field(plan, "intent", "")),
        "risk_level": str(_field(plan, "risk_level", "")),
        "selected_agent": str(_field(plan, "selected_agent", "")),
        "expanded_queries": [str(query) for query in _field_list(plan, "expanded_queries")],
        "metadata_filters": dict(_field(plan, "metadata_filters", {}) or {}),
        "candidate_limit": int(_field(plan, "candidate_limit", 8) or 8),
        "source_limit": int(_field(plan, "source_limit", 4) or 4),
    }


def _search_query_from_plan(plan: object, fallback: str) -> str:
    plan_data = _plan_diagnostic(plan)
    query_parts = [
        str(plan_data["normalized_query"]) or fallback,
        *[str(query) for query in plan_data["expanded_queries"]],
    ]
    return " ".join(dict.fromkeys(part for part in query_parts if part))


def _fallback_confidence(hits: list[KnowledgeHit], source_limit: int = 4) -> float:
    if not hits:
        return 0.0
    top_score = max(_bounded_score(hit.score) for hit in hits)
    coverage_score = min(1.0, len(hits) / max(source_limit, 1))
    return round(min(0.55, (top_score * 0.70) + (coverage_score * 0.20) + 0.10), 4)


def _legacy_retrieval(
    state: AgentStudioState,
    *,
    selected_agent: str,
    customer_driver: str,
    reason: str,
    error: str | None = None,
) -> dict[str, object]:
    query = state["normalized_message"]
    try:
        hits = get_retriever().search(
            query,
            intent=state["intent"],
            risk_level=state["risk_level"],
            limit=4,
        )
    except Exception as exc:
        diagnostic: dict[str, object] = {
            "workflow": "legacy_retriever_fallback",
            "workflow_available": False,
            "selected_agent": selected_agent,
            "customer_driver": customer_driver,
            "search_query": query,
            "candidate_count": 0,
            "selected_count": 0,
            "reasons": [reason, "retriever search failed"],
            "error": str(exc),
        }
        if error:
            diagnostic["workflow_error"] = error
        if RETRIEVAL_WORKFLOW_IMPORT_ERROR:
            diagnostic["workflow_import_error"] = RETRIEVAL_WORKFLOW_IMPORT_ERROR
        return {
            "selected_agent": selected_agent,
            "customer_driver": customer_driver,
            "retrieved_knowledge": [],
            "retrieval_confidence": 0.0,
            "missing_knowledge": True,
            "retrieval_diagnostic": diagnostic,
        }

    selected = list(hits)
    confidence = _fallback_confidence(selected)
    missing_knowledge = not selected or confidence < 0.40
    reasons = [reason]
    if not selected:
        reasons.append("no approved sources retrieved")
    if missing_knowledge and selected:
        reasons.append("legacy retrieval confidence below threshold")
    diagnostic = {
        "workflow": "legacy_retriever_fallback",
        "workflow_available": False,
        "selected_agent": selected_agent,
        "customer_driver": customer_driver,
        "search_query": query,
        "candidate_count": len(hits),
        "selected_count": len(selected),
        "selected_sources": [_source_diagnostic(hit) for hit in selected],
        "reasons": reasons,
    }
    if error:
        diagnostic["workflow_error"] = error
    if RETRIEVAL_WORKFLOW_IMPORT_ERROR:
        diagnostic["workflow_import_error"] = RETRIEVAL_WORKFLOW_IMPORT_ERROR
    return {
        "selected_agent": selected_agent,
        "customer_driver": customer_driver,
        "retrieved_knowledge": selected,
        "retrieval_confidence": confidence,
        "missing_knowledge": missing_knowledge,
        "retrieval_diagnostic": diagnostic,
    }


def normalize_message(state: AgentStudioState) -> dict[str, str]:
    message = state["incoming_message"].strip()
    return {"normalized_message": " ".join(message.split())}


def classify_message(state: AgentStudioState) -> dict[str, str]:
    message = state["normalized_message"].lower()
    memory_text = " ".join(
        hit.content.lower()
        for hit in state.get("memory_context", [])
        if isinstance(hit, MemoryHit)
    )
    vague_followup = any(term in message for term in ["already", "that", "it", "same", "this"])
    classification_text = f"{message} {memory_text}" if vague_followup else message

    if any(term in classification_text for term in ["refund", "cancel", "angry", "complaint"]):
        return {"intent": "refund_or_cancellation", "risk_level": "high"}
    if any(term in classification_text for term in ["price", "pricing", "quote", "cost"]):
        return {"intent": "pricing_lead", "risk_level": "low"}
    if any(term in classification_text for term in ["appointment", "schedule", "book", "reschedule"]):
        return {"intent": "booking_or_support", "risk_level": "medium"}
    if len(message.split()) <= 2:
        return {"intent": "general_support", "risk_level": "medium"}
    return {"intent": "general_support", "risk_level": "medium"}


def retrieve_memory(state: AgentStudioState) -> dict[str, object]:
    history = [
        message
        if isinstance(message, ConversationMessageRecord)
        else ConversationMessageRecord.model_validate(message)
        for message in state.get("conversation_history", [])
    ]
    durable_memory = [
        hit if isinstance(hit, MemoryHit) else MemoryHit.model_validate(hit)
        for hit in state.get("memory_context", [])
    ]
    pack = build_memory_pack(
        current_message=state.get("normalized_message") or state["incoming_message"],
        recent_messages=history,
        durable_memory=durable_memory,
        conversation_id=state.get("conversation_id"),
        chatwoot_conversation_id=state.get("chatwoot_conversation_id"),
        limit=5,
    )
    return {
        "memory_context": pack.memory_context,
        "memory_diagnostic": pack.memory_diagnostic,
    }


def select_markdown_agent(state: AgentStudioState) -> dict[str, str | None]:
    intent = state.get("intent", "general_support")
    message = state.get("normalized_message", "").lower()
    agent = _resolve_markdown_agent(intent)
    selected_agent = agent.name if agent else "general_support"
    return {
        "selected_agent": selected_agent,
        "customer_driver": _customer_driver(intent, message),
    }


def retrieve_knowledge(state: AgentStudioState) -> dict[str, object]:
    selected_agent = state.get("selected_agent") or "general_support"
    customer_driver = state.get("customer_driver") or _customer_driver(
        state.get("intent", "general_support"),
        state.get("normalized_message", "").lower(),
    )
    if build_query_plan is None or build_retrieval_pack is None:
        return _legacy_retrieval(
            state,
            selected_agent=selected_agent,
            customer_driver=customer_driver,
            reason="agent_studio.retrieval_workflow is unavailable",
        )

    try:
        plan = build_query_plan(
            message=state["normalized_message"],
            intent=state["intent"],
            risk_level=state["risk_level"],
            selected_agent=selected_agent,
            customer_driver=customer_driver,
        )
        plan_data = _plan_diagnostic(plan)
        search_query = _search_query_from_plan(plan, state["normalized_message"])
        hits = get_retriever().search(
            search_query,
            intent=state["intent"],
            risk_level=state["risk_level"],
            limit=int(plan_data["candidate_limit"]),
        )
        pack = build_retrieval_pack(plan=plan, hits=hits)
    except Exception as exc:
        return _legacy_retrieval(
            state,
            selected_agent=selected_agent,
            customer_driver=customer_driver,
            reason="retrieval workflow failed",
            error=str(exc),
        )

    selected_sources = _field_list(pack, "selected_sources")
    selected_hits = [_source_to_knowledge_hit(source) for source in selected_sources]
    diagnostic = {
        "workflow": "retrieval_workflow",
        "workflow_available": True,
        "selected_agent": selected_agent,
        "customer_driver": customer_driver,
        "query_plan": plan_data,
        "search_query": search_query,
        "candidate_count": len(hits),
        "selected_count": len(selected_hits),
        "selected_sources": [_source_diagnostic(source) for source in selected_sources],
        "reasons": [str(reason) for reason in _field_list(pack, "reasons")],
    }
    return {
        "selected_agent": selected_agent,
        "customer_driver": customer_driver,
        "retrieved_knowledge": selected_hits,
        "retrieval_confidence": _coerce_float(_field(pack, "retrieval_confidence", 0.0)),
        "missing_knowledge": bool(_field(pack, "missing_knowledge", not selected_hits)),
        "retrieval_diagnostic": diagnostic,
    }





def _parse_json_from_llm(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n", "", content)
        content = re.sub(r"\n```$", "", content)
    content = content.strip()
    return json.loads(content)


def _prepare_agent_prompt_with_context(agent_prompt: str, state: AgentStudioState) -> str:
    prompt = agent_prompt
    memory = state.get("memory_context", [])
    knowledge = state.get("retrieved_knowledge", [])
    if memory:
        memory_context = "\n".join(
            [
                f"- {hit.memory_type} ({hit.source}, score {hit.score:.2f}): {hit.content}"
                for hit in memory
            ]
        )
        prompt += (
            "\n\nConversation Memory:\n"
            f"{memory_context}\n"
            "Use conversation memory only for customer/thread context."
        )
    if knowledge:
        knowledge_context = "\n".join(
            [
                f"- {hit.title} ({hit.category}, score {hit.score:.2f}): {hit.excerpt}"
                for hit in knowledge
            ]
        )
        prompt += f"\n\nSelected Source Pack:\n{knowledge_context}"
    if state.get("missing_knowledge"):
        prompt += (
            "\n\nThe selected sources may be insufficient. Do not invent policy details."
        )
    return prompt


def classify_and_route(state: AgentStudioState) -> dict[str, object]:
    message = state["incoming_message"].strip()
    normalized_message = " ".join(message.split())

    agent = get_agent_registry().get_agent("classifier_agent")
    system_prompt = agent.system_prompt if agent else "Classify the user intent and routed agent."

    try:
        llm = _build_chat_model("classifier")
        lc_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=normalized_message),
        ]
        response = llm.invoke(lc_messages)
        body = response.content or ""

        data = _parse_json_from_llm(body)
        intent = data.get("intent", "general_support")
        risk_level = data.get("risk_level", "medium")
        routed_agent = data.get("routed_agent", "general_support")
    except Exception:
        message_lower = normalized_message.lower()
        if any(term in message_lower for term in ["refund", "cancel", "angry", "complaint"]):
            intent = "refund_or_cancellation"
            risk_level = "high"
            routed_agent = "refund_resolver"
        elif any(term in message_lower for term in ["price", "pricing", "quote", "cost"]):
            intent = "pricing_lead"
            risk_level = "low"
            routed_agent = "sales_agent"
        elif any(term in message_lower for term in ["appointment", "schedule", "book", "reschedule"]):
            intent = "booking_or_support"
            risk_level = "medium"
            routed_agent = "general_support"
        else:
            intent = "general_support"
            risk_level = "medium"
            routed_agent = "general_support"

    return {
        "normalized_message": normalized_message,
        "intent": intent,
        "risk_level": risk_level,
        "routed_agent": routed_agent,
        "selected_agent": routed_agent,
        "customer_driver": _customer_driver(intent, normalized_message.lower())
    }


def _run_sub_agent(state: AgentStudioState, agent_key: str) -> dict[str, object]:
    agent = get_agent_registry().get_agent(agent_key)
    if not agent:
        return {
            "sub_agent_report": {
                "agent": agent_key,
                "analysis": "Agent configuration missing.",
                "recommended_action": "ESCALATE",
                "tool_requests": [],
                "draft_hint": "I need assistance from a supervisor.",
                "confidence": 0.0,
                "risk_flags": ["missing_config"]
            },
            "tool_requests": []
        }

    prompt = _prepare_agent_prompt_with_context(agent.system_prompt, state)

    try:
        llm = _build_chat_model("extractor")
        lc_messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=state["normalized_message"]),
        ]
        response = llm.invoke(lc_messages)
        body = response.content or ""

        report = _parse_json_from_llm(body)

        report.setdefault("agent", agent.name)
        report.setdefault("analysis", "")
        report.setdefault("recommended_action", "DRAFT_REPLY")
        report.setdefault("tool_requests", [])
        report.setdefault("draft_hint", "")
        report.setdefault("confidence", 0.5)
        report.setdefault("risk_flags", [])

        tool_requests = report.get("tool_requests", [])
        if not isinstance(tool_requests, list):
            tool_requests = []

        return {
            "sub_agent_report": report,
            "tool_requests": tool_requests
        }
    except Exception as exc:
        return {
            "sub_agent_report": {
                "agent": agent.name,
                "analysis": f"Error running sub-agent: {exc}",
                "recommended_action": "ESCALATE",
                "tool_requests": [],
                "draft_hint": "I encountered an internal error and need supervisor review.",
                "confidence": 0.0,
                "risk_flags": ["agent_execution_error"]
            },
            "tool_requests": []
        }


def run_sales_agent(state: AgentStudioState) -> dict[str, object]:
    return _run_sub_agent(state, "pricing_lead")


def run_refund_resolver(state: AgentStudioState) -> dict[str, object]:
    return _run_sub_agent(state, "refund_or_cancellation")


def run_support_agent(state: AgentStudioState) -> dict[str, object]:
    return _run_sub_agent(state, "general_support")


async def run_tool_executor(state: AgentStudioState) -> dict[str, object]:
    tool_requests = state.get("tool_requests", [])
    tool_outputs = list(state.get("tool_outputs", []))
    tool_plans = list(state.get("tool_plans", []))
    tool_results = list(state.get("tool_results", []))

    selected_agent = state.get("routed_agent") or "general_support"
    risk_level = state.get("risk_level") or "medium"

    settings = get_settings()

    # Track whether we ran an agent tool so the supervisor can re-enter
    ran_agent_tool = False

    for tr in tool_requests:
        tool_name = tr.get("tool")
        args = tr.get("args", {})

        # ---- Agent tool: supervisor delegated to a sub-agent ----
        if tool_name.startswith("agent."):
            agent_name = tool_name.removeprefix("agent.")
            # Map agent name to intent key via registry lookup
            registry = get_agent_registry()
            agent_config = next(
                (a for a in registry.get_all_agents() if a.name == agent_name),
                None,
            )
            if agent_config and agent_config.intents:
                first_intent = agent_config.intents[0]
                sub_result = _run_sub_agent(state, first_intent)
                tool_outputs.append({
                    "tool": tool_name,
                    "status": "succeeded",
                    "output": {
                        "sub_agent_report": sub_result.get("sub_agent_report", {}),
                        "tool_requests": sub_result.get("tool_requests", []),
                    }
                })
                ran_agent_tool = True
            else:
                tool_outputs.append({
                    "tool": tool_name,
                    "status": "blocked",
                    "reason": f"Agent '{agent_name}' not found in registry.",
                })
            continue

        approved = state.get("approval_status") == "approved" or state.get("approved", False)

        policy_context = ToolPolicyContext(
            selected_agent=selected_agent,
            conversation_risk=risk_level,
            approved=approved,
            autonomous=True,
            provider_enabled=settings.twenty_enabled,
            provider_configured=settings.twenty_configured,
            provider_dry_run=settings.twenty_dry_run,
            provider_writes_enabled=settings.twenty_allow_writes,
        )

        policy_decision = evaluate_tool_policy(
            tool_name,
            policy_context,
        )

        if policy_decision.allowed:
            try:
                if tool_name == "crm.lookup_contact":
                    adapter = TwentyAdapter(settings)
                    query = args.get("query", "")
                    crm_context, plan, result = await adapter.lookup_contact(
                        query=query,
                        conversation_id=state.get("conversation_id"),
                    )

                    tool_plans.append(plan)
                    tool_results.append(result)

                    tool_outputs.append({
                        "tool": tool_name,
                        "status": "succeeded",
                        "output": {
                            "contact_id": crm_context.contact_id if crm_context else None,
                            "display_name": crm_context.display_name if crm_context else None,
                            "company_name": crm_context.company_name if crm_context else None,
                            "phone_masked": crm_context.phone_masked if crm_context else None,
                            "email_masked": crm_context.email_masked if crm_context else None,
                        }
                    })
                else:
                    tool_outputs.append({
                        "tool": tool_name,
                        "status": "blocked",
                        "reason": f"Tool {tool_name} execution not implemented."
                    })
            except Exception as e:
                tool_outputs.append({
                    "tool": tool_name,
                    "status": "failed",
                    "error": str(e)
                })
        else:
            from agent_studio.schemas import ToolPlan, ToolResult
            plan = ToolPlan(
                tool_name=tool_name,
                action="Blocked",
                args=args,
                requires_approval=policy_decision.requires_approval,
                approved=approved,
                dry_run=policy_decision.dry_run,
                risk_level=risk_level,
            )
            result = ToolResult(
                plan_id=plan.id,
                tool_name=tool_name,
                status="blocked",
                detail=policy_decision.blocked_reason or "Blocked by tool policy.",
            )
            tool_plans.append(plan)
            tool_results.append(result)
            tool_outputs.append({
                "tool": tool_name,
                "status": "blocked",
                "reason": policy_decision.blocked_reason or "Blocked by tool policy."
            })

    # Clear processed tool_requests to prevent infinite re-entry.  Only
    # repopulate them when an agent tool just ran and its sub-agent
    # requested new (as-yet-unprocessed) CRM tools.
    result: dict[str, object] = {
        "tool_outputs": tool_outputs,
        "tool_plans": tool_plans,
        "tool_results": tool_results,
        "tool_requests": [],  # clear processed requests
    }

    # If an agent tool was executed, promote its report into the graph state
    # so the supervisor can see it on re-entry.
    if ran_agent_tool:
        for to in tool_outputs:
            if to.get("tool", "").startswith("agent.") and to.get("status") == "succeeded":
                output = to.get("output", {})
                report = output.get("sub_agent_report")
                if report:
                    result["sub_agent_report"] = report
                    # Also propagate any tool requests the sub-agent made
                    sub_tool_requests = output.get("tool_requests", [])
                    if sub_tool_requests:
                        result["tool_requests"] = sub_tool_requests
                break

    return result


def _build_agent_tool_schemas() -> list[dict]:
    """Build tool schemas for all registered sub-agents so the supervisor can call them as tools."""
    registry = get_agent_registry()
    schemas: list[dict] = []
    for agent in registry.get_all_agents():
        if agent.name in ("classifier_agent", "supervisor_agent"):
            continue
        schemas.append({
            "type": "function",
            "function": {
                "name": f"agent.{agent.name}",
                "description": f"Analyze as {agent.name}. Intents: {', '.join(agent.intents)}.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Customer message"},
                    },
                    "required": ["message"],
                },
            },
        })
    return schemas


def _has_agent_tool_calls(response: AIMessage) -> list[dict]:
    """Check if the LLM response contains agent tool calls."""
    tcs = getattr(response, "tool_calls", None) or []
    return [tc for tc in tcs if tc.get("name", "").startswith("agent.")]



def supervisor_draft(state: AgentStudioState) -> dict[str, object]:
    """Supervisor node — pick sub-agent via tool call or write the final draft.

    First pass (no sub_agent_report): the supervisor has agent-tool schemas bound
    as function calls. It selects the right sub-agent and returns the tool request.

    Re-entry (sub_agent_report exists): the supervisor synthesises the final
    customer-facing draft from the sub-agent report + tool outputs.
    """
    existing_report = state.get("sub_agent_report") or {}
    has_report = bool(existing_report.get("analysis"))

    agent = get_agent_registry().get_agent("supervisor_agent")
    system_prompt = agent.system_prompt if agent else "You are the supervisor. Synthesize response."

    if not has_report:
        # ---- First pass: bind agent tools, let supervisor pick one ----
        agent_tools = _build_agent_tool_schemas()
        tool_desc = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in agent_tools)
        system_prompt += (
            f"\n\n# Agent Tools Available\n{tool_desc}\n\n"
            "Call ONE agent tool with the customer message. "
            "The agent returns a structured analysis. "
            "If you already have a sub-agent report, ignore tools and write the draft."
        )
    else:
        # ---- Re-entry: we have sub-agent report + tool outputs, write draft ----
        report = existing_report
        tool_outputs = state.get("tool_outputs") or []
        context_str = f"SUB-AGENT REPORT:\n{json.dumps(report, indent=2)}\n\nTOOL OUTPUTS:\n{json.dumps(tool_outputs, indent=2)}"
        knowledge = state.get("retrieved_knowledge", [])
        if knowledge:
            knowledge_context = "\n".join(f"- {hit.title} ({hit.category}, score {hit.score:.2f}): {hit.excerpt}" for hit in knowledge)
            context_str += f"\n\nSELECTED SOURCE PACK:\n{knowledge_context}"
        system_prompt += (
            f"\n\n# Context\n{context_str}\n\n"
            "Write the final customer-facing draft based on the sub-agent analysis "
            "and tool outputs. No JSON or tool logs — plain text only."
        )

    try:
        llm = _build_chat_model("supervisor")
        if not has_report:
            llm = llm.bind_tools(agent_tools, tool_choice="auto")

        msg = state.get("normalized_message", state.get("incoming_message", ""))
        lc_messages = [SystemMessage(content=system_prompt), HumanMessage(content=msg)]
        response = llm.invoke(lc_messages)
        body = (response.content or "").strip()

        # ---- Detect agent tool calls (first-pass) ----
        agent_calls = _has_agent_tool_calls(response)
        if agent_calls and not has_report:
            return {
                "tool_requests": [{"tool": tc["name"], "args": tc.get("args", {}), "id": tc.get("id", "")} for tc in agent_calls],
                "draft_reply": "",
                "approval_status": "needs_approval",
            }

        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\n", "", body)
            body = re.sub(r"\n```$", "", body)
        body = body.strip()
        if not body:
            body = "I am looking into this request. One moment please."
    except Exception as exc:
        body = f"An error occurred: {exc}"

    knowledge = state.get("retrieved_knowledge", [])
    citation_titles = ", ".join(hit.title for hit in knowledge[:4])
    if citation_titles and not body.startswith("An error occurred:"):
        body = f"{body}\n\nBasis: {citation_titles}."

    return {"draft_reply": body, "approval_status": "needs_approval"}


def run_guardrail(state: AgentStudioState) -> dict[str, object]:
    knowledge = state.get("retrieved_knowledge", [])
    memory = state.get("memory_context", [])
    missing_knowledge = bool(state.get("missing_knowledge", not knowledge))
    retrieval_confidence = state.get("retrieval_confidence")
    draft = state.get("draft_reply", "")
    has_draft_error = draft.startswith("An error occurred:")
    has_empty_draft = not draft.strip()

    findings = []

    if knowledge and not missing_knowledge:
        knowledge_status = "pass"
        knowledge_detail = "Draft includes selected KB/SOP source-pack context."
    elif knowledge:
        knowledge_status = "watch"
        knowledge_detail = "Selected sources were weak or incomplete; supervisor review is required."
    else:
        knowledge_status = "watch"
        knowledge_detail = "No matching knowledge was retrieved."

    if retrieval_confidence is not None:
        knowledge_detail = f"{knowledge_detail} Retrieval confidence: {retrieval_confidence:.2f}."

    findings.append(
        QaFinding(
            label="Knowledge basis",
            status=knowledge_status,
            detail=knowledge_detail,
        )
    )

    findings.append(
        QaFinding(
            label="HITL policy",
            status="pass",
            detail="Live Chatwoot replies require supervisor approval.",
        )
    )

    if missing_knowledge:
        findings.append(
            QaFinding(
                label="Missing knowledge",
                status="watch",
                detail="Graph marked the source pack as insufficient or low confidence.",
            ),
        )

    if memory and knowledge:
        memory_text = " ".join(hit.content.lower() for hit in memory)
        knowledge_text = " ".join(
            f"{hit.title} {hit.excerpt}".lower()
            for hit in knowledge
        )
        conflict_terms = ["refund", "cancel", "pricing", "quote"]
        conflicts = [
            term
            for term in conflict_terms
            if term in memory_text and term not in knowledge_text
        ]
        if conflicts:
            findings.append(
                QaFinding(
                    label="Memory policy boundary",
                    status="watch",
                    detail=(
                        "Conversation memory mentions operational context not present in the selected source pack; "
                        "do not let memory override approved policy."
                    ),
                ),
            )

    if has_draft_error or has_empty_draft:
        findings.append(
            QaFinding(
                label="Draft generation",
                status="fail",
                detail="Model/provider output failed or returned no sendable draft.",
            ),
        )

    if state.get("risk_level") == "high":
        findings.append(
            QaFinding(
                label="High-risk escalation",
                status="watch",
                detail="Refund, cancellation, and complaint language must remain supervisor-gated.",
            ),
        )

    diagnostic = dict(state.get("retrieval_diagnostic", {}) or {})
    diagnostic["skill_diagnostic"] = skill_registry.graph_diagnostic(
        selected_agent=state.get("routed_agent") or "general_support",
        completed_stages=[
            "normalize",
            "retrieve_memory",
            "classify",
            "select_agent",
            "retrieve",
            "draft",
            "qa_compliance",
        ],
    )

    quality_score = 0.88
    if retrieval_confidence is not None:
        quality_score = min(quality_score, max(0.0, float(retrieval_confidence)))
    if missing_knowledge:
        quality_score = min(quality_score, 0.48)
    if state.get("risk_level") == "high":
        quality_score = min(quality_score, 0.72)
    if has_draft_error or has_empty_draft:
        quality_score = 0.0
    quality_score = round(quality_score, 4)

    quality_label = (
        "blocked"
        if has_draft_error or has_empty_draft
        else "needs_review"
        if missing_knowledge or state.get("risk_level") == "high"
        else "review_ready"
    )

    decision_reason = (
        "Provider draft generation failed or returned no sendable reply."
        if has_draft_error or has_empty_draft
        else "Missing or weak knowledge requires supervisor review."
        if missing_knowledge
        else "High-risk conversation remains supervisor-gated."
        if state.get("risk_level") == "high"
        else "Draft is grounded enough for supervisor review."
    )

    trace_attributes = {
        "sagad.graph": "Hierarchical Support Graph v0.2.0",
        "sagad.intent": state.get("intent", "unknown"),
        "sagad.risk_level": state.get("risk_level", "medium"),
        "sagad.selected_agent": state.get("routed_agent") or "general_support",
        "sagad.retrieval_confidence": retrieval_confidence,
        "sagad.missing_knowledge": missing_knowledge,
        "sagad.approval_status": "needs_approval",
        "sagad.quality_label": quality_label,
    }

    confidence_breakdown = {
        "retrieval_confidence": retrieval_confidence,
        "knowledge_available": bool(knowledge),
        "missing_knowledge": missing_knowledge,
        "risk_level": state.get("risk_level", "medium"),
        "draft_available": not has_empty_draft,
        "provider_error": has_draft_error,
        "final_score": quality_score,
    }

    compliance_status = "blocked" if has_draft_error or has_empty_draft else "needs_review"

    return {
        "qa_findings": findings,
        "compliance_status": compliance_status,
        "approval_status": "needs_approval",
        "retrieval_diagnostic": diagnostic,
        "eval_tags": [
            str(state.get("intent", "unknown")),
            str(state.get("risk_level", "medium")),
            "missing_knowledge" if missing_knowledge else "knowledge_supported",
            quality_label,
        ],
        "trace_attributes": trace_attributes,
        "diagnostic_payload": diagnostic,
        "decision_reason": decision_reason,
        "guardrail_findings": findings,
        "confidence_breakdown": confidence_breakdown,
        "final_confidence_score": quality_score,
        "quality_score": quality_score,
        "quality_label": quality_label,
        "quality_signals": confidence_breakdown,
        "quality_notes": decision_reason,
    }


def _route_to_agent(state: AgentStudioState) -> str:
    agent = state.get("routed_agent")
    if agent == "sales_agent":
        return "run_sales_agent"
    elif agent == "refund_resolver":
        return "run_refund_resolver"
    else:
        return "run_support_agent"


def _needs_tools(state: AgentStudioState) -> str:
    """Decide whether to run tool executor or proceed to supervisor draft.

    Returns ``"run_tool_executor"`` when:
    - A sub-agent has requested a CRM tool, OR
    - The supervisor has requested an agent tool (``agent.*`` tool call)
    """
    tool_requests = state.get("tool_requests") or []

    # Check if any tool request is an agent tool (supervisor delegating to sub-agent)
    agent_tool_requested = any(
        tr.get("tool", "").startswith("agent.") for tr in tool_requests
    )
    if agent_tool_requested:
        return "run_tool_executor"

    # Check if a sub-agent has requested a CRM tool
    report = state.get("sub_agent_report") or {}
    action = report.get("recommended_action")
    if action == "REQUEST_TOOL" and tool_requests:
        return "run_tool_executor"

    return "supervisor_draft"


def build_graph() -> object:
    workflow = StateGraph(AgentStudioState)

    workflow.add_node("normalize", normalize_message)
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("classify_and_route", classify_and_route)
    workflow.add_node("retrieve", retrieve_knowledge)

    workflow.add_node("run_sales_agent", run_sales_agent)
    workflow.add_node("run_refund_resolver", run_refund_resolver)
    workflow.add_node("run_support_agent", run_support_agent)

    workflow.add_node("run_tool_executor", run_tool_executor)
    workflow.add_node("supervisor_draft", supervisor_draft)
    workflow.add_node("run_guardrail", run_guardrail)

    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "retrieve_memory")
    workflow.add_edge("retrieve_memory", "classify_and_route")
    workflow.add_edge("classify_and_route", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        _route_to_agent,
        {
            "run_sales_agent": "run_sales_agent",
            "run_refund_resolver": "run_refund_resolver",
            "run_support_agent": "run_support_agent",
        }
    )

    workflow.add_conditional_edges(
        "run_sales_agent",
        _needs_tools,
        {
            "run_tool_executor": "run_tool_executor",
            "supervisor_draft": "supervisor_draft",
        }
    )
    workflow.add_conditional_edges(
        "run_refund_resolver",
        _needs_tools,
        {
            "run_tool_executor": "run_tool_executor",
            "supervisor_draft": "supervisor_draft",
        }
    )
    workflow.add_conditional_edges(
        "run_support_agent",
        _needs_tools,
        {
            "run_tool_executor": "run_tool_executor",
            "supervisor_draft": "supervisor_draft",
        }
    )

    workflow.add_conditional_edges(
        "run_tool_executor",
        _needs_tools,
        {
            "run_tool_executor": "run_tool_executor",
            "supervisor_draft": "supervisor_draft",
        }
    )
    workflow.add_edge("supervisor_draft", "run_guardrail")
    workflow.add_edge("run_guardrail", END)

    return workflow.compile()


graph = build_graph()

