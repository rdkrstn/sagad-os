from collections.abc import Callable, Iterable, Mapping
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_studio.schemas import ToolRiskLevel

try:
    from agent_studio.tool_manifests import ToolManifestRegistry
except ImportError:
    ToolManifestRegistry = None


ToolMode = Literal["read", "write", "dry_run"]
PolicyEvaluator = Callable[[object], object]

DESCRIPTOR_ONLY_POLICY_REASONS = [
    "Descriptor only; execution remains behind Agent Studio policy.",
    "No provider credentials or URLs are exposed.",
]

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer|secret|password|base[_ -]?url|provider[_ -]?url)\b",
    re.IGNORECASE,
)
_SENSITIVE_SCHEMA_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "bearer",
    "secret",
    "password",
    "credentials",
    "credential",
    "authorization",
    "auth",
    "headers",
    "header",
    "cookie",
    "cookies",
    "base_url",
    "provider_url",
    "url",
    "endpoint",
    "host",
}
_FORBIDDEN_TOOL_TERMS = {
    "shell",
    "filesystem",
    "file_system",
    "browser",
    "terminal",
    "powershell",
    "bash",
    "cmd",
    "command",
}
_FORBIDDEN_TOOL_PHRASES = {
    "run_command",
    "execute_command",
    "exec_command",
    "read_file",
    "write_file",
    "delete_file",
}


class McpToolDescriptor(BaseModel):
    name: str
    description: str
    provider: str
    skill_name: str
    mode: ToolMode
    risk_level: ToolRiskLevel
    requires_approval: bool
    dry_run_default: bool
    enabled: bool
    input_schema: dict[str, object] = Field(default_factory=dict)
    policy_reasons: list[str] = Field(default_factory=list)

    @property
    def policy_wrapped(self) -> bool:
        return True


def build_mcp_descriptors(
    manifests: Iterable[object] | None = None,
    *,
    policy_evaluator: PolicyEvaluator | None = None,
) -> list[McpToolDescriptor]:
    """Build descriptor-only MCP facade metadata from Agent Studio manifests."""
    manifest_source = list(manifests) if manifests is not None else _default_manifests()
    descriptors: list[McpToolDescriptor] = []
    for manifest in manifest_source:
        if not _field_bool(manifest, "enabled", False):
            continue
        if _is_forbidden_tool(manifest):
            continue

        input_schema = _field(manifest, "input_schema", {})
        if not _schema_defined(input_schema):
            continue

        policy_metadata = _policy_metadata(manifest, policy_evaluator)
        if policy_metadata is None:
            continue

        redacted_schema = _redact_schema(input_schema)
        if not _schema_defined(redacted_schema):
            continue
        if "properties" in redacted_schema and not redacted_schema.get("properties"):
            continue

        name = str(_field(manifest, "name", _field(manifest, "tool_name", "")))
        if not name:
            continue

        descriptors.append(
            McpToolDescriptor(
                name=name,
                description=_redact_text(str(_field(manifest, "description", ""))),
                provider=str(_field(manifest, "provider", "")),
                skill_name=str(_field(manifest, "skill_name", "")),
                mode=str(_field(manifest, "mode", "dry_run")),  # type: ignore[arg-type]
                risk_level=str(_field(manifest, "risk_level", "medium")),  # type: ignore[arg-type]
                requires_approval=policy_metadata["requires_approval"],
                dry_run_default=policy_metadata["dry_run_default"],
                enabled=True,
                input_schema=redacted_schema,
                policy_reasons=policy_metadata["policy_reasons"],
            ),
        )
    return descriptors


def list_mcp_tool_descriptors(
    manifests: Iterable[object] | None = None,
    *,
    policy_evaluator: PolicyEvaluator | None = None,
) -> list[dict[str, object]]:
    return [
        descriptor.model_dump()
        for descriptor in build_mcp_descriptors(
            manifests,
            policy_evaluator=policy_evaluator,
        )
    ]


def _default_manifests() -> list[object]:
    if ToolManifestRegistry is None:
        return []
    return list(ToolManifestRegistry().list_manifests())


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _field_bool(value: object, name: str, default: bool) -> bool:
    return bool(_field(value, name, default))


def _field_list(value: object, name: str) -> list[object]:
    found = _field(value, name, [])
    if found is None:
        return []
    if isinstance(found, str):
        return [found]
    return list(found)


def _schema_defined(schema: object) -> bool:
    return isinstance(schema, Mapping) and bool(schema)


def _policy_metadata(
    manifest: object,
    policy_evaluator: PolicyEvaluator | None,
) -> dict[str, Any] | None:
    manifest_requires_approval = _field_bool(manifest, "requires_approval", True)
    manifest_dry_run_default = _field_bool(manifest, "dry_run_default", True)
    if policy_evaluator is None:
        return {
            "requires_approval": manifest_requires_approval,
            "dry_run_default": manifest_dry_run_default,
            "policy_reasons": list(DESCRIPTOR_ONLY_POLICY_REASONS),
        }

    decision = policy_evaluator(manifest)
    if not _field_bool(decision, "allowed", False):
        return None

    policy_reasons = [str(reason) for reason in _field_list(decision, "policy_reasons")]
    if not policy_reasons:
        return None

    return {
        "requires_approval": _field_bool(
            decision,
            "requires_approval",
            manifest_requires_approval,
        ),
        "dry_run_default": _field_bool(decision, "dry_run", manifest_dry_run_default),
        "policy_reasons": policy_reasons,
    }


def _is_forbidden_tool(manifest: object) -> bool:
    fragments = [
        str(_field(manifest, "name", _field(manifest, "tool_name", ""))),
        str(_field(manifest, "provider", "")),
        str(_field(manifest, "skill_name", "")),
    ]
    text = " ".join(fragments).lower()
    if any(phrase in text for phrase in _FORBIDDEN_TOOL_PHRASES):
        return True

    terms = set(re.split(r"[\s._:/\\-]+", text))
    return any(term in terms for term in _FORBIDDEN_TOOL_TERMS)


def _redact_schema(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for key, nested in value.items():
            key_text = str(key)
            if _sensitive_key(key_text):
                continue
            if key_text == "properties" and isinstance(nested, Mapping):
                redacted[key_text] = {
                    str(prop_name): _redact_schema(prop_schema)
                    for prop_name, prop_schema in nested.items()
                    if not _sensitive_key(str(prop_name))
                }
                continue
            if key_text == "required" and isinstance(nested, list):
                redacted[key_text] = [
                    item
                    for item in nested
                    if isinstance(item, str) and not _sensitive_key(item)
                ]
                continue
            redacted[key_text] = _redact_schema(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_schema(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    without_urls = _URL_PATTERN.sub("[redacted]", value)
    return _SENSITIVE_TEXT_PATTERN.sub("[redacted]", without_urls)


def _sensitive_key(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    compact = normalized.replace("_", "")
    if normalized in _SENSITIVE_SCHEMA_KEYS or compact in _SENSITIVE_SCHEMA_KEYS:
        return True
    return normalized.endswith("_url") or normalized.endswith("_endpoint")
