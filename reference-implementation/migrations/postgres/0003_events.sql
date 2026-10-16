-- The crown jewel.  Append-only: no UPDATE/DELETE grants; corrections are new
-- events of type '<pack>.correction'.
CREATE TABLE IF NOT EXISTS events (
  event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type   TEXT NOT NULL,
  entity_id     TEXT NOT NULL,
  event_type    TEXT NOT NULL,
  payload       JSONB NOT NULL,
  source        TEXT NOT NULL,
  source_ref    TEXT,
  observed_at   TIMESTAMPTZ NOT NULL,
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  ledger_index  BIGINT NOT NULL REFERENCES ledger(idx),
  leaf_hash     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_entity ON events (entity_type, entity_id, observed_at);
CREATE INDEX IF NOT EXISTS events_type ON events (event_type, observed_at);
DROP TRIGGER IF EXISTS events_append_only ON events;
CREATE TRIGGER events_append_only BEFORE UPDATE OR DELETE ON events
  FOR EACH ROW EXECUTE FUNCTION harness_append_only();
REVOKE UPDATE, DELETE, TRUNCATE ON events FROM PUBLIC;
