-- One process per store (HARNESS.md), enforced instead of documented.  The ledger's Merkle log
-- lives in one process's memory; a second writer would race the ledger index.  A process that
-- writes on a schedule or for a long time (engine.schedule, engine.sweep, engine.autoloop) takes
-- the lease named 'store' first; a second process cannot take it until the holder releases it
-- or stops renewing it (expires_at passes).  Operational state, not evidence: acquisitions and
-- heartbeats are recorded as ledger-bound '<pack>.heartbeat' events by the scheduler.
CREATE TABLE IF NOT EXISTS engine_leases (
  name          TEXT PRIMARY KEY,
  holder        TEXT NOT NULL,
  acquired_at   TEXT NOT NULL,
  expires_at    TEXT NOT NULL,
  heartbeat_at  TEXT NOT NULL
);
