"""M-RI-14 audit runner — deterministic; reads snapshot bytes only.

Usage:
    python -m audit.run_audit [--snapdir audit/snapshots] [--outdir audit/out]

Exit 0 only if the in-process checks pass:
  C1 every verdict is in the closed vocabulary, every NOT_CHECKABLE has a
     registered reason, every non-absence verdict carries >= 1 citation;
  C2 the known-answer PIN (if present in the universe) classifies as
     pre-registered (STOP S6 otherwise);
  C3 byte-identical outputs across two in-process runs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audit import engine, report, rules


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m audit.run_audit")
    default_dir = Path(__file__).parent
    ap.add_argument("--snapdir", default=str(default_dir / "snapshots"))
    ap.add_argument("--outdir", default=str(default_dir / "out"))
    args = ap.parse_args(argv)

    snaps = engine.load_snapshots(args.snapdir)
    verdicts = engine.classify_all(snaps)
    verdicts2 = engine.classify_all(snaps)

    checks = []
    ok_vocab = all(
        v["verdict"] in rules.VERDICTS
        and (v["verdict"] != rules.NOT_CHECKABLE
             or v["reason"] in rules.NOT_CHECKABLE_REASONS)
        and (v["citations"] or v["verdict"] == rules.NOT_CHECKABLE)
        for v in verdicts)
    checks.append(("C1 closed vocabulary, typed reasons, citations present",
                   ok_vocab))

    ka = [v for v in verdicts if v["pin14"] == rules.KNOWN_ANSWER_PIN14]
    ka_ok = (not ka) or ka[0]["verdict"] == rules.KNOWN_ANSWER_VERDICT
    checks.append((f"C2 known answer {rules.KNOWN_ANSWER_PIN14} -> "
                   f"{rules.KNOWN_ANSWER_VERDICT}"
                   f" (found: {ka[0]['verdict'] if ka else 'ABSENT'})", ka_ok))

    outputs = {
        "discrepancy_table.csv": report.to_csv(verdicts),
        "discrepancy_table.json": report.to_json(verdicts, snaps),
        "audit-report-client-DO-NOT-SEND-PROSPECTS.md":
            report.to_markdown(verdicts, snaps),
    }
    outputs2 = {
        "discrepancy_table.csv": report.to_csv(verdicts2),
        "discrepancy_table.json": report.to_json(verdicts2, snaps),
        "audit-report-client-DO-NOT-SEND-PROSPECTS.md":
            report.to_markdown(verdicts2, snaps),
    }
    checks.append(("C3 two in-process runs byte-identical", outputs == outputs2))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        with open(outdir / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    tally = {name: 0 for name in rules.VERDICTS}
    for v in verdicts:
        tally[v["verdict"]] += 1
    for name in rules.VERDICTS:
        print(f"{name:>22}: {tally[name]}")
    print(f"{'total':>22}: {len(verdicts)}")
    print()
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    if not ka_ok:
        print("STOP S6: known-answer deviation — this is a finding to report, "
              "not a bug to tune away.")
    print(f"\nAUDIT: {'OK' if all_ok else 'FAILED'} -> {outdir}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
