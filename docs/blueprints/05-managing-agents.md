# Managing Agents

Sagad OS uses an "Agents as Markdown" approach to configure specialist agents. Developers and operators define new agents by creating and editing Markdown files in the `agent_studio/agent_studio/agents/` directory. This declarative approach makes it straightforward to version-control agent behaviors, set explicit tool boundaries, and map them to routing intents.

## File Structure

An agent definition file consists of two sections:
1. **YAML Frontmatter**: Defines the core system configuration (name, routing intents, allowed tools).
2. **Markdown Body**: Acts as the system prompt, containing the identity, boundaries, and standard operating procedures (SOP).

### Frontmatter Configuration

The frontmatter properties strictly control how Agent Studio loads, routes, and restricts the agent.

| Property | Type | Description |
| --- | --- | --- |
| `name` | string | A unique identifier for the agent (e.g., `general_support`). |
| `intents` | list | The routing keys mapped to this agent. When the classifier assigns one of these intents to a conversation, this agent is invoked. |
| `allowed_tools` | list | The specific tools this agent is authorized to use. This explicitly restricts capabilities to prevent overreach or unauthorized actions. |

### Prompt Structure

The markdown body shapes the agent's behavior. For operational consistency and clarity, it should be structured into these standard sections:

- **Identity**: The persona, role, and overarching goal of the agent.
- **Boundaries**: Hard limits on what the agent should NOT do, mitigating risk.
- **Process**: The step-by-step workflow the agent should follow to handle inquiries and utilize its allowed tools.

## Example: Support Agent

Below is a complete, copy-pasteable example of an agent definition. 

```markdown
---
name: general_support
intents:
  - general_support
  - account_access
  - billing_refund
allowed_tools:
  - crm.lookup_contact
  - knowledge_base_search
  - chatwoot_draft_reply
---

# Identity
You are the Support Agent for Sagad OS. Your primary goal is to resolve account and service issues accurately while maintaining an empathetic and professional tone.

# Boundaries
- Do NOT issue refunds directly.
- Do NOT guess technical troubleshooting steps.

# Process
1. Acknowledge the customer's issue clearly.
2. Use `knowledge_base_search` to locate the relevant SOP.
3. Use `crm.lookup_contact` for customer history if needed.
```
