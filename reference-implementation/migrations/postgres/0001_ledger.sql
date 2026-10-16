-- The RI evidence ledger: canonical entry bytes + leaf hash, append-only.
CREATE TABLE IF NOT EXISTS ledger (
  idx        BIGINT PRIMARY KEY,
  entry      BYTEA NOT NULL,
  leaf_hash  BYTEA NOT NULL
);
CREATE OR REPLACE FUNCTION harness_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ledger_append_only ON ledger;
CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE ON ledger
  FOR EACH ROW EXECUTE FUNCTION harness_append_only();
REVOKE UPDATE, DELETE, TRUNCATE ON ledger FROM PUBLIC;
