# Implementation Phases Blueprint

## Summary

Sagad OS should ship in phases. The early work must prove the operator workflow before adding persistent vector stores, MCP servers, managed hosting, or enterprise hardening.

## Roadmap

```mermaid
flowchart LR
  P1["Phase 1: Blueprints"] --> P2["Phase 2: Frontend Preview Wiring"]
  P2 --> P3["Phase 3: Agent Studio Dev Backend"]
  P3 --> P4["Phase 4: Chatwoot HITL Loop"]
  P4 --> P5["Phase 5: Production Hardening"]

  P1 --> D1["Docs, Mermaid, Images"]
  P2 --> D2["Mock/live API adapter fallback"]
  P3 --> D3["uv + FastAPI + LangGraph + Markdown RAG"]
  P4 --> D4["Real inbound + approved outbound + Twenty dry-run"]
  P5 --> D5["Persistent DB, MCP, managed hosting, Auth, Audit"]
```

![Implementation Phases Diagram](images/implementation-phases.png)

## Phase Commitments

- Phase 1 documents the architecture.
- Phase 2 makes the console ready for live preview states.
- Phase 3 adds a local Agent Studio backend.
- Phase 4 proves Chatwoot inbound, HITL outbound, and external Twenty adapter readiness.
- Phase 5 turns the preview into a production service.
