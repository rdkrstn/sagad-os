-- Widen integration_connections.provider to include 'ghl' (GoHighLevel adapter).
-- The original CHECK constraint (migrations/0001_sagad_foundation.sql) was unnamed, so
-- Postgres auto-named it `integration_connections_provider_check`. Drop-then-add keeps this
-- migration idempotent: on re-run the DROP IF EXISTS removes the constraint we added last
-- time, and the ADD recreates it with the full provider set.
ALTER TABLE integration_connections
  DROP CONSTRAINT IF EXISTS integration_connections_provider_check;

ALTER TABLE integration_connections
  ADD CONSTRAINT integration_connections_provider_check
  CHECK (provider IN ('chatwoot', 'twenty', 'ghl'));