-- A third verdict source: `outcome` (see sqlite/0005).  Precedence human > outcome > agent.
ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS agent_runs_verdict_source_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_verdict_source_check
  CHECK (verdict_source IS NULL OR verdict_source IN ('human','agent','outcome'));
