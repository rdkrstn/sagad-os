# Security Policy

Sagad OS is early-stage open-source software. Do not use it for regulated or high-risk customer data without reviewing the deployment, auth, audit, and data-retention model.

## Reporting Security Issues

Please do not open public issues for vulnerabilities. Use GitHub private vulnerability reporting or contact the maintainers through the repository owner.

## Current Security Boundaries

- Browser code must not call provider APIs directly.
- Agent Studio owns provider credentials, approval gates, retries, and audit metadata.
- `.env` files, provider tokens, customer exports, generated caches, local databases, and private maintainer notes must not be committed.
- Twenty CRM writes are disabled or dry-run by default.
- Chatwoot sends should stay HITL-only until explicitly configured otherwise.

## Not Production-Hardened Yet

The current preview does not include full production auth, tenant isolation, encrypted secret storage, persistent audit storage, or high-risk compliance workflows.
