ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS eval_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS trace_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS diagnostic_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS decision_reason TEXT,
  ADD COLUMN IF NOT EXISTS guardrail_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS confidence_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS final_confidence_score DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS quality_label TEXT,
  ADD COLUMN IF NOT EXISTS quality_signals JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS quality_notes TEXT,
  ADD COLUMN IF NOT EXISTS quality_evaluated_at TIMESTAMPTZ;

DO $$
BEGIN
  ALTER TABLE conversations
    ADD CONSTRAINT conversations_quality_score_range
    CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER TABLE conversations
    ADD CONSTRAINT conversations_final_confidence_score_range
    CHECK (
      final_confidence_score IS NULL
      OR (final_confidence_score >= 0 AND final_confidence_score <= 1)
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS eval_runs (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  suite_name TEXT NOT NULL DEFAULT 'default',
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  total_cases INTEGER NOT NULL DEFAULT 0 CHECK (total_cases >= 0),
  passed_cases INTEGER NOT NULL DEFAULT 0 CHECK (passed_cases >= 0),
  failed_cases INTEGER NOT NULL DEFAULT 0 CHECK (failed_cases >= 0),
  average_score DOUBLE PRECISION CHECK (
    average_score IS NULL OR (average_score >= 0 AND average_score <= 1)
  ),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  trace_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_results (
  id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  eval_run_id TEXT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  case_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'passed'
    CHECK (status IN ('passed', 'failed', 'errored', 'skipped')),
  score DOUBLE PRECISION CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  expected_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  actual_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  failure_reason TEXT,
  trace_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS eval_runs_org_started_idx
  ON eval_runs(organization_id, started_at DESC);

CREATE INDEX IF NOT EXISTS eval_results_run_case_idx
  ON eval_results(organization_id, eval_run_id, case_name);

CREATE INDEX IF NOT EXISTS eval_results_conversation_idx
  ON eval_results(organization_id, conversation_id, created_at DESC)
  WHERE conversation_id IS NOT NULL;

ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE eval_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS eval_runs_org_isolation ON eval_runs;
DROP POLICY IF EXISTS eval_results_org_isolation ON eval_results;

CREATE POLICY eval_runs_org_isolation
  ON eval_runs
  USING (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  )
  WITH CHECK (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  );

CREATE POLICY eval_results_org_isolation
  ON eval_results
  USING (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  )
  WITH CHECK (
    organization_id = sagad_current_organization_id()
    AND sagad_has_active_membership(organization_id)
  );
