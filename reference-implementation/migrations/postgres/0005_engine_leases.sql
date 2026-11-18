-- One process per store, enforced in the store (see sqlite/0005_engine_leases.sql).
CREATE TABLE IF NOT EXISTS engine_leases (
  name          TEXT PRIMARY KEY,
  holder        TEXT NOT NULL,
  acquired_at   TIMESTAMPTZ NOT NULL,
  expires_at    TIMESTAMPTZ NOT NULL,
  heartbeat_at  TIMESTAMPTZ NOT NULL
);
