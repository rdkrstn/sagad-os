# Sagad OS Blueprints

## Purpose

This package is the visual and operational blueprint set for Sagad OS. It explains how the AI-native BPO layer moves from today's mock supervisor console into a working Chatwoot and Agent Studio preview.

## Blueprint Set

- `01-system-architecture.md`: canonical Sagad OS architecture plus the working Chatwoot -> Agent Studio -> HITL preview.
- `02-knowledge-architecture.md`: KB, SOP, QA, and compliance knowledge layer for human agents and AI agents.
- `03-chatwoot-hitl-loop.md`: first live preview loop with HITL-only sending.
- `04-implementation-phases.md`: phased delivery path from diagrams to dev preview and production hardening.
- `05-adapter-architecture.md`: tool-agnostic adapter layer for channels, CRM, automation, knowledge, and audit systems.

## Diagram Assets

- Mermaid sources live in `diagrams/`.
- Rendered technical images live in `images/`.
- The generated poster image is for presentation and orientation only; Mermaid files remain the source of truth for exact architecture.

## Current Boundary

Sagad OS remains safe to run locally. The frontend can fall back to typed mocks when Agent Studio is not available. Live Chatwoot sending is only allowed through explicit HITL approval in Agent Studio. Twenty CRM is external, disabled/dry-run by default, and configured only in Agent Studio.
