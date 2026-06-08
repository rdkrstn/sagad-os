import os

import litellm
from langgraph.graph import END, START, StateGraph

from agent_studio.agents import AgentRegistry
from agent_studio.memory_workflow import build_memory_pack
from agent_studio.retrieval import retriever
from agent_studio.schemas import ConversationMessageRecord, KnowledgeHit, MemoryHit, QaFinding
from agent_studio.state import AgentStudioState

try:
    from agent_studio.retrieval_workflow import build_query_plan, build_retrieval_pack
except ImportError as exc:
    build_query_plan = None
    build_retrieval_pack = None
    RETRIEVAL_WORKFLOW_IMPORT_ERROR: str | None = str(exc)
else:
    RETRIEVAL_WORKFLOW_IMPORT_ERROR = None


registry = AgentRegistry()

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
        hits = retriever.search(
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
        hits = retriever.search(
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


def draft_reply(state: AgentStudioState) -> dict[str, object]:
    intent = state["intent"]
    knowledge = state.get("retrieved_knowledge", [])
    memory = state.get("memory_context", [])
    citation_titles = ", ".join(hit.title for hit in knowledge[:4])

    agent = _resolve_markdown_agent(intent, state.get("selected_agent"))
    system_prompt = agent.system_prompt if agent else "You are a helpful assistant."
    if memory:
        memory_context = "\n".join(
            [
                f"- {hit.memory_type} ({hit.source}, score {hit.score:.2f}): {hit.content}"
                for hit in memory
            ],
        )
        system_prompt += (
            "\n\nConversation Memory:\n"
            f"{memory_context}\n"
            "Use conversation memory only for customer/thread context. "
            "Do not treat it as approved policy or override the selected source pack."
        )
    if knowledge:
        knowledge_context = "\n".join(
            [
                f"- {hit.title} ({hit.category}, score {hit.score:.2f}): {hit.excerpt}"
                for hit in knowledge
            ],
        )
        system_prompt += f"\n\nSelected Source Pack:\n{knowledge_context}"
    if state.get("missing_knowledge"):
        system_prompt += (
            "\n\nThe selected sources may be insufficient. Do not invent policy details; "
            "ask for supervisor review or more context when the source pack cannot support the answer."
        )

    tools = []
    if agent:
        for tool_name in agent.allowed_tools:
            if tool_name in TOOL_SCHEMAS:
                tools.append(TOOL_SCHEMAS[tool_name])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["normalized_message"]},
    ]

    try:
        response = litellm.completion(
            model=os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
            messages=messages,
            tools=tools if tools else None,
        )
        response_message = response.choices[0].message
        body = response_message.content
        tool_calls = getattr(response_message, "tool_calls", None)
        if not body and tool_calls:
            body = f"I am checking my tools to assist you: {tool_calls[0].function.name}"
    except Exception as exc:
        body = f"An error occurred: {str(exc)}"
        diagnostic = dict(state.get("retrieval_diagnostic", {}) or {})
        diagnostic["draft_error"] = str(exc)
        return {"draft_reply": body, "retrieval_diagnostic": diagnostic}

    if citation_titles:
        body = f"{body}\n\nBasis: {citation_titles}."

    return {"draft_reply": body}


def run_qa_compliance(state: AgentStudioState) -> dict[str, object]:
    knowledge = state.get("retrieved_knowledge", [])
    memory = state.get("memory_context", [])
    missing_knowledge = bool(state.get("missing_knowledge", not knowledge))
    retrieval_confidence = state.get("retrieval_confidence")
    draft = state.get("draft_reply", "")
    has_draft_error = draft.startswith("An error occurred:")
    has_empty_draft = not draft.strip()

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

    findings = [
        QaFinding(
            label="Knowledge basis",
            status=knowledge_status,
            detail=knowledge_detail,
        ),
        QaFinding(
            label="HITL policy",
            status="pass",
            detail="Live Chatwoot replies require supervisor approval.",
        ),
    ]

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

    if state["risk_level"] == "high":
        findings.append(
            QaFinding(
                label="High-risk escalation",
                status="watch",
                detail="Refund, cancellation, and complaint language must remain supervisor-gated.",
            ),
        )

    return {
        "qa_findings": findings,
        "compliance_status": "blocked" if has_draft_error or has_empty_draft else "needs_review",
        "approval_status": "needs_approval",
    }


def build_graph() -> object:
    workflow = StateGraph(AgentStudioState)
    workflow.add_node("normalize", normalize_message)
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("classify", classify_message)
    workflow.add_node("select_agent", select_markdown_agent)
    workflow.add_node("retrieve", retrieve_knowledge)
    workflow.add_node("draft", draft_reply)
    workflow.add_node("qa_compliance", run_qa_compliance)
    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "retrieve_memory")
    workflow.add_edge("retrieve_memory", "classify")
    workflow.add_edge("classify", "select_agent")
    workflow.add_edge("select_agent", "retrieve")
    workflow.add_edge("retrieve", "draft")
    workflow.add_edge("draft", "qa_compliance")
    workflow.add_edge("qa_compliance", END)
    return workflow.compile()


graph = build_graph()
