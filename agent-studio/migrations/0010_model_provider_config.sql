-- Writable model-provider config (SuperAdmin console).
--
-- One model_provider_config row per organization holds the active chat/embedding provider
-- selection plus a JSONB blob of non-secret per-provider fields (models, base URLs, per-node
-- overrides). API keys live in model_provider_secret_versions, encrypted with
-- pgp_sym_encrypt using the same SAGAD_INTEGRATION_ENCRYPTION_KEY as integration secrets.
--
-- configured_settings() merges this row over env (DB wins; env is the fallback when no row),
-- so the resolver (model_config.py) reads merged Settings unchanged.
--
-- Idempotent: every CREATE is IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS model_provider_config (
  organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  chat_provider TEXT NOT NULL DEFAULT 'none',
  embedding_provider TEXT NOT NULL DEFAULT 'auto',
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- users.id is SERIAL (INTEGER) in 0001, so updated_by must be INTEGER (matching the 0001
  -- convention at line 130), NOT UUID -- binding the trusted-context user_id (users.id::text,
  -- e.g. "6") into a UUID column raised "invalid input syntax for type uuid: "6"" on every
  -- DB-backed PUT /model-providers. See 0012 for the existing-deploy heal.
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_provider_secret_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  secret_name TEXT NOT NULL CHECK (secret_name IN (
    'openai_api_key',
    'fireworks_api_key',
    'ollama_cloud_api_key',
    'openrouter_api_key',
    'litellm_master_key'
  )),
  encrypted_secret BYTEA NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS model_provider_secret_versions_active_idx
  ON model_provider_secret_versions(organization_id, secret_name)
  WHERE is_active;
