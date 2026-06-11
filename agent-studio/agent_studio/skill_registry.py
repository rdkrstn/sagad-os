"""Static registry for internal Sagad Agent Studio skills."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


SkillCategory = Literal[
    "classification",
    "routing",
    "retrieval",
    "memory",
    "tooling",
    "drafting",
    "quality",
    "policy",
    "approval",
]
SkillRiskLevel = Literal["low", "medium", "high"]

DEFAULT_SKILL_NAMES: tuple[str, ...] = (
    "classify_message",
    "route_agent",
    "retrieve_knowledge",
    "summarize_thread",
    "plan_tools",
    "draft_reply",
    "score_confidence",
    "apply_guardrails",
    "create_approval_item",
)
INTERNAL_AGENT_NAMES: tuple[str, ...] = (
    "agent_studio",
    "general_support",
    "sales_agent",
    "refund_resolver",
    "support",
    "sales",
)
_ALL_INTERNAL_AGENTS = INTERNAL_AGENT_NAMES
_GRAPH_STAGE_SKILLS: dict[str, tuple[str, ...]] = {
    "classify": ("classify_message",),
    "select_agent": ("route_agent",),
    "retrieve_memory": ("summarize_thread",),
    "retrieve": ("retrieve_knowledge",),
    "tool_planning": ("plan_tools",),
    "plan_tools": ("plan_tools",),
    "draft": ("draft_reply",),
    "qa_compliance": (
        "score_confidence",
        "apply_guardrails",
        "create_approval_item",
    ),
    "approval": ("create_approval_item",),
}


class SkillDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    category: SkillCategory
    allowed_agents: tuple[str, ...]
    requires_model: bool = False
    requires_tools: bool = False
    risk_level: SkillRiskLevel = "low"


def default_skills() -> tuple[SkillDefinition, ...]:
    return (
        SkillDefinition(
            name="classify_message",
            description="Classify the normalized customer message into intent and risk.",
            category="classification",
            allowed_agents=("agent_studio",),
            requires_model=False,
            requires_tools=False,
            risk_level="low",
        ),
        SkillDefinition(
            name="route_agent",
            description="Select the internal Sagad agent profile for the conversation.",
            category="routing",
            allowed_agents=("agent_studio",),
            requires_model=False,
            requires_tools=False,
            risk_level="low",
        ),
        SkillDefinition(
            name="retrieve_knowledge",
            description="Build an approved Sagad knowledge source pack for the draft.",
            category="retrieval",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=False,
            requires_tools=True,
            risk_level="medium",
        ),
        SkillDefinition(
            name="summarize_thread",
            description="Summarize relevant thread history and durable memory.",
            category="memory",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=True,
            requires_tools=False,
            risk_level="medium",
        ),
        SkillDefinition(
            name="plan_tools",
            description="Prepare provider-agnostic tool intent for later policy review.",
            category="tooling",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=False,
            requires_tools=True,
            risk_level="medium",
        ),
        SkillDefinition(
            name="draft_reply",
            description="Draft a grounded customer reply from approved Sagad context.",
            category="drafting",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=True,
            requires_tools=False,
            risk_level="medium",
        ),
        SkillDefinition(
            name="score_confidence",
            description="Score retrieval, policy, and draft confidence for review routing.",
            category="quality",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=False,
            requires_tools=False,
            risk_level="low",
        ),
        SkillDefinition(
            name="apply_guardrails",
            description="Apply deterministic policy and handoff checks before delivery.",
            category="policy",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=False,
            requires_tools=False,
            risk_level="high",
        ),
        SkillDefinition(
            name="create_approval_item",
            description="Create or update the internal supervisor approval item.",
            category="approval",
            allowed_agents=_ALL_INTERNAL_AGENTS,
            requires_model=False,
            requires_tools=False,
            risk_level="medium",
        ),
    )


class SkillRegistry:
    def __init__(self, skills: tuple[SkillDefinition, ...] | None = None) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        for skill in skills or default_skills():
            self.register(skill)

    def register(self, skill: SkillDefinition) -> None:
        if not skill.name:
            raise ValueError("Skill name is required.")
        unknown_agents = set(skill.allowed_agents).difference(INTERNAL_AGENT_NAMES)
        if unknown_agents:
            raise ValueError(
                f"Unknown internal agents for skill {skill.name}: {sorted(unknown_agents)}"
            )
        self._skills[skill.name] = skill

    def list_skills(self) -> tuple[SkillDefinition, ...]:
        return tuple(self._skills[name] for name in DEFAULT_SKILL_NAMES)

    def list_for_agent(self, agent: str) -> tuple[SkillDefinition, ...]:
        return tuple(
            skill for skill in self.list_skills() if agent in skill.allowed_agents
        )

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def get_skill(self, name: str) -> SkillDefinition | None:
        return self.get(name)

    def require(self, name: str, *, agent: str) -> SkillDefinition:
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"Unknown skill: {name}")
        if agent not in skill.allowed_agents:
            raise PermissionError(f"Agent '{agent}' cannot use skill '{name}'.")
        return skill

    def skills_for_graph_stage(self, stage: str) -> tuple[SkillDefinition, ...]:
        return tuple(
            self._skills[name]
            for name in _GRAPH_STAGE_SKILLS.get(stage, ())
            if name in self._skills
        )

    def skills_for_stages(self, stages: list[str]) -> list[str]:
        selected: list[str] = []
        for stage in stages:
            for skill in self.skills_for_graph_stage(stage):
                if skill.name not in selected:
                    selected.append(skill.name)
        return selected

    def diagnose_skill_lookup(self, name: str) -> dict[str, object]:
        skill = self.get(name)
        if skill is None:
            return {
                "name": name,
                "allowed": False,
                "reason": "unknown_skill",
                "skill": None,
            }
        return {
            "name": name,
            "allowed": True,
            "reason": None,
            "skill": skill.model_dump(mode="json"),
        }

    def diagnose_graph_stage(self, stage: str) -> dict[str, object]:
        if stage not in _GRAPH_STAGE_SKILLS:
            return {
                "stage": stage,
                "allowed": False,
                "reason": "unknown_stage",
                "skills": [],
            }
        return {
            "stage": stage,
            "allowed": True,
            "reason": None,
            "skills": [
                skill.model_dump(mode="json")
                for skill in self.skills_for_graph_stage(stage)
            ],
        }

    def graph_diagnostic(
        self,
        *,
        selected_agent: str,
        completed_stages: list[str],
    ) -> dict[str, object]:
        return {
            "selected_agent": selected_agent,
            "selected_skills": self.skills_for_stages(completed_stages),
            "available_skills": [skill.name for skill in self.list_skills()],
        }


skill_registry = SkillRegistry()


def list_internal_agent_names() -> tuple[str, ...]:
    return INTERNAL_AGENT_NAMES


def list_skill_definitions() -> tuple[SkillDefinition, ...]:
    return skill_registry.list_skills()


def get_skill_definition(name: str) -> SkillDefinition | None:
    return skill_registry.get(name)


def diagnose_skill_lookup(name: str) -> dict[str, object]:
    return skill_registry.diagnose_skill_lookup(name)


def skills_for_graph_stage(stage: str) -> tuple[SkillDefinition, ...]:
    return skill_registry.skills_for_graph_stage(stage)


def diagnose_graph_stage(stage: str) -> dict[str, object]:
    return skill_registry.diagnose_graph_stage(stage)
