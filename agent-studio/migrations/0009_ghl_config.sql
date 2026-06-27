-- GHL (GoHighLevel) DB-backed adapter config.
--
-- Adds GHL-specific columns to integration_connections. They are nullable and are only
-- populated on 'ghl' rows; chatwoot/twenty rows keep working unchanged. Migration 0007
-- already widened the provider CHECK to include 'ghl'.
--
-- integration_secret_versions.secret_name is free-form text (no CHECK constraint), so the
-- new GHL secret names ('ghl_webhook_secret', 'ghl_native_webhook_key') need no schema change
-- there — they are simply new rows written by the existing _upsert_secret helper.
--
-- Idempotent: every ADD COLUMN is guarded by IF NOT EXISTS so re-runs are safe.

ALTER TABLE integration_connections
  ADD COLUMN IF NOT EXISTS location_id text,
  ADD COLUMN IF NOT EXISTS outbound_mode text,
  ADD COLUMN IF NOT EXISTS signature_scheme text,
  ADD COLUMN IF NOT EXISTS poll_enabled boolean,
  ADD COLUMN IF NOT EXISTS poll_interval_seconds int,
  ADD COLUMN IF NOT EXISTS poll_conversation_limit int,
  ADD COLUMN IF NOT EXISTS poll_message_limit int;
