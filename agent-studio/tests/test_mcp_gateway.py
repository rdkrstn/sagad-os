from agent_studio.mcp_gateway import build_mcp_descriptors
from agent_studio.tool_manifests import ToolManifest, ToolManifestRegistry


def test_mcp_descriptors_are_descriptor_only_and_redacted() -> None:
    descriptors = build_mcp_descriptors(ToolManifestRegistry().list_manifests())

    assert descriptors
    rendered = str([descriptor.model_dump() for descriptor in descriptors]).lower()
    assert "api_key" not in rendered
    assert "token" not in rendered
    assert "base_url" not in rendered
    assert "execute" not in rendered


def test_mcp_descriptors_expose_only_enabled_policy_wrapped_tools() -> None:
    descriptors = build_mcp_descriptors(ToolManifestRegistry().list_manifests())

    assert {descriptor.name for descriptor in descriptors} == {
        "knowledge.search",
        "crm.lookup_contact",
        "crm.create_note",
        "crm.create_task",
        "crm.update_lead_stage",
        "chatwoot.messages.send_approved",
        "chatwoot.conversations.resolve",
        "ghl.messages.send_approved",
    }
    for descriptor in descriptors:
        assert descriptor.enabled is True
        assert descriptor.policy_wrapped is True
        assert descriptor.input_schema
        if descriptor.mode == "write":
            assert descriptor.requires_approval is True


def _manifest(
    tool_name: str,
    *,
    provider: str = "Twenty CRM",
    enabled: bool = True,
    input_schema: dict[str, object] | None = None,
    mode: str = "read",
    requires_approval: bool = False,
    risk_level: str = "medium",
) -> ToolManifest:
    return ToolManifest(
        tool_name=tool_name,
        provider=provider,
        skill_name="plan_tools",
        mode=mode,
        risk_level=risk_level,
        allowed_agents=["Support Agent"],
        requires_approval=requires_approval,
        enabled=enabled,
        dry_run_default=True,
        description="Use provider records at https://tenant.example.test.",
        input_schema=(
            input_schema
            if input_schema is not None
            else {"type": "object", "properties": {"query": {"type": "string"}}}
        ),
    )


def test_mcp_descriptors_remove_sensitive_fields_and_execution_surfaces() -> None:
    descriptors = build_mcp_descriptors(
        [
            _manifest(
                "crm.lookup_contact",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "api_key": {"type": "string"},
                        "base_url": {"type": "string"},
                        "headers": {"type": "object"},
                    },
                    "required": ["query", "api_key", "base_url"],
                },
            )
        ]
    )

    assert len(descriptors) == 1
    dumped = descriptors[0].model_dump()
    assert set(dumped) == {
        "name",
        "description",
        "provider",
        "skill_name",
        "allowed_agents",
        "allowed_skills",
        "mode",
        "risk_level",
        "requires_approval",
        "dry_run_default",
        "enabled",
        "input_schema",
        "policy_reasons",
        "policy_wrapped",
    }
    assert dumped["allowed_agents"] == ["Support Agent"]
    assert dumped["allowed_skills"] == ["plan_tools"]
    assert dumped["policy_wrapped"] is True
    assert set(dumped["input_schema"]["properties"]) == {"query"}
    assert dumped["input_schema"]["required"] == ["query"]

    rendered = str(dumped).lower()
    assert "api_key" not in rendered
    assert "base_url" not in rendered
    assert "headers" not in rendered
    assert "https://" not in rendered
    assert "execute" not in rendered
    assert "handler" not in rendered


def test_mcp_descriptors_filter_disabled_schema_less_and_shell_filesystem_tools() -> None:
    descriptors = build_mcp_descriptors(
        [
            _manifest("knowledge.search", provider="Sagad Knowledge", risk_level="low"),
            _manifest("crm.create_note", enabled=False),
            _manifest("crm.lookup_missing_schema", input_schema={}),
            _manifest("shell.run_command", provider="shell", mode="write", requires_approval=True, risk_level="high"),
            _manifest("filesystem.read_file", provider="filesystem", requires_approval=True, risk_level="high"),
        ]
    )

    assert [descriptor.name for descriptor in descriptors] == ["knowledge.search"]
