from collections.abc import Mapping
from datetime import datetime

import httpx

from agent_studio.config import Settings
from agent_studio.schemas import (
    CrmContactContext,
    CrmProviderStatus,
    ToolPlan,
    ToolRiskLevel,
    ToolResult,
)


def twenty_status(settings: Settings) -> CrmProviderStatus:
    if not settings.twenty_enabled:
        return CrmProviderStatus(
            status="disabled",
            base_url=settings.twenty_base_url,
            mode=settings.twenty_api_mode,
            dry_run=settings.twenty_dry_run,
            writes_enabled=False,
            detail="Twenty CRM is external and currently disabled for Agent Studio.",
        )

    if not settings.twenty_configured:
        return CrmProviderStatus(
            status="unconfigured",
            base_url=settings.twenty_base_url,
            mode=settings.twenty_api_mode,
            dry_run=settings.twenty_dry_run,
            writes_enabled=False,
            detail="Set TWENTY_BASE_URL and TWENTY_API_KEY in Agent Studio.",
        )

    if settings.twenty_dry_run:
        return CrmProviderStatus(
            status="dry_run",
            base_url=settings.twenty_base_url,
            mode=settings.twenty_api_mode,
            dry_run=True,
            writes_enabled=False,
            detail="Twenty is configured, but write calls are dry-run only.",
        )

    return CrmProviderStatus(
        status="ready",
        base_url=settings.twenty_base_url,
        mode=settings.twenty_api_mode,
        dry_run=False,
        writes_enabled=settings.twenty_allow_writes,
        detail="Twenty CRM is configured as an external provider.",
    )


class TwentyAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _plan(
        self,
        tool_name: str,
        action: str,
        args: dict[str, object],
        *,
        requires_approval: bool,
        approved: bool,
        risk_level: ToolRiskLevel = "medium",
    ) -> ToolPlan:
        return ToolPlan(
            tool_name=tool_name,
            action=action,
            args=args,
            requires_approval=requires_approval,
            approved=approved,
            dry_run=self.settings.twenty_dry_run,
            risk_level=risk_level,
        )

    def _blocked_result(self, plan: ToolPlan, detail: str) -> ToolResult:
        return ToolResult(
            plan_id=plan.id,
            tool_name=plan.tool_name,
            status="blocked",
            detail=detail,
        )

    def _dry_run_result(self, plan: ToolPlan, detail: str) -> ToolResult:
        return ToolResult(
            plan_id=plan.id,
            tool_name=plan.tool_name,
            status="dry_run",
            detail=detail,
            data={"args": plan.args},
        )

    def _graphql_url(self) -> str:
        base_url = (self.settings.twenty_base_url or "").rstrip("/")
        return f"{base_url}/graphql"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.twenty_api_key}",
            "Content-Type": "application/json",
        }

    async def lookup_contact(
        self,
        query: str,
        conversation_id: str | None = None,
    ) -> tuple[CrmContactContext | None, ToolPlan, ToolResult]:
        plan = self._plan(
            "crm.lookup_contact",
            "Lookup contact in external Twenty CRM.",
            {"query": query, "conversation_id": conversation_id},
            requires_approval=False,
            approved=True,
            risk_level="low",
        )

        if not self.settings.twenty_reads_enabled:
            return (
                None,
                plan,
                self._blocked_result(
                    plan,
                    "Twenty lookup is unavailable until TWENTY_ENABLED, TWENTY_BASE_URL, and TWENTY_API_KEY are configured.",
                ),
            )

        graphql_query = """
        query SagadContactLookup($query: String!) {
          people(filter: { or: [
            { name: { ilike: $query } },
            { emails: { primaryEmail: { ilike: $query } } },
            { phones: { primaryPhoneNumber: { ilike: $query } } }
          ] }, first: 1) {
            edges { node { id name emails phones company { name } tags } }
          }
        }
        """
        payload = {"query": graphql_query, "variables": {"query": f"%{query}%"}}

        async with httpx.AsyncClient(timeout=self.settings.twenty_timeout_seconds) as client:
            response = await client.post(
                self._graphql_url(),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()

        context = self._contact_from_payload(response.json())
        return (
            context,
            plan,
            ToolResult(
                plan_id=plan.id,
                tool_name=plan.tool_name,
                status="succeeded",
                detail="Twenty contact lookup completed.",
                data={"contact_id": context.contact_id if context else None},
            ),
        )

    async def create_note(
        self,
        contact_id: str,
        note: str,
        *,
        conversation_id: str | None,
        approved: bool,
    ) -> tuple[ToolPlan, ToolResult]:
        return await self._write_tool(
            tool_name="crm.create_note",
            action="Create a note in external Twenty CRM.",
            args={
                "contact_id": contact_id,
                "note": note,
                "conversation_id": conversation_id,
            },
            approved=approved,
            mutation="""
            mutation SagadCreateNote($contactId: ID!, $body: String!) {
              createNote(data: { targetableId: $contactId, body: $body }) { id }
            }
            """,
            variables={"contactId": contact_id, "body": note},
        )

    async def create_task(
        self,
        contact_id: str,
        title: str,
        *,
        due_at: datetime | None,
        owner_id: str | None,
        conversation_id: str | None,
        approved: bool,
    ) -> tuple[ToolPlan, ToolResult]:
        return await self._write_tool(
            tool_name="crm.create_task",
            action="Create a task in external Twenty CRM.",
            args={
                "contact_id": contact_id,
                "title": title,
                "due_at": due_at.isoformat() if due_at else None,
                "owner_id": owner_id,
                "conversation_id": conversation_id,
            },
            approved=approved,
            mutation="""
            mutation SagadCreateTask($contactId: ID!, $title: String!) {
              createTask(data: { targetableId: $contactId, title: $title }) { id }
            }
            """,
            variables={"contactId": contact_id, "title": title},
        )

    async def update_lead_stage(
        self,
        contact_id: str,
        lead_stage: str,
        *,
        conversation_id: str | None,
        approved: bool,
    ) -> tuple[ToolPlan, ToolResult]:
        return await self._write_tool(
            tool_name="crm.update_lead_stage",
            action="Update lead stage in external Twenty CRM.",
            args={
                "contact_id": contact_id,
                "lead_stage": lead_stage,
                "conversation_id": conversation_id,
            },
            approved=approved,
            mutation="""
            mutation SagadUpdateLeadStage($contactId: ID!, $leadStage: String!) {
              updatePerson(id: $contactId, data: { leadStage: $leadStage }) { id }
            }
            """,
            variables={"contactId": contact_id, "leadStage": lead_stage},
            risk_level="high",
        )

    async def _write_tool(
        self,
        *,
        tool_name: str,
        action: str,
        args: dict[str, object],
        approved: bool,
        mutation: str,
        variables: dict[str, object],
        risk_level: ToolRiskLevel = "medium",
    ) -> tuple[ToolPlan, ToolResult]:
        plan = self._plan(
            tool_name,
            action,
            args,
            requires_approval=True,
            approved=approved,
            risk_level=risk_level,
        )

        if not self.settings.twenty_enabled:
            return plan, self._blocked_result(plan, "Twenty CRM is disabled.")

        if not self.settings.twenty_configured:
            return plan, self._blocked_result(plan, "Twenty CRM is not configured.")

        if self.settings.twenty_dry_run:
            return plan, self._dry_run_result(
                plan,
                "Twenty write was dry-run only; no external request was sent.",
            )

        if not self.settings.twenty_allow_writes:
            return plan, self._blocked_result(
                plan,
                "TWENTY_ALLOW_WRITES must be true before live CRM mutations.",
            )

        payload = {"query": mutation, "variables": variables}
        async with httpx.AsyncClient(timeout=self.settings.twenty_timeout_seconds) as client:
            response = await client.post(
                self._graphql_url(),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()

        return (
            plan,
            ToolResult(
                plan_id=plan.id,
                tool_name=tool_name,
                status="succeeded",
                detail="Twenty write completed.",
                data=response.json(),
            ),
        )

    def _contact_from_payload(self, payload: object) -> CrmContactContext | None:
        record = self._first_contact_record(payload)
        if record is None:
            return CrmContactContext(status="ready", raw={"result": "not_found"})

        company = record.get("company")
        company_name = company.get("name") if isinstance(company, Mapping) else None

        return CrmContactContext(
            status="ready",
            contact_id=self._text(record, "id"),
            display_name=self._text(record, "name"),
            company_name=company_name if isinstance(company_name, str) else None,
            phone_masked=self._masked_phone(record.get("phones")),
            email_masked=self._masked_email(record.get("emails")),
            tags=self._tags(record.get("tags")),
            raw=dict(record),
        )

    def _first_contact_record(self, payload: object) -> Mapping[str, object] | None:
        if not isinstance(payload, Mapping):
            return None
        data = payload.get("data")
        if not isinstance(data, Mapping):
            return None
        people = data.get("people")
        if not isinstance(people, Mapping):
            return None
        edges = people.get("edges")
        if not isinstance(edges, list) or not edges:
            return None
        first = edges[0]
        if not isinstance(first, Mapping):
            return None
        node = first.get("node")
        return node if isinstance(node, Mapping) else None

    def _text(self, record: Mapping[str, object], key: str) -> str | None:
        value = record.get(key)
        return value if isinstance(value, str) else None

    def _masked_email(self, value: object) -> str | None:
        if isinstance(value, Mapping):
            primary = value.get("primaryEmail")
            if isinstance(primary, str):
                return self._mask_email(primary)
        if isinstance(value, str):
            return self._mask_email(value)
        return None

    def _mask_email(self, email: str) -> str:
        local, _, domain = email.partition("@")
        if not domain:
            return "***"
        prefix = local[:2] if len(local) > 1 else local[:1]
        return f"{prefix}***@{domain}"

    def _masked_phone(self, value: object) -> str | None:
        if isinstance(value, Mapping):
            primary = value.get("primaryPhoneNumber")
            if isinstance(primary, str):
                return self._mask_phone(primary)
        if isinstance(value, str):
            return self._mask_phone(value)
        return None

    def _mask_phone(self, phone: str) -> str:
        digits = "".join(character for character in phone if character.isdigit())
        suffix = digits[-4:] if len(digits) >= 4 else "****"
        return f"*** *** {suffix}"

    def _tags(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
