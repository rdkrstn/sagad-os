# Knowledge Pipeline

Operator language: this is the approved answer source. Developer language: this is the RAG layer.

## Sources

v0.1 starts with Markdown knowledge packs:

- FAQs;
- SOPs;
- QA rubrics;
- compliance rules;
- escalation rules;
- approved templates.

## Retrieval Flow

```mermaid
flowchart LR
  Docs["Approved docs"] --> Chunks["Chunks + metadata"]
  Chunks --> Search["Retriever"]
  Intent["Intent + risk"] --> Search
  Search --> Context["Cited context"]
  Context --> Agent["Sales or Support Agent"]
  Agent --> Draft["Draft reply"]
```

Future versions can move from in-memory search to Postgres `pgvector`, but the source of truth remains governed knowledge.

