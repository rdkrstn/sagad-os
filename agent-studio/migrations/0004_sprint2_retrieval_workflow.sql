ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS selected_agent TEXT,
  ADD COLUMN IF NOT EXISTS customer_driver TEXT,
  ADD COLUMN IF NOT EXISTS retrieval_confidence DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS missing_knowledge BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS retrieval_diagnostic JSONB DEFAULT '{}'::jsonb;
