ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS chatwoot_context JSONB;
