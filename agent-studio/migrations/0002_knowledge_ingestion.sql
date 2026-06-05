CREATE TABLE IF NOT EXISTS knowledge_sources (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  sync_policy TEXT NOT NULL DEFAULT 'manual',
  last_synced_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, source_type, name)
);

CREATE TABLE IF NOT EXISTS knowledge_ingestion_jobs (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  total_files INTEGER NOT NULL DEFAULT 0,
  processed_files INTEGER NOT NULL DEFAULT 0,
  failed_files INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_ingestion_errors (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL REFERENCES knowledge_ingestion_jobs(id) ON DELETE CASCADE,
  source_path TEXT NOT NULL,
  error_code TEXT NOT NULL,
  message TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE knowledge_documents
  ADD COLUMN IF NOT EXISTS source_id TEXT REFERENCES knowledge_sources(id) ON DELETE SET NULL;

ALTER TABLE knowledge_documents
  ADD COLUMN IF NOT EXISTS last_ingestion_job_id TEXT REFERENCES knowledge_ingestion_jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS knowledge_ingestion_jobs_source_idx
  ON knowledge_ingestion_jobs(organization_id, source_id, created_at DESC);

CREATE INDEX IF NOT EXISTS knowledge_ingestion_errors_job_idx
  ON knowledge_ingestion_errors(organization_id, job_id, created_at ASC);

DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'knowledge_sources',
    'knowledge_ingestion_jobs',
    'knowledge_ingestion_errors'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I_org_isolation ON %I', table_name, table_name);
    EXECUTE format(
      'CREATE POLICY %I_org_isolation ON %I USING (organization_id = sagad_current_organization_id() AND sagad_has_active_membership(organization_id)) WITH CHECK (organization_id = sagad_current_organization_id() AND sagad_has_active_membership(organization_id))',
      table_name,
      table_name
    );
  END LOOP;
END $$;
