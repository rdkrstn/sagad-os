CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS verification_token (
  identifier TEXT NOT NULL,
  expires TIMESTAMPTZ NOT NULL,
  token TEXT NOT NULL,
  PRIMARY KEY (identifier, token)
);

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255),
  email VARCHAR(255) UNIQUE,
  "emailVerified" TIMESTAMPTZ,
  image TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(255) NOT NULL,
  provider VARCHAR(255) NOT NULL,
  "providerAccountId" VARCHAR(255) NOT NULL,
  refresh_token TEXT,
  access_token TEXT,
  expires_at BIGINT,
  id_token TEXT,
  scope TEXT,
  session_state TEXT,
  token_type TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS accounts_provider_provider_account_id_idx
  ON accounts(provider, "providerAccountId");

CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires TIMESTAMPTZ NOT NULL,
  "sessionToken" VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  display_name TEXT,
  default_organization_id UUID REFERENCES organizations(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_members (
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'supervisor', 'agent', 'qa', 'viewer')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);

INSERT INTO organizations (slug, name)
VALUES ('johnred-workspace', 'Johnred Workspace')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO users (name, email)
VALUES ('Sagad Owner', 'owner@sagad.local')
ON CONFLICT (email) DO NOTHING;

INSERT INTO profiles (user_id, display_name, default_organization_id)
SELECT users.id, users.name, organizations.id
FROM users, organizations
WHERE users.email = 'owner@sagad.local'
  AND organizations.slug = 'johnred-workspace'
ON CONFLICT (user_id) DO UPDATE
SET default_organization_id = EXCLUDED.default_organization_id,
    updated_at = now();

INSERT INTO organization_members (organization_id, user_id, role, status)
SELECT organizations.id, users.id, 'owner', 'active'
FROM users, organizations
WHERE users.email = 'owner@sagad.local'
  AND organizations.slug = 'johnred-workspace'
ON CONFLICT (organization_id, user_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS chatwoot_inboxes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  chatwoot_account_id TEXT,
  chatwoot_inbox_id TEXT,
  name TEXT NOT NULL DEFAULT 'Default Chatwoot Inbox',
  is_default BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS chatwoot_inboxes_provider_idx
  ON chatwoot_inboxes(organization_id, chatwoot_account_id, chatwoot_inbox_id)
  WHERE chatwoot_account_id IS NOT NULL AND chatwoot_inbox_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS chatwoot_inboxes_default_idx
  ON chatwoot_inboxes(organization_id)
  WHERE is_default;

INSERT INTO chatwoot_inboxes (organization_id, name, is_default)
SELECT id, 'Johnred Workspace Chatwoot', true
FROM organizations
WHERE slug = 'johnred-workspace'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS integration_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('chatwoot', 'twenty')),
  base_url TEXT,
  account_id TEXT,
  inbox_id TEXT,
  api_mode TEXT,
  enabled BOOLEAN NOT NULL DEFAULT true,
  dry_run BOOLEAN NOT NULL DEFAULT true,
  allow_writes BOOLEAN NOT NULL DEFAULT false,
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, provider)
);

CREATE TABLE IF NOT EXISTS integration_secret_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connection_id UUID NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
  secret_name TEXT NOT NULL CHECK (secret_name IN ('api_access_token', 'webhook_token', 'api_key')),
  encrypted_secret BYTEA NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS integration_secret_versions_active_idx
  ON integration_secret_versions(connection_id, secret_name)
  WHERE is_active;

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  chatwoot_conversation_id TEXT,
  chatwoot_message_id TEXT,
  customer_name TEXT NOT NULL DEFAULT 'Unknown customer',
  channel TEXT NOT NULL DEFAULT 'chatwoot',
  incoming_message TEXT NOT NULL,
  normalized_message TEXT NOT NULL DEFAULT '',
  intent TEXT NOT NULL DEFAULT 'unknown',
  route TEXT,
  contact_driver TEXT,
  confidence DOUBLE PRECISION,
  risk_level TEXT NOT NULL DEFAULT 'medium',
  sentiment TEXT,
  verification_required TEXT,
  retrieved_knowledge JSONB NOT NULL DEFAULT '[]'::jsonb,
  crm_context JSONB,
  tool_plans JSONB NOT NULL DEFAULT '[]'::jsonb,
  tool_results JSONB NOT NULL DEFAULT '[]'::jsonb,
  draft_reply TEXT NOT NULL DEFAULT '',
  qa_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  compliance_status TEXT NOT NULL DEFAULT 'needs_review',
  approval_status TEXT NOT NULL DEFAULT 'needs_approval',
  send_status TEXT NOT NULL DEFAULT 'not_sent',
  trace_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_org_updated_idx
  ON conversations(organization_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL CHECK (sender_type IN ('customer', 'ai_agent', 'human_agent', 'system', 'tool')),
  body TEXT NOT NULL,
  external_message_id TEXT,
  provider TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS conversation_messages_external_idx
  ON conversation_messages(conversation_id, external_message_id)
  WHERE external_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  supervisor_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'edited', 'sent', 'send_failed')),
  edited_reply TEXT,
  send_status TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_plans (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  action TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  requires_approval BOOLEAN NOT NULL DEFAULT true,
  approved BOOLEAN NOT NULL DEFAULT false,
  dry_run BOOLEAN NOT NULL DEFAULT true,
  args JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_results (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  plan_id TEXT REFERENCES tool_plans(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT NOT NULL,
  external_id TEXT,
  data JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pack_slug TEXT NOT NULL,
  category TEXT NOT NULL,
  source_path TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  approval_status TEXT NOT NULL DEFAULT 'approved',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, pack_slug, source_path)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  heading TEXT,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  token_count INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS knowledge_chunk_embeddings (
  chunk_id TEXT NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  embedding_model TEXT NOT NULL,
  embedding vector(1536),
  content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (chunk_id, embedding_model)
);

CREATE INDEX IF NOT EXISTS knowledge_chunk_embeddings_vector_idx
  ON knowledge_chunk_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE TABLE IF NOT EXISTS retrieval_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  query TEXT NOT NULL,
  intent TEXT,
  risk_level TEXT,
  filters JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding_model TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval_hits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  retrieval_run_id UUID NOT NULL REFERENCES retrieval_runs(id) ON DELETE CASCADE,
  chunk_id TEXT REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
  rank INTEGER NOT NULL,
  score DOUBLE PRECISION NOT NULL,
  excerpt TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  embedding vector(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TABLE IF EXISTS sagad_duplicate_conversation_map;

CREATE TEMP TABLE sagad_duplicate_conversation_map ON COMMIT DROP AS
WITH ranked AS (
  SELECT
    id,
    FIRST_VALUE(id) OVER (
      PARTITION BY organization_id, channel, chatwoot_conversation_id
      ORDER BY updated_at DESC, created_at DESC, id DESC
    ) AS survivor_id,
    ROW_NUMBER() OVER (
      PARTITION BY organization_id, channel, chatwoot_conversation_id
      ORDER BY updated_at DESC, created_at DESC, id DESC
    ) AS row_number
  FROM conversations
  WHERE chatwoot_conversation_id IS NOT NULL
)
SELECT id AS duplicate_id, survivor_id
FROM ranked
WHERE row_number > 1;

DELETE FROM conversation_messages duplicate_message
USING sagad_duplicate_conversation_map duplicate_map,
      conversation_messages survivor_message
WHERE duplicate_message.conversation_id = duplicate_map.duplicate_id
  AND survivor_message.conversation_id = duplicate_map.survivor_id
  AND duplicate_message.external_message_id IS NOT NULL
  AND duplicate_message.external_message_id = survivor_message.external_message_id;

UPDATE conversation_messages
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE conversation_messages.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE approvals
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE approvals.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE tool_plans
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE tool_plans.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE tool_results
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE tool_results.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE audit_events
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE audit_events.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE retrieval_runs
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE retrieval_runs.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

UPDATE conversation_summaries
SET conversation_id = sagad_duplicate_conversation_map.survivor_id
FROM sagad_duplicate_conversation_map
WHERE conversation_summaries.conversation_id = sagad_duplicate_conversation_map.duplicate_id;

DELETE FROM conversations
USING sagad_duplicate_conversation_map
WHERE conversations.id = sagad_duplicate_conversation_map.duplicate_id;

CREATE UNIQUE INDEX IF NOT EXISTS conversations_chatwoot_thread_idx
  ON conversations(organization_id, channel, chatwoot_conversation_id)
  WHERE chatwoot_conversation_id IS NOT NULL;

DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'chatwoot_inboxes',
    'integration_connections',
    'integration_secret_versions',
    'conversations',
    'conversation_messages',
    'approvals',
    'tool_plans',
    'tool_results',
    'audit_events',
    'knowledge_documents',
    'knowledge_chunks',
    'knowledge_chunk_embeddings',
    'retrieval_runs',
    'retrieval_hits',
    'conversation_summaries'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION sagad_current_organization_id()
RETURNS UUID
LANGUAGE SQL
STABLE
AS $$
  SELECT NULLIF(current_setting('app.organization_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION sagad_current_user_id()
RETURNS INTEGER
LANGUAGE SQL
STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::integer
$$;

CREATE OR REPLACE FUNCTION sagad_has_active_membership(target_organization_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM organization_members
    WHERE organization_id = target_organization_id
      AND user_id = sagad_current_user_id()
      AND status = 'active'
  )
$$;

DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'chatwoot_inboxes',
    'integration_connections',
    'integration_secret_versions',
    'conversations',
    'conversation_messages',
    'approvals',
    'tool_plans',
    'tool_results',
    'audit_events',
    'knowledge_documents',
    'knowledge_chunks',
    'knowledge_chunk_embeddings',
    'retrieval_runs',
    'retrieval_hits',
    'conversation_summaries'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I_org_isolation ON %I', table_name, table_name);
    EXECUTE format(
      'CREATE POLICY %I_org_isolation ON %I USING (organization_id = sagad_current_organization_id() AND sagad_has_active_membership(organization_id)) WITH CHECK (organization_id = sagad_current_organization_id() AND sagad_has_active_membership(organization_id))',
      table_name,
      table_name
    );
  END LOOP;
END $$;
