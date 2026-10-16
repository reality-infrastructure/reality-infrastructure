-- Traces.  Failed runs are logged identically to successes.
CREATE TABLE IF NOT EXISTS agent_runs (
  run_id           TEXT PRIMARY KEY,
  pack             TEXT NOT NULL,
  agent            TEXT NOT NULL,
  role             TEXT NOT NULL,
  manifest_hash    TEXT NOT NULL,
  agent_version    TEXT NOT NULL,
  provider         TEXT NOT NULL,
  model            TEXT NOT NULL,
  input_hash       TEXT NOT NULL,
  input            TEXT NOT NULL,            -- json
  iterations       TEXT NOT NULL,            -- json: per iteration candidates, tool calls, checks
  output           TEXT,                     -- json, NULL if failed
  status           TEXT NOT NULL CHECK (status IN ('succeeded','failed_guardrail','failed_verifier','access_denied','error')),
  cost_usd         TEXT NOT NULL,            -- decimal string
  latency_ms       INTEGER NOT NULL,
  items_evaluated  INTEGER,
  parent_run_id    TEXT,
  judgement        TEXT NOT NULL,            -- json: RI belief over candidates + log export + root
  judgement_hash   TEXT NOT NULL,            -- sha256 of config/judgement.yaml used
  access_denied    INTEGER NOT NULL DEFAULT 0,
  failure_reasons  TEXT NOT NULL,            -- json list
  ledger_index     INTEGER NOT NULL,
  leaf_hash        TEXT NOT NULL,
  human_verdict    TEXT CHECK (human_verdict IN ('followed','overridden','wrong','n/a')),
  verdict_reason   TEXT,
  verdict_at       TEXT,
  created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_runs_pack_agent ON agent_runs (pack, agent, created_at);
CREATE INDEX IF NOT EXISTS agent_runs_parent ON agent_runs (parent_run_id);

-- Only the verdict columns may change after insert; nothing may be deleted.
CREATE TRIGGER IF NOT EXISTS agent_runs_frozen BEFORE UPDATE ON agent_runs
  WHEN OLD.run_id IS NOT NEW.run_id OR OLD.pack IS NOT NEW.pack OR OLD.agent IS NOT NEW.agent
    OR OLD.role IS NOT NEW.role OR OLD.manifest_hash IS NOT NEW.manifest_hash
    OR OLD.agent_version IS NOT NEW.agent_version OR OLD.provider IS NOT NEW.provider
    OR OLD.model IS NOT NEW.model OR OLD.input_hash IS NOT NEW.input_hash OR OLD.input IS NOT NEW.input
    OR OLD.iterations IS NOT NEW.iterations OR OLD.output IS NOT NEW.output OR OLD.status IS NOT NEW.status
    OR OLD.cost_usd IS NOT NEW.cost_usd OR OLD.latency_ms IS NOT NEW.latency_ms
    OR OLD.items_evaluated IS NOT NEW.items_evaluated OR OLD.parent_run_id IS NOT NEW.parent_run_id
    OR OLD.judgement IS NOT NEW.judgement OR OLD.judgement_hash IS NOT NEW.judgement_hash
    OR OLD.access_denied IS NOT NEW.access_denied OR OLD.failure_reasons IS NOT NEW.failure_reasons
    OR OLD.ledger_index IS NOT NEW.ledger_index OR OLD.leaf_hash IS NOT NEW.leaf_hash
    OR OLD.created_at IS NOT NEW.created_at
  BEGIN SELECT RAISE(ABORT, 'agent_runs: only verdict columns may change'); END;
CREATE TRIGGER IF NOT EXISTS agent_runs_no_delete BEFORE DELETE ON agent_runs
  BEGIN SELECT RAISE(ABORT, 'agent_runs is append-only'); END;
