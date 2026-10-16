-- The RI evidence ledger: canonical entry bytes + leaf hash, append-only.
CREATE TABLE IF NOT EXISTS ledger (
  idx        INTEGER PRIMARY KEY,
  entry      BLOB NOT NULL,
  leaf_hash  BLOB NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
