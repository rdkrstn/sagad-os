-- Sagad OS Sprint 2-4 AI Ops quality layer
-- Review against 0001_sagad_foundation.sql before applying.

CREATE TABLE IF NOT EXISTS retrieval_quality_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  conversation_id text NULL,
  raw_query text NOT NULL,
  normalized_query text NOT NULL,
  intent text NOT NULL,
  risk_level text NOT NULL,
  selected_agent text NOT NULL,
  expanded_queries jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata_filters jsonb NOT NULL DEFAULT '{}'::jsonb,
  retrieval_confidence double precision NOT NULL DEFAULT 0,
  missing_knowledge boolean NOT NULL DEFAULT false,
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval_quality_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  retrieval_quality_run_id uuid NOT NULL REFERENCES retrieval_quality_runs(id) ON DELETE CASCADE,
  source_id text NOT NULL,
  title text NOT NULL,
  category text NOT NULL,
  source_path text NOT NULL,
  original_score double precision NOT NULL DEFAULT 0,
  rerank_score double precision NOT NULL DEFAULT 0,
  excerpt text NOT NULL DEFAULT '',
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  rank integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_capability_manifests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  tool_name text NOT NULL,
  provider text NOT NULL,
  skill_name text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('read', 'write', 'dry_run')),
  risk_level text NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
  allowed_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
  requires_approval boolean NOT NULL DEFAULT false,
  enabled boolean NOT NULL DEFAULT true,
  dry_run_default boolean NOT NULL DEFAULT true,
  description text NOT NULL DEFAULT '',
  input_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, tool_name)
);

CREATE TABLE IF NOT EXISTS tool_policy_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  conversation_id text NULL,
  tool_name text NOT NULL,
  selected_agent text NOT NULL,
  conversation_risk_level text NOT NULL,
  allowed boolean NOT NULL,
  requires_approval boolean NOT NULL,
  dry_run boolean NOT NULL,
  blocked_reason text NULL,
  policy_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_cases (
  id text PRIMARY KEY,
  organization_id uuid NULL,
  suite text NOT NULL,
  message text NOT NULL,
  expected jsonb NOT NULL DEFAULT '{}'::jsonb,
  tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  suite text NOT NULL,
  git_sha text NULL,
  total integer NOT NULL DEFAULT 0,
  passed integer NOT NULL DEFAULT 0,
  failed integer NOT NULL DEFAULT 0,
  pass_rate double precision NOT NULL DEFAULT 0,
  average_score double precision NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NULL,
  eval_run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  case_id text NOT NULL,
  passed boolean NOT NULL,
  score double precision NOT NULL DEFAULT 0,
  failures jsonb NOT NULL DEFAULT '[]'::jsonb,
  prediction jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_quality_runs_org_created
  ON retrieval_quality_runs (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_conversation
  ON tool_policy_decisions (organization_id, conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_eval_runs_org_created
  ON eval_runs (organization_id, created_at DESC);
