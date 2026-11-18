-- JH-C11 wpH: run linkage and the clarification status (see sqlite/0004_zz_c11_wph_run_links.sql).
-- The freeze trigger (0004_verdict_source) excludes only the verdict columns, so every column
-- added here is frozen after insert like the rest of the row.
ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS agent_runs_status_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_status_check
  CHECK (status IN ('succeeded','failed_guardrail','failed_verifier','access_denied','error','needs_clarification'));
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS session_id TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS supersedes_run_id UUID REFERENCES agent_runs(run_id);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS replayed_from TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS forked_from UUID;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS fanout_group TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS context_sha256 TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS clarification TEXT;
CREATE INDEX IF NOT EXISTS agent_runs_session ON agent_runs (session_id, created_at);
CREATE INDEX IF NOT EXISTS agent_runs_supersedes ON agent_runs (supersedes_run_id);
