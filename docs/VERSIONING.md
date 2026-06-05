# Versioning

Sagad OS uses Semantic Versioning.

Current version: `0.1.0`

## Version Sources

Keep these in sync for releases:

- `VERSION`
- `v1/package.json`
- `agent-studio/pyproject.toml`
- `CHANGELOG.md`

## Version Rules

Until `1.0.0`, minor versions may include breaking changes while the platform contracts are still stabilizing.

- Patch: bug fixes, docs corrections, internal cleanup.
- Minor: new features, new adapter surfaces, schema changes, deployment changes.
- Major: stable post-1.0 breaking changes.

## Release Checklist

1. Update `VERSION`.
2. Update `v1/package.json`.
3. Update `agent-studio/pyproject.toml`.
4. Update `CHANGELOG.md`.
5. Run local verification:

```powershell
cd v1
npm run lint
npx tsc --noEmit --pretty false
npm run build

cd ..\agent-studio
uv run pytest

cd ..
docker compose -f compose.preview.yaml build
```

6. Tag the release:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

7. Watch GitHub Actions:

- `release-check.yml` verifies version file alignment and changelog coverage.
- `docker-publish.yml` builds, scans, and publishes the Sagad Console and Agent Studio images to GHCR.

Do not deploy a tag until both release workflows pass.
