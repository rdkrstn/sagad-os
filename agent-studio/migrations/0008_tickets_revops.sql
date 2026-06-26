-- AI RevOps: lightweight ticket fields on conversations + per-provider sync watermarks.
--
-- Tickets extend ConversationRecord in place (no separate ticket table): every conversation
-- IS a ticket. Defaults keep existing rows unchanged -- ticket_status='open', all other
-- ticket fields NULL -- so prior behavior and tests are preserved.
--
-- integration_sync_state holds inbound-poller watermarks (GHL today): `updated_since` is the
-- epoch-millis /conversations/search cursor; `payload` stores the per-conversation lastMessageId
-- cursor map. The GHL poller reads/advances these each cycle (see agent_studio/ghl_poller.py).

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS provider_conversation_id TEXT,
  ADD COLUMN IF NOT EXISTS ticket_status TEXT NOT NULL DEFAULT 'open'
    CHECK (ticket_status IN ('open', 'in_progress', 'waiting', 'resolved')),
  ADD COLUMN IF NOT EXISTS assignee TEXT,
  ADD COLUMN IF NOT EXISTS priority TEXT
    CHECK (priority IS NULL OR priority IN ('low', 'medium', 'high', 'urgent')),
  ADD COLUMN IF NOT EXISTS pipeline_stage TEXT,
  ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMPTZ;

-- Supervisor ticket-queue index: filter by status/assignee within an org, newest first.
CREATE INDEX IF NOT EXISTS conversations_ticket_queue_idx
  ON conversations (organization_id, ticket_status, assignee, updated_at DESC);

CREATE TABLE IF NOT EXISTS integration_sync_state (
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  updated_since BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, provider)
);