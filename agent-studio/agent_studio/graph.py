from langgraph.graph import END, START, StateGraph

from agent_studio.retrieval import retriever
from agent_studio.schemas import QaFinding
from agent_studio.state import AgentStudioState


def normalize_message(state: AgentStudioState) -> dict[str, str]:
    message = state["incoming_message"].strip()
    return {"normalized_message": " ".join(message.split())}


def classify_message(state: AgentStudioState) -> dict[str, str]:
    message = state["normalized_message"].lower()

    if any(term in message for term in ["refund", "cancel", "angry", "complaint"]):
        return {"intent": "refund_or_cancellation", "risk_level": "high"}
    if any(term in message for term in ["price", "pricing", "quote", "cost"]):
        return {"intent": "pricing_lead", "risk_level": "low"}
    if any(term in message for term in ["appointment", "schedule", "book", "reschedule"]):
        return {"intent": "booking_or_support", "risk_level": "medium"}
    if len(message.split()) <= 2:
        return {"intent": "discovery", "risk_level": "medium"}
    return {"intent": "general_support", "risk_level": "medium"}


def retrieve_knowledge(state: AgentStudioState) -> dict[str, object]:
    hits = retriever.search(
        state["normalized_message"],
        intent=state["intent"],
        risk_level=state["risk_level"],
    )
    return {"retrieved_knowledge": hits}


def draft_reply(state: AgentStudioState) -> dict[str, str]:
    intent = state["intent"]
    knowledge = state.get("retrieved_knowledge", [])
    citation_titles = ", ".join(hit.title for hit in knowledge[:2])

    if intent == "pricing_lead":
        body = (
            "Thanks for reaching out. I can help with pricing, but I need one "
            "detail first: what service do you need and what city are you in?"
        )
    elif intent == "refund_or_cancellation":
        body = (
            "I understand. I am going to bring this to a supervisor so we can "
            "review the cancellation or refund request before promising an outcome."
        )
    elif intent == "booking_or_support":
        body = (
            "I can help with that. Before I discuss account or appointment details, "
            "please confirm the phone number or ZIP code on the booking."
        )
    elif intent == "discovery":
        body = "Hi. What can we help with today: HVAC, plumbing, electrical, cleaning, or something else?"
    else:
        body = "Thanks. I can help route this to the right team. Can you share a little more detail?"

    if citation_titles:
        body = f"{body}\n\nBasis: {citation_titles}."

    return {"draft_reply": body}


def run_qa_compliance(state: AgentStudioState) -> dict[str, object]:
    findings = [
        QaFinding(
            label="Knowledge basis",
            status="pass" if state.get("retrieved_knowledge") else "watch",
            detail="Draft includes retrieved KB/SOP context." if state.get("retrieved_knowledge") else "No matching knowledge was retrieved.",
        ),
        QaFinding(
            label="HITL policy",
            status="pass",
            detail="Live Chatwoot replies require supervisor approval.",
        ),
    ]

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
        "compliance_status": "needs_review",
        "approval_status": "needs_approval",
    }


def build_graph() -> object:
    workflow = StateGraph(AgentStudioState)
    workflow.add_node("normalize", normalize_message)
    workflow.add_node("classify", classify_message)
    workflow.add_node("retrieve", retrieve_knowledge)
    workflow.add_node("draft", draft_reply)
    workflow.add_node("qa_compliance", run_qa_compliance)
    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "classify")
    workflow.add_edge("classify", "retrieve")
    workflow.add_edge("retrieve", "draft")
    workflow.add_edge("draft", "qa_compliance")
    workflow.add_edge("qa_compliance", END)
    return workflow.compile()


graph = build_graph()
