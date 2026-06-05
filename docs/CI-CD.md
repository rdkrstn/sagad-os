# CI/CD

Sagad OS uses GitHub Actions for CI, release validation, and Docker image publishing. CD is intentionally manual for now so self-host operators can learn the deploy flow before automation hides it.

## Pull Request Gate

Workflow: `.github/workflows/ci.yml`

The workflow runs on pull requests and pushes to `main`.

Required jobs:

- Security scan: `gitleaks` secret scan plus Trivy filesystem scan for high and critical vulnerabilities.
- Frontend: `npm ci`, production dependency audit, `npm run lint`, `npx tsc --noEmit --pretty false`, and `npm run build`.
- Agent Studio: Python 3.12, `uv sync`, pgvector migration smoke check, and `uv run pytest` with the optional Postgres persistence test enabled.
- OCR runtime: the Agent Studio job installs `poppler-utils`, `tesseract-ocr`, and `tesseract-ocr-eng` before tests so scanned-PDF ingestion paths are covered.
- Container builds: Docker Buildx builds both runtime images, loads them locally, and scans each image with Trivy.
- Compose smoke: validates `compose.preview.yaml`, boots Sagad Postgres, Agent Studio, and the Console, then verifies `/health`, `/health/live`, `/health/ready`, and console-to-Agent-Studio internal connectivity.

If the compose smoke test fails, CI prints service status and logs for `sagad-db`, `agent-studio`, and `sagad-console`.

## Release Gate

Workflow: `.github/workflows/release-check.yml`

Release tags must use `vX.Y.Z`.

The release check verifies:

- `VERSION` matches the tag without the `v` prefix;
- `v1/package.json` matches `VERSION`;
- `agent-studio/pyproject.toml` matches `VERSION`;
- `CHANGELOG.md` contains an entry for the release version.

## Docker Publish

Workflow: `.github/workflows/docker-publish.yml`

This workflow runs on:

- version tags such as `v0.1.0`;
- manual `workflow_dispatch`.

It publishes two GitHub Container Registry images:

- `ghcr.io/<owner>/sagad-os-console`
- `ghcr.io/<owner>/sagad-os-agent-studio`

Before publish, each image is built locally and scanned with Trivy. Published images include Git tag, semantic-version, major/minor, and `sha-...` tags. The publish job also asks Docker Buildx to attach SBOM and provenance attestations.

## Manual VPS Deploy Flow

Until automated CD exists, deploy from the VPS:

```bash
cd ~/apps/sagad-os
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose -f compose.vps.yaml config --quiet
docker compose -f compose.vps.yaml up -d --build
docker compose -f compose.vps.yaml ps
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/ready').read().decode())"
```

For GHCR-based releases later, replace the local build step with image pulls after the tagged release workflow succeeds.

## Rollback Flow

Keep rollback boring:

```bash
cd ~/apps/sagad-os
git log --oneline -5
git checkout <previous-good-sha-or-tag>
docker compose -f compose.vps.yaml up -d --build
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/ready').read().decode())"
```

Before production, add database backup/restore steps around migrations. Do not rely on Git rollback alone after schema-changing releases.

## Observability Boundaries

- Uptime Kuma answers: is the service reachable?
- Sentry answers: did the console or backend crash?
- LangSmith answers: why did the graph or AI agent behave this way?
- Sagad Diagnostics answers: what provider/webhook/tool action failed?

Sentry is optional. The repo should run without it, but deployments may set:

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=preview
SENTRY_RELEASE=
SENTRY_TRACES_SAMPLE_RATE=0.1
```

## Required Secrets Later

For image publishing:

- default `GITHUB_TOKEN` with `packages: write` permissions.

For managed deploys:

- deployment SSH key or cloud deploy token;
- target host;
- registry credentials if private;
- environment-specific secrets stored outside Git.

Do not put provider credentials in GitHub Actions logs or repository files.
