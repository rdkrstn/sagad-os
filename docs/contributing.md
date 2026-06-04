# Contributing

Read the root `CONTRIBUTING.md` first. This page adds product-specific contribution rules.

## Contribution Priorities

1. Keep the golden demo loop working.
2. Keep provider credentials out of browser code.
3. Prefer typed contracts over loose payloads.
4. Keep the Console operator-friendly.
5. Update docs when behavior or architecture changes.

## Before Opening A PR

Run the relevant checks:

```powershell
cd v1
npm run lint
npx tsc --noEmit --pretty false
npm run build
```

```powershell
cd agent-studio
uv run pytest
```

Include the commands you ran in the PR body.

