-- The crown jewel.  Append-only: corrections are new events of type '<pack>.correction'.
CREATE TABLE IF NOT EXISTS events (
  event_id      TEXT PRIMARY KEY,
  entity_type   TEXT NOT NULL,
  entity_id     TEXT NOT NULL,
  event_type    TEXT NOT NULL,
  payload       TEXT NOT NULL,              -- json
  source        TEXT NOT NULL,              -- human | agent:<name> | adapter:<id> | pipeline:<id>
  source_ref    TEXT,
  observed_at   TEXT NOT NULL,
  recorded_at   TEXT NOT NULL,
  ledger_index  INTEGER NOT NULL,
  leaf_hash     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_entity ON events (entity_type, entity_id, observed_at);
CREATE INDEX IF NOT EXISTS events_type ON events (event_type, observed_at);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
