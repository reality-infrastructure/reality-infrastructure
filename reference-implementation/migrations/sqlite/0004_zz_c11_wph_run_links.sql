-- JH-C11 wpH: run linkage and the clarification status, ledger-bound like the rest of the row.
--   session_id          the multi-turn session the run belongs to (G-P13)
--   supersedes_run_id   the earlier run this run revises (G-P13); the reverse link is a lookup
--   replayed_from       '<run_id>@<iteration>:<candidate>' for a mid-run replay (G-B21)
--   forked_from         the parent run whose working context the child received (G-B4)
--   fanout_group        the orchestrator fan-out group a child ran in (G-D11)
--   context_sha256      sha256 of the run's working context (G-B4, G-B21)
--   clarification       the question a child returned instead of guessing (G-B3)
-- SQLite cannot widen a CHECK in place, so the table is rebuilt with the new status
-- 'needs_clarification'.  This file sorts after 0004_verdict_source and before every 0005_*:
-- a later migration that adds agent_runs columns alters the rebuilt table.
CREATE TABLE agent_runs_c11 (
  run_id           TEXT PRIMARY KEY,
  pack             TEXT NOT NULL,
  agent            TEXT NOT NULL,
  role             TEXT NOT NULL,
  manifest_hash    TEXT NOT NULL,
  agent_version    TEXT NOT NULL,
  provider         TEXT NOT NULL,
  model            TEXT NOT NULL,
  input_hash       TEXT NOT NULL,
  input            TEXT NOT NULL,
  iterations       TEXT NOT NULL,
  output           TEXT,
  status           TEXT NOT NULL CHECK (status IN ('succeeded','failed_guardrail','failed_verifier','access_denied','error','needs_clarification')),
  cost_usd         TEXT NOT NULL,
  latency_ms       INTEGER NOT NULL,
  items_evaluated  INTEGER,
  parent_run_id    TEXT,
  judgement        TEXT NOT NULL,
  judgement_hash   TEXT NOT NULL,
  access_denied    INTEGER NOT NULL DEFAULT 0,
  failure_reasons  TEXT NOT NULL,
  ledger_index     INTEGER NOT NULL,
  leaf_hash        TEXT NOT NULL,
  human_verdict    TEXT CHECK (human_verdict IN ('followed','overridden','wrong','n/a')),
  verdict_reason   TEXT,
  verdict_at       TEXT,
  created_at       TEXT NOT NULL,
  verdict_source   TEXT CHECK (verdict_source IS NULL OR verdict_source IN ('human','agent')),
  verdict_ref      TEXT,
  session_id        TEXT,
  supersedes_run_id TEXT,
  replayed_from     TEXT,
  forked_from       TEXT,
  fanout_group      TEXT,
  context_sha256    TEXT,
  clarification     TEXT
);
INSERT INTO agent_runs_c11 (run_id, pack, agent, role, manifest_hash, agent_version, provider, model, input_hash,
  input, iterations, output, status, cost_usd, latency_ms, items_evaluated, parent_run_id, judgement, judgement_hash,
  access_denied, failure_reasons, ledger_index, leaf_hash, human_verdict, verdict_reason, verdict_at, created_at,
  verdict_source, verdict_ref)
SELECT run_id, pack, agent, role, manifest_hash, agent_version, provider, model, input_hash,
  input, iterations, output, status, cost_usd, latency_ms, items_evaluated, parent_run_id, judgement, judgement_hash,
  access_denied, failure_reasons, ledger_index, leaf_hash, human_verdict, verdict_reason, verdict_at, created_at,
  verdict_source, verdict_ref
FROM agent_runs;
DROP TABLE agent_runs;
ALTER TABLE agent_runs_c11 RENAME TO agent_runs;
CREATE INDEX IF NOT EXISTS agent_runs_pack_agent ON agent_runs (pack, agent, created_at);
CREATE INDEX IF NOT EXISTS agent_runs_parent ON agent_runs (parent_run_id);
CREATE INDEX IF NOT EXISTS agent_runs_session ON agent_runs (session_id, created_at);
CREATE INDEX IF NOT EXISTS agent_runs_supersedes ON agent_runs (supersedes_run_id);

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
    OR OLD.session_id IS NOT NEW.session_id OR OLD.supersedes_run_id IS NOT NEW.supersedes_run_id
    OR OLD.replayed_from IS NOT NEW.replayed_from OR OLD.forked_from IS NOT NEW.forked_from
    OR OLD.fanout_group IS NOT NEW.fanout_group OR OLD.context_sha256 IS NOT NEW.context_sha256
    OR OLD.clarification IS NOT NEW.clarification
  BEGIN SELECT RAISE(ABORT, 'agent_runs: only verdict columns may change'); END;
CREATE TRIGGER IF NOT EXISTS agent_runs_no_delete BEFORE DELETE ON agent_runs
  BEGIN SELECT RAISE(ABORT, 'agent_runs is append-only'); END;
