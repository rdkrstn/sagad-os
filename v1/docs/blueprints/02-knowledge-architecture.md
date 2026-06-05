# Knowledge Architecture Blueprint

## Summary

The knowledge layer is the operating system for both human agents and AI agents. Source files and reviewed knowledge records are the source of truth; pgvector is only the retrieval index used by Agent Studio.

![Knowledge Layer Poster](images/knowledge-layer-poster.png)

## Knowledge Flow

```mermaid
flowchart LR
  Source["Markdown Source Docs"] --> Canonical["Knowledge Records"]
  Canonical --> Chunks["Chunks + Metadata + Version"]
  Chunks --> Vector["Vector Index"]
  Chunks --> Store["Source Store"]
  Conversation["Conversation State"] --> Policy["Intent + Risk + Role Filter"]
  Policy --> Vector
  Policy --> Store
  Store --> Context["Cited Context Pack"]
  Vector --> Context
  Context --> Agent["Specialist Agent"]
  Agent --> QA["QA/Compliance Gate"]
```

![Knowledge Architecture Diagram](images/knowledge-layer.png)

## Ingestion Engine

The ingestion engine is documented in `07-ingestion-engine.md`. It starts with local files and transcripts, extracts text, normalizes metadata, creates `needs_review` documents, and only embeds content after approval. Google Drive and other remote source syncs are phase two.

```mermaid
flowchart LR
  Files["Files / transcripts"] --> Extract["Extract text"]
  Extract --> Review["Needs review"]
  Review --> Approved["Approved knowledge"]
  Approved --> Chunks["Chunks + versions"]
  Chunks --> Embeddings["OpenAI embeddings"]
  Embeddings --> Pgvector["Sagad Postgres + pgvector"]
  Pgvector --> Context["Approved answer source"]
  Context --> Agents["Sales / Support agents"]
```

## First Knowledge Pack Categories

- `kb`: product/service facts, pricing language, FAQs.
- `sops`: step-by-step workflows for support, booking, verification, handoff, and follow-up.
- `qa`: rubric criteria used by supervisors and AI review nodes.
- `compliance`: hard rules, blocked claims, identity verification requirements, and approval thresholds.
- `escalations`: refund, cancellation, angry customer, failed tool, and high-risk handling.
- `approved_templates`: safe response language that can be reused in drafts.

## Retrieval Rule

Agent Studio must filter retrieval by client, channel, intent, risk, agent role, and approval status before passing context to an agent. Agents should receive cited context packs, not unrestricted document search.
