# Audit Log

Sagad Audit makes the system BPO-grade. Every AI action should be explainable later.

## Required Events

- message received;
- intent classified;
- agent selected;
- knowledge retrieved;
- draft generated;
- confidence scored;
- approval required;
- supervisor action taken;
- final response sent;
- provider action failed or dry-ran;
- webhook rejected, ignored, duplicated, or persisted.

## Operator Diagnostics

Agent Studio stores diagnostic events in the audit layer and exposes them through `GET /diagnostics/events` behind the internal Sagad boundary. The Console should surface these events before an operator needs Docker logs. Conversation Review shows per-thread tool and delivery results, including provider HTTP status, error type, and a clipped response body when available.

## Why It Matters

Audit logs support QA review, coaching, incident investigation, compliance checks, and client reporting. They also prevent the system from feeling like an AI black box.
