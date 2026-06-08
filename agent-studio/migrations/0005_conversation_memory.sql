CREATE TABLE IF NOT EXISTS conversation_memory_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
  chatwoot_conversation_id TEXT,
  customer_name TEXT,
  memory_type TEXT NOT NULL,
  content TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'conversation',
  score DOUBLE PRECISION NOT NULL DEFAULT 0,
  source_message_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding_model TEXT,
  embedding vector(1536),
  content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS conversation_memory_items_unique_idx
  ON conversation_memory_items(organization_id, conversation_id, memory_type, content_hash)
  WHERE conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS conversation_memory_items_org_thread_idx
  ON conversation_memory_items(organization_id, conversation_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS conversation_memory_items_chatwoot_idx
  ON conversation_memory_items(organization_id, chatwoot_conversation_id, updated_at DESC)
  WHERE chatwoot_conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS conversation_memory_items_vector_idx
  ON conversation_memory_items
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

ALTER TABLE conversation_memory_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS conversation_memory_items_org_isolation ON conversation_memory_items;

CREATE POLICY conversation_memory_items_org_isolation
  ON conversation_memory_items
  USING (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  )
  WITH CHECK (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  );
