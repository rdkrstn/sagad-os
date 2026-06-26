## Summary

- 

## Verification

- [ ] `cd v1 && npm run lint`
- [ ] `cd v1 && npx tsc --noEmit --pretty false`
- [ ] `cd v1 && npm run build`
- [ ] `cd agent-studio && DATABASE_URL="" LLM_MODE=dry_run uv run python -m pytest`
- [ ] `bash scripts/dev-e2e.sh` → `ALL GREEN` (boots compose, runs the live roundtrip, tears down)
- [ ] `docker compose -f compose.vps.example.yaml build` (only if runtime/Dockerfile changed)

E2E is the definition of done: the stack must be `(healthy)` and `dev-e2e` green before merge. See [`docs/ci-and-e2e.md`](../docs/ci-and-e2e.md).

## Notes

- Linked issue:
- Screenshots:
- Deployment or migration impact:
