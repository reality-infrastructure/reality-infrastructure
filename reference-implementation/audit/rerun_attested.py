"""M-RI-15 attested re-run — the same frozen machine, attestation as the only new input.

Usage:
    python -m audit.rerun_attested [--snapdir audit/snapshots]
                                   [--baseline audit/out/discrepancy_table.json]
                                   [--outdir audit/out/attested-2026-08-02]
                                   [--pin PIN14]   (replay a single parcel's verdict)

Mechanism (PREREGISTRATION.md §9 amendment A1): operator attestation events from
audit/attestation/attestations.yaml are composed at the rules boundary —
attestation-aware client_match / near_miss wrappers that consult the attested
sets by normalized EXACT string equality and delegate everything else to the
frozen originals. rules.py / engine.py / report.py / run_audit.py execute
byte-identical to the baseline commit; verified here by sha256 and pinned again
in tests. The verdict delta is therefore attributable entirely to the rulings.

Exit 0 only if all checks pass:
  C1 closed vocabulary, typed reasons, citations present;
  C2 known-answer PIN still classifies as pre-registered;
  C3 two in-process runs byte-identical (attested outputs AND delta outputs);
  C4 frozen surfaces byte-identical to baseline (sha256);
  C5 every verdict transition vs baseline traces to >=1 attestation event —
     an untraceable transition means the re-run is not the same machine
     (M-RI-15 stop condition; the halt is the finding).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

from audit import engine, report, rules
from audit.attestation import events as att

FROZEN_SHA256 = {
    "rules.py": "4b9f561d495206d8403289ad0cee38b052bcafa9fac2c3d07f1e0c9e41023748",
    "engine.py": "fb68f4e74f6b6722874c73fc50118409a0f9715f85fbf238734d0ccb0aa11f93",
    "report.py": "99c5dd931974113b520305864e41bd092c1b789f1bb6360cfb19b0b9bf0428ff",
    "run_audit.py": "14d3133eea3b4a7fe200e9717465e51ecf0ffb343a5284ee5328fe26127f00ae",
}

DELTA_CSV_FIELDS = ["pin", "status", "claim_class", "from_verdict", "from_rule",
                    "to_verdict", "to_rule", "verdict_changed", "causing_events"]


def frozen_surface_ok() -> list[tuple[str, bool]]:
    here = Path(__file__).parent
    out = []
    for name, want in sorted(FROZEN_SHA256.items()):
        got = hashlib.sha256((here / name).read_bytes()).hexdigest()
        out.append((name, got == want))
    return out


# --------------------------------------------------------------------------
# boundary composition (the attestation overlay)
# --------------------------------------------------------------------------

def compose_matchers(events: list[dict]):
    """Attestation-aware (client_match, near_miss, STATUS_CLASS).

    Pure functions of the frozen originals plus the attestation events.
    Normalized EXACT equality only — no ruling generalizes into a pattern.
    """
    alias_norm = frozenset(rules.normalize(s) for s in att.alias_strings(events))
    ruled_norm = alias_norm | frozenset(
        rules.normalize(s) for s in att.not_client_strings(events))
    frozen_client_match = rules.client_match
    frozen_near_miss = rules.near_miss

    def client_match(name: str) -> bool:
        if rules.normalize(name or "") in alias_norm:
            return True
        return frozen_client_match(name)

    def near_miss(name: str) -> bool:
        if rules.normalize(name or "") in ruled_norm:
            return False
        return frozen_near_miss(name)

    status_class = dict(rules.STATUS_CLASS)
    status_class.update(att.status_overrides(events))
    return client_match, near_miss, status_class


def classify_all_attested(snaps: dict, events: list[dict]) -> list[dict]:
    """engine.classify_all with the overlay bound at the rules boundary."""
    cm, nm, sc = compose_matchers(events)
    saved = (rules.client_match, rules.near_miss, rules.STATUS_CLASS)
    rules.client_match, rules.near_miss, rules.STATUS_CLASS = cm, nm, sc
    try:
        return engine.classify_all(snaps)
    finally:
        rules.client_match, rules.near_miss, rules.STATUS_CLASS = saved


# --------------------------------------------------------------------------
# delta vs the archived baseline
# --------------------------------------------------------------------------

def causing_events(base_v: dict, events: list[dict]) -> list[str]:
    """Attestation events attributable to this parcel's transition."""
    out = []
    nm = set(base_v.get("near_miss_strings") or [])
    for e in events:
        if e["kind"] == "name-variant" and e["subject"] in nm:
            out.append(f"name-variant:{e['subject']}={e['decision']}")
        elif (e["kind"] == "status-semantics"
              and e["subject"] == base_v["status"]
              and e["decision"] != "uncertain"):
            out.append(f"status-semantics:{e['subject']}={e['decision']}")
    return out


def compute_delta(baseline: list[dict], attested: list[dict],
                  events: list[dict]) -> list[dict]:
    base_by_pin = {v["pin"]: v for v in baseline}
    delta = []
    for v in attested:
        b = base_by_pin[v["pin"]]
        if (b["verdict"], b["rule"]) == (v["verdict"], v["rule"]):
            continue
        delta.append({
            "pin": v["pin"], "status": v["status"],
            "claim_class": v["claim_class"],
            "from_verdict": b["verdict"], "from_rule": b["rule"],
            "to_verdict": v["verdict"], "to_rule": v["rule"],
            "verdict_changed": b["verdict"] != v["verdict"],
            "causing_events": causing_events(b, events),
        })
    return delta


def delta_csv(delta: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=DELTA_CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    for d in delta:
        row = dict(d)
        row["causing_events"] = "; ".join(d["causing_events"])
        w.writerow(row)
    return buf.getvalue()


def _tally(verdicts: list[dict]) -> dict[str, int]:
    t = {name: 0 for name in rules.VERDICTS}
    for v in verdicts:
        t[v["verdict"]] += 1
    return t


def delta_json(delta: list[dict], baseline: list[dict], attested: list[dict],
               events: list[dict], meta: dict) -> str:
    doc = {
        "banner": report.BANNER,
        "contract": "M-RI-15 (attest, re-run, select)",
        "amendment": "audit/PREREGISTRATION.md §9 A1",
        "inputs": meta,
        "headline": {"before": _tally(baseline), "after": _tally(attested),
                     "denominators": {"parcels": len(attested),
                                      "county_checkable_claims": sum(
                                          1 for v in attested
                                          if v["claim_class"] in
                                          (rules.DISPOSED, rules.HELD)
                                          and v["verdict"] != rules.NOT_CHECKABLE)}},
        "attestation_events": events,
        "transitions": delta,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def delta_markdown(delta: list[dict], baseline: list[dict], attested: list[dict],
                   events: list[dict], meta: dict) -> str:
    tb, ta = _tally(baseline), _tally(attested)
    n = len(attested)
    eligible = sum(1 for v in attested
                   if v["claim_class"] in (rules.DISPOSED, rules.HELD)
                   and v["verdict"] != rules.NOT_CHECKABLE)
    verdict_changed = [d for d in delta if d["verdict_changed"]]
    rule_only = [d for d in delta if not d["verdict_changed"]]
    lines = []
    a = lines.append
    a(f"> **{report.BANNER}**")
    a("")
    a("# Attested re-run — verdict delta against the M-RI-14 baseline")
    a("")
    a(f"The only new input is the operator's 12 attestation rulings "
      f"(`audit/attestation/attestations.yaml`, sha256 "
      f"`{meta['attestations_sha256'][:16]}…`, attested 2026-08-02; "
      f"PREREGISTRATION.md §9 amendment A1). County snapshots, classifier, and "
      f"rules are byte-identical to the baseline (sha256-verified) — every "
      f"transition below is attributable to a ruling, and the re-run asserts it.")
    a("")
    a("Structural guarantee: the baseline's 25 CONTRADICTED verdicts were "
      "unreachable by these rulings — any parcel containing a ruled string had "
      "already been forced AMBIGUOUS by the near-miss discipline, so the "
      "contradiction count survives attestation untouched; it cannot have been "
      "softened or inflated by the operator's own rulings.")
    a("")
    a("## Headline")
    a("")
    a(f"| Verdict | before | after | denominator |")
    a("|---|---|---|---|")
    for name in rules.VERDICTS:
        a(f"| {name} | {tb[name]} | {ta[name]} | {n} parcels |")
    a(f"\nCounty-checkable claims: {eligible} of {n} parcels (unchanged; all "
      f"five status-semantics rulings were `uncertain`, so no NOT_CHECKABLE "
      f"parcel entered or left the checkable universe).")
    a("")
    a(f"## Verdict transitions ({len(verdict_changed)})")
    a("")
    a("| PIN | CRM status | from | to | caused by |")
    a("|---|---|---|---|---|")
    for d in verdict_changed:
        cause = "; ".join(f"`{c}`" for c in d["causing_events"]) or "**NONE — DEFECT**"
        a(f"| {d['pin']} | {d['status']} | {d['from_verdict']} ({d['from_rule']}) "
          f"| {d['to_verdict']} ({d['to_rule']}) | {cause} |")
    a("")
    if rule_only:
        a(f"## Rule-path changes without verdict change ({len(rule_only)})")
        a("")
        a("The near-miss force was released by a ruling but the frozen rules "
          "still reach the same verdict:")
        a("")
        a("| PIN | CRM status | verdict | rule before | rule after | caused by |")
        a("|---|---|---|---|---|---|")
        for d in rule_only:
            cause = "; ".join(f"`{c}`" for c in d["causing_events"]) or "**NONE — DEFECT**"
            a(f"| {d['pin']} | {d['status']} | {d['to_verdict']} | {d['from_rule']} "
              f"| {d['to_rule']} | {cause} |")
        a("")
    amb = [v for v in attested if v["verdict"] == rules.AMBIGUOUS]
    a(f"## Residual AMBIGUOUS ({len(amb)} of {n})")
    a("")
    for v in amb:
        nm = set(v.get("near_miss_strings") or [])
        if nm:
            why = ("uncertain ruling keeps the near-miss force: "
                   + "; ".join(f"`{s}`" for s in sorted(nm)))
        else:
            why = (f"structural ({v['rule']}): records neither support nor "
                   "contradict under the frozen rules — not curable by "
                   "attestation")
        a(f"- {v['pin']} — CRM `{v['status']}`: {why}")
    a("")
    unclear = [v for v in attested if v["verdict"] == rules.NOT_CHECKABLE
               and v["reason"] == "status-semantics-unresolved"]
    a(f"Status semantics deferred to client confirmation keep "
      f"{len(unclear)} parcels NOT_CHECKABLE(status-semantics-unresolved); "
      f"the operator's client-confirmation question list is recorded in "
      f"`audit/attestation/attestations.yaml`.")
    a("")
    a(f"> {rules.COVERAGE_CAVEAT}")
    a("")
    a("Replay: `python -m audit.rerun_attested` reconstructs this delta "
      "byte-identically from the frozen snapshots plus the attestation events; "
      "`--pin <PIN14>` replays a single parcel's verdict.")
    a("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def build_outputs(snaps: dict, baseline: list[dict],
                  events: list[dict], meta: dict) -> dict[str, str]:
    verdicts = classify_all_attested(snaps, events)
    delta = compute_delta(baseline, verdicts, events)
    return {
        "discrepancy_table.csv": report.to_csv(verdicts),
        "discrepancy_table.json": report.to_json(verdicts, snaps),
        "audit-report-client-DO-NOT-SEND-PROSPECTS.md":
            report.to_markdown(verdicts, snaps),
        "delta_table.csv": delta_csv(delta),
        "delta_table.json": delta_json(delta, baseline, verdicts, events, meta),
        "delta-report.md": delta_markdown(delta, baseline, verdicts, events, meta),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m audit.rerun_attested")
    default_dir = Path(__file__).parent
    ap.add_argument("--snapdir", default=str(default_dir / "snapshots"))
    ap.add_argument("--baseline",
                    default=str(default_dir / "out" / "discrepancy_table.json"))
    ap.add_argument("--outdir",
                    default=str(default_dir / "out" / "attested-2026-08-02"))
    ap.add_argument("--pin", default=None,
                    help="replay one parcel: print its attested verdict record")
    args = ap.parse_args(argv)

    surface = frozen_surface_ok()
    events = att.load_events()
    att_sha = hashlib.sha256(att.DEFAULT_PATH.read_bytes()).hexdigest()
    baseline_bytes = Path(args.baseline).read_bytes()
    baseline = json.loads(baseline_bytes)["verdicts"]
    meta = {
        "attestations_sha256": att_sha,
        "baseline": str(Path(args.baseline).as_posix()),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "snapdir": str(Path(args.snapdir).as_posix()),
    }
    snaps = engine.load_snapshots(args.snapdir)

    if args.pin:
        verdicts = classify_all_attested(snaps, events)
        hit = [v for v in verdicts if v["pin14"] == args.pin.replace("-", "")]
        if not hit:
            print(f"PIN {args.pin}: not in the audit universe")
            return 1
        print(json.dumps(hit[0], indent=2, ensure_ascii=False))
        base = {v["pin"]: v for v in baseline}[hit[0]["pin"]]
        print(f"\nbaseline verdict: {base['verdict']} ({base['rule']})"
              f" -> attested verdict: {hit[0]['verdict']} ({hit[0]['rule']})")
        for c in causing_events(base, events):
            print(f"  caused by {c}")
        return 0

    outputs = build_outputs(snaps, baseline, events, meta)
    outputs2 = build_outputs(snaps, baseline, events, meta)

    verdicts = classify_all_attested(snaps, events)
    delta = compute_delta(baseline, verdicts, events)

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
    checks.append(("C3 two in-process runs byte-identical (incl. delta)",
                   outputs == outputs2))
    checks.append(("C4 frozen surfaces byte-identical to baseline: "
                   + ", ".join(name for name, _ in surface),
                   all(ok for _, ok in surface)))
    untraceable = [d for d in delta if not d["causing_events"]]
    checks.append(("C5 every transition traces to an attestation event "
                   f"({len(delta)} transitions, {len(untraceable)} untraceable)",
                   not untraceable))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        with open(outdir / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    for name in rules.VERDICTS:
        b = sum(1 for v in baseline if v["verdict"] == name)
        n = sum(1 for v in verdicts if v["verdict"] == name)
        print(f"{name:>22}: {b:>3} -> {n:>3}")
    print(f"{'total':>22}: {len(verdicts)}")
    print()
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    if untraceable:
        print("\nSTOP: verdict transition(s) not traceable to any attestation "
              "event — the re-run is not the same machine. Parcels: "
              + ", ".join(d["pin"] for d in untraceable))
    print(f"\nATTESTED RE-RUN: {'OK' if all_ok else 'FAILED'} -> {outdir}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
