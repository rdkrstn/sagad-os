# Ingestion Engine Blueprint

## Summary

The Sagad Knowledge Ingestion Engine turns operational source material into a governed approved answer source. Agent Studio owns the ingestion runtime, file parsing, review state, embedding calls, pgvector writes, and audit trail. The Console only shows source status, review queues, ingestion jobs, and missing knowledge.

![Ingestion Engine Poster](images/ingestion-engine-poster.png)

## Technical Diagram

The Mermaid source is `diagrams/ingestion-engine.mmd`. Rendered technical assets are available as:

- `images/ingestion-engine.svg`
- `images/ingestion-engine.png`

![Ingestion Engine Diagram](images/ingestion-engine.png)

## First Slice

Local ingestion ships first. Supported first-pass inputs are Markdown, TXT, transcripts, PDF, DOCX, XLSX, and CSV. Google Drive, websites, Notion, Confluence, and external KBs are future source adapters behind Agent Studio.

New imports start as `needs_review`. They are not available to Sales or Support agents until a supervisor, admin, or QA operator approves the document.

## Runtime Flow

```mermaid
flowchart LR
  Source["Source Content"] --> Extract["Extract Text"]
  Extract --> Normalize["Normalize Record"]
  Normalize --> Review["Needs Review"]
  Review --> Approved["Approved Knowledge"]
  Approved --> Chunk["Chunk + Version"]
  Chunk --> Embed["OpenAI Embeddings"]
  Embed --> Vector["Postgres + pgvector"]
  Vector --> Retrieve["Approved Answer Source"]
  Retrieve --> Agent["Sales / Support Agent"]
```

## Governance Rules

- pgvector is the retrieval index, not the source of truth.
- Reviewable knowledge records remain the source material.
- SOP, QA, compliance, refund, cancellation, billing, and verification content must remain approval-gated.
- Scanned PDFs without extractable text should fail with an OCR-needed error.
- Duplicate content is detected by source path and content hash.
- Retrieval filters by organization, category, approval status, intent, risk, and agent role where available.

## Sync And Staleness

Manual uploads require manual re-upload when the source changes. Markdown packs can be re-indexed on command. Google Drive should default to scheduled sync in a later phase. Stale content should be flagged when it has not been reviewed for six months.
