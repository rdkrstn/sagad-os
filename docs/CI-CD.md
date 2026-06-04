# CI/CD

Sagad OS uses GitHub Actions for continuous integration.

## Current CI

Workflow: `.github/workflows/ci.yml`

The workflow runs on pushes to `main` and on pull requests.

Jobs:

- Frontend: `npm ci`, `npm run lint`, `npx tsc --noEmit --pretty false`, `npm run build`.
- Agent Studio: `uv sync`, `uv run pytest`.
- Container builds: Docker build smoke tests for `v1/` and `agent-studio/`.
- Docker Compose smoke: boots `compose.preview.yaml`, waits for service health, then verifies `GET /health` and `GET /health/ready` on Agent Studio.

If the compose smoke test fails, the workflow prints `sagad-db`, `agent-studio`, and `sagad-console` logs so unhealthy containers can be diagnosed from the pull request.

## Docker Publish

Workflow: `.github/workflows/docker-publish.yml`

This workflow runs on:

- version tags such as `v0.1.0`;
- manual `workflow_dispatch`.

It publishes two GitHub Container Registry images:

- `ghcr.io/<owner>/sagad-os-console`
- `ghcr.io/<owner>/sagad-os-agent-studio`

Published tags include:

- the Git tag when the workflow runs from a version tag;
- a `sha-...` tag for the exact commit.

The current workflow does not deploy to a VPS. That is intentional until the target environment and managed-hosting model are finalized. A VPS can either build locally from source or pull the GHCR images after a tagged release.

## Future CD

Recommended stages:

1. CI validates source and container builds.
2. CI boots the preview compose stack and verifies Agent Studio health.
3. Release workflow builds versioned images.
4. Images are pushed to GitHub Container Registry.
5. A deployment workflow updates the target self-hosted or managed environment.
6. Deployment verifies `GET /health`, `GET /health/ready`, and provider readiness endpoints.

## Required Secrets Later

For image publishing:

- default `GITHUB_TOKEN` with `packages: write` permissions.

For managed deploys:

- deployment SSH key or cloud deploy token;
- target host;
- registry credentials if private;
- environment-specific secrets stored outside Git.

Do not put provider credentials in GitHub Actions logs or repository files.
