-- Who adjudicated a run.  `human_verdict` keeps its name and holds the verdict in force;
-- `verdict_source` says whether a human or a judge agent recorded it (a human verdict
-- outranks and replaces an agent's; an agent never replaces a human's), and
-- `verdict_ref` is the judge's own run_id when the source is an agent.
ALTER TABLE agent_runs ADD COLUMN verdict_source TEXT CHECK (verdict_source IS NULL OR verdict_source IN ('human','agent'));
ALTER TABLE agent_runs ADD COLUMN verdict_ref TEXT;
