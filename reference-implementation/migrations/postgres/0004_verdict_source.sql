-- Who adjudicated a run (see sqlite/0004).  The freeze trigger must let the two new
-- verdict columns change along with the three it already allowed.
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS verdict_source TEXT CHECK (verdict_source IS NULL OR verdict_source IN ('human','agent'));
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS verdict_ref UUID;

CREATE OR REPLACE FUNCTION harness_runs_frozen() RETURNS trigger AS $$
BEGIN
  IF (to_jsonb(OLD) - 'human_verdict' - 'verdict_reason' - 'verdict_at' - 'verdict_source' - 'verdict_ref')
     IS DISTINCT FROM (to_jsonb(NEW) - 'human_verdict' - 'verdict_reason' - 'verdict_at' - 'verdict_source' - 'verdict_ref') THEN
    RAISE EXCEPTION 'agent_runs: only verdict columns may change';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
