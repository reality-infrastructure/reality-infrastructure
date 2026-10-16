-- Traces.  Failed runs are logged identically to successes.
CREATE TABLE IF NOT EXISTS agent_runs (
  run_id           UUID PRIMARY KEY,
  pack             TEXT NOT NULL,
  agent            TEXT NOT NULL,
  role             TEXT NOT NULL,
  manifest_hash    TEXT NOT NULL,
  agent_version    TEXT NOT NULL,
  provider         TEXT NOT NULL,
  model            TEXT NOT NULL,
  input_hash       TEXT NOT NULL,
  input            JSONB NOT NULL,
  iterations       JSONB NOT NULL,
  output           JSONB,
  status           TEXT NOT NULL CHECK (status IN ('succeeded','failed_guardrail','failed_verifier','access_denied','error')),
  cost_usd         NUMERIC(18,8) NOT NULL,
  latency_ms       INTEGER NOT NULL,
  items_evaluated  INTEGER,
  parent_run_id    UUID REFERENCES agent_runs(run_id),
  judgement        JSONB NOT NULL,
  judgement_hash   TEXT NOT NULL,
  access_denied    BOOLEAN NOT NULL DEFAULT FALSE,
  failure_reasons  JSONB NOT NULL,
  ledger_index     BIGINT NOT NULL REFERENCES ledger(idx),
  leaf_hash        TEXT NOT NULL,
  human_verdict    TEXT CHECK (human_verdict IN ('followed','overridden','wrong','n/a')),
  verdict_reason   TEXT,
  verdict_at       TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_runs_pack_agent ON agent_runs (pack, agent, created_at);
CREATE INDEX IF NOT EXISTS agent_runs_parent ON agent_runs (parent_run_id);

CREATE OR REPLACE FUNCTION harness_runs_frozen() RETURNS trigger AS $$
BEGIN
  IF (to_jsonb(OLD) - 'human_verdict' - 'verdict_reason' - 'verdict_at')
     IS DISTINCT FROM (to_jsonb(NEW) - 'human_verdict' - 'verdict_reason' - 'verdict_at') THEN
    RAISE EXCEPTION 'agent_runs: only verdict columns may change';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS agent_runs_frozen ON agent_runs;
CREATE TRIGGER agent_runs_frozen BEFORE UPDATE ON agent_runs
  FOR EACH ROW EXECUTE FUNCTION harness_runs_frozen();
DROP TRIGGER IF EXISTS agent_runs_no_delete ON agent_runs;
CREATE TRIGGER agent_runs_no_delete BEFORE DELETE ON agent_runs
  FOR EACH ROW EXECUTE FUNCTION harness_append_only();
REVOKE DELETE, TRUNCATE ON agent_runs FROM PUBLIC;
