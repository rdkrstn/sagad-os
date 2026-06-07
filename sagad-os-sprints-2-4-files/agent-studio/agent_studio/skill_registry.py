"""Internal skill registry for Sagad OS agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SkillCategory = Literal["classification", "retrieval", "drafting", "policy", "tooling", "delivery", "review"]
SkillRiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    category: SkillCategory
    allowed_agents: list[str]
    requires_model: bool = False
    requires_tools: bool = False
    risk_level: SkillRiskLevel = "low"


class SkillRegistry:
    def __init__(self, skills: list[SkillDefinition] | None = None) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        for skill in skills or default_skills():
            self.register(skill)

    def register(self, skill: SkillDefinition) -> None:
        if not skill.name:
            raise ValueError("Skill name is required.")
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def list_for_agent(self, agent: str) -> list[SkillDefinition]:
        return [skill for skill in self._skills.values() if agent in skill.allowed_agents]

    def require(self, name: str, *, agent: str) -> SkillDefinition:
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"Unknown skill: {name}")
        if agent not in skill.allowed_agents:
            raise PermissionError(f"Agent '{agent}' cannot use skill '{name}'.")
        return skill



def default_skills() -> list[SkillDefinition]:
    return [
        SkillDefinition(
            name="classify_message",
            description="Classify intent, driver, urgency, and risk.",
            category="classification",
            allowed_agents=["sales", "support"],
            requires_model=False,
        ),
        SkillDefinition(
            name="route_agent",
            description="Route the conversation to Sales or Support.",
            category="classification",
            allowed_agents=["sales", "support"],
            requires_model=False,
        ),
        SkillDefinition(
            name="retrieve_knowledge",
            description="Retrieve approved knowledge sources.",
            category="retrieval",
            allowed_agents=["sales", "support"],
            requires_tools=True,
        ),
        SkillDefinition(
            name="summarize_thread",
            description="Summarize relevant conversation history.",
            category="retrieval",
            allowed_agents=["sales", "support"],
            requires_model=True,
        ),
        SkillDefinition(
            name="plan_tools",
            description="Plan server-side tools needed for this conversation.",
            category="tooling",
            allowed_agents=["sales", "support"],
            requires_tools=True,
            risk_level="medium",
        ),
        SkillDefinition(
            name="draft_reply",
            description="Draft a grounded response from approved context.",
            category="drafting",
            allowed_agents=["sales", "support"],
            requires_model=True,
        ),
        SkillDefinition(
            name="score_confidence",
            description="Score operational confidence using weighted rubric.",
            category="policy",
            allowed_agents=["sales", "support"],
        ),
        SkillDefinition(
            name="apply_guardrails",
            description="Apply deterministic delivery guardrails.",
            category="policy",
            allowed_agents=["sales", "support"],
        ),
        SkillDefinition(
            name="create_approval_item",
            description="Create or update supervisor approval queue item.",
            category="review",
            allowed_agents=["sales", "support"],
            risk_level="medium",
        ),
        SkillDefinition(
            name="send_approved_reply",
            description="Send only supervisor-approved replies.",
            category="delivery",
            allowed_agents=["sales", "support"],
            requires_tools=True,
            risk_level="high",
        ),
    ]


skill_registry = SkillRegistry()
