-- Bootstrap a real, login-able owner for the default workspace.
--
-- ensureDefaultMembership (v1/auth.ts) seeds every newly-signed-in user as 'supervisor'
-- (ON CONFLICT DO NOTHING, so re-login never upgrades them). The only seeded owner from
-- 0001_sagad_foundation.sql is owner@sagad.local -- a fake email no one can sign into.
-- The members console + every admin API route 403 unless role IN ('owner','admin'), so
-- promoting a member requires already being an owner: chicken-and-egg.
--
-- This migration promotes hello@johnreddemafeliz.com to owner of johnred-workspace.
-- owner@sagad.local is intentionally LEFT IN PLACE -- agent_studio.db.default_trusted_context
-- requires it (DEFAULT_USER_EMAIL) or the backend cannot resolve a trusted context.
-- Idempotent: safe to re-run.

INSERT INTO users (name, email)
VALUES ('Johnred Demafeliz', 'hello@johnreddemafeliz.com')
ON CONFLICT (email) DO NOTHING;

INSERT INTO organization_members (organization_id, user_id, role, status)
SELECT o.id, u.id, 'owner', 'active'
FROM users u
JOIN organizations o ON o.slug = 'johnred-workspace'
WHERE u.email = 'hello@johnreddemafeliz.com'
ON CONFLICT (organization_id, user_id) DO UPDATE
SET role = 'owner',
    status = 'active',
    updated_at = now();
