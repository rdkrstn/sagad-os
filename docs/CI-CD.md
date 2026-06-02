# CI/CD

Sagad OS uses GitHub Actions for continuous integration.

## Current CI

Workflow: `.github/workflows/ci.yml`

The workflow runs on pushes to `main` and on pull requests.

Jobs:

- Frontend: `npm ci`, `npm run lint`, `npx tsc --noEmit --pretty false`, `npm run build`.
- Agent Studio: `uv sync`, `uv run pytest`.
- Container builds: Docker build smoke tests for `v1/` and `agent-studio/`.

The current workflow does not publish images or deploy to a VPS. That is intentional until the registry, environment, and managed-hosting model are finalized.

## Future CD

Recommended stages:

1. CI validates source and container builds.
2. Release workflow builds versioned images.
3. Images are pushed to GitHub Container Registry.
4. A deployment workflow updates the target self-hosted or managed environment.
5. Deployment verifies `GET /health` and provider readiness endpoints.

## Required Secrets Later

For image publishing:

- `GHCR_TOKEN` or default `GITHUB_TOKEN` package permissions.

For managed deploys:

- deployment SSH key or cloud deploy token;
- target host;
- registry credentials if private;
- environment-specific secrets stored outside Git.

Do not put provider credentials in GitHub Actions logs or repository files.
