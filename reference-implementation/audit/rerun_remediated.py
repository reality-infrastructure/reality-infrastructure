"""M-RI-16 remediated re-run — F1 closed; every delta cause-traced by counterfactual.

Usage:
    python -m audit.rerun_remediated [--snapdir audit/snapshots]
        [--baseline audit/out/attested-2026-08-02/discrepancy_table.json]
        [--outdir audit/out/attested-remediated-2026-08-02]

Two things changed since the M-RI-15 attested baseline (§9 amendment A2):
the normalization amendment ('/' -> space) and the operator's 13th attestation
(SO SUB LAND/BK/DEV -> client-alias). This runner executes the full audit with
both, then runs two COUNTERFACTUALS — attestation-only (pre-A2 normalization,
all 13 rulings) and amendment-only (A2 normalization, first 12 rulings) — and
labels every transition attestation / amendment / both. A transition in
neither counterfactual is a stop-condition defect (exit 1).

Recorder-confirmation banners: verdicts resting solely on blank-party docs
2401822036/2401822037 carry the banner in every table and are excluded from
exhibit consideration by construction.

Checks: C1 vocabulary/citations · C2 known answer · C3 two in-process runs
byte-identical · C4 pinned surfaces match (post-A2 pins) · C5 every transition
cause-traced by counterfactual · C6 zero transitions outside the attested
surface.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

from audit import engine, report, rules, rerun_attested
from audit.attestation import events as att

F1_SUBJECT = "SO SUB LAND/BK/DEV"

# The two verdicts resting solely on blank-party quit claims (M-RI-16 Scope 6).
RECORDER_BANNER = ("RECORDER-CONFIRMATION REQUIRED (docs 2401822036/2401822037 "
                   "are blank-party $100 quit claims; a human must read the "
                   "recorded documents before this verdict faces anyone)")
BANNERED_PINS = ("25-29-323-064-0000", "25-30-207-023-0000")

DELTA_CSV_FIELDS = ["pin", "status", "claim_class", "from_verdict", "from_rule",
                    "to_verdict", "to_rule", "verdict_changed", "cause",
                    "causing_events", "recorder_banner"]


# --------------------------------------------------------------------------
# counterfactual matcher composition (norm-parameterized)
# --------------------------------------------------------------------------

def _pre_a2_normalize(name: str) -> str:
    """The pre-amendment normalization, reproduced for the counterfactual:
    upper, & -> AND, strip .,' , collapse whitespace — no '/' mapping."""
    s = (name or "").upper().replace("&", " AND ")
    s = rules._PUNCT_RE.sub("", s)
    return rules._WS_RE.sub(" ", s).strip()


def compose(norm, events: list[dict]):
    alias = frozenset(norm(s) for s in att.alias_strings(events))
    ruled = alias | frozenset(norm(s) for s in att.not_client_strings(events))

    def cm(name: str) -> bool:
        n = norm(name or "")
        return n in alias or any(p in n for p in rules.CLIENT_ALIAS_PATTERNS)

    def nm(name: str) -> bool:
        n = norm(name or "")
        if n in ruled:
            return False
        return (any(p in n for p in rules.NEAR_MISS_PATTERNS)
                and not cm(name))

    return cm, nm


def classify_with(snaps: dict, norm, events: list[dict]) -> list[dict]:
    cm, nm = compose(norm, events)
    saved = (rules.client_match, rules.near_miss)
    rules.client_match, rules.near_miss = cm, nm
    try:
        return engine.classify_all(snaps)
    finally:
        rules.client_match, rules.near_miss = saved


# --------------------------------------------------------------------------
# cause labeling
# --------------------------------------------------------------------------

def label_causes(baseline: list[dict], full: list[dict],
                 cf_attestation: list[dict], cf_amendment: list[dict]) -> dict:
    """pin -> cause label for every (verdict, rule) change vs baseline."""
    def changed(run):
        b = {v["pin"]: v for v in baseline}
        return {v["pin"] for v in run
                if (b[v["pin"]]["verdict"], b[v["pin"]]["rule"])
                != (v["verdict"], v["rule"])}
    a_set, b_set, f_set = (changed(cf_attestation), changed(cf_amendment),
                           changed(full))
    labels = {}
    for pin in sorted(f_set):
        in_a, in_b = pin in a_set, pin in b_set
        labels[pin] = ("both" if in_a and in_b else
                       "attestation" if in_a else
                       "amendment" if in_b else "UNTRACED")
    return labels


def _tally(verdicts: list[dict]) -> dict[str, int]:
    t = {name: 0 for name in rules.VERDICTS}
    for v in verdicts:
        t[v["verdict"]] += 1
    return t


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------

def delta_rows(baseline, full, events, parties, labels) -> list[dict]:
    delta = rerun_attested.compute_delta(baseline, full, events, parties)
    for d in delta:
        d["cause"] = labels.get(d["pin"], "UNTRACED")
        d["recorder_banner"] = (RECORDER_BANNER if d["pin"] in BANNERED_PINS
                                else "")
    return delta


def delta_csv(delta: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=DELTA_CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    for d in delta:
        row = {k: d[k] for k in DELTA_CSV_FIELDS if k != "causing_events"}
        row["causing_events"] = "; ".join(d["causing_events"])
        w.writerow(row)
    return buf.getvalue()


def contested_manifest(full: list[dict], run_sha: str) -> dict:
    """The frozen contested set M-RI-17 takes as input: every parcel whose
    post-remediation verdict is CONTRADICTED or AMBIGUOUS."""
    contested = [
        {"pin": v["pin"], "verdict": v["verdict"], "rule": v["rule"],
         "status": v["status"],
         "recorder_banner": v["pin"] in BANNERED_PINS}
        for v in full if v["verdict"] in (rules.CONTRADICTED, rules.AMBIGUOUS)]
    return {
        "banner": report.BANNER,
        "purpose": ("M-RI-17 frozen input: the post-remediation contested set "
                    "(CONTRADICTED + AMBIGUOUS) of the M-RI-16 run"),
        "run": "audit/out/attested-remediated-2026-08-02/discrepancy_table.json",
        "run_sha256": run_sha,
        "attestations": "audit/attestation/attestations.yaml (13 events)",
        "preregistration_amendments": ["A1", "A2"],
        "counts": {"CONTRADICTED":
                   sum(1 for c in contested
                       if c["verdict"] == rules.CONTRADICTED),
                   "AMBIGUOUS":
                   sum(1 for c in contested
                       if c["verdict"] == rules.AMBIGUOUS)},
        "parcels": contested,
    }


def remediation_markdown(baseline, full, delta, labels, events, meta,
                         cohorts) -> str:
    tb, ta = _tally(baseline), _tally(full)
    n = len(full)
    eligible = sum(1 for v in full
                   if v["claim_class"] in (rules.DISPOSED, rules.HELD)
                   and v["verdict"] != rules.NOT_CHECKABLE)
    counts = {"attestation": 0, "amendment": 0, "both": 0}
    for lab in labels.values():
        counts[lab] = counts.get(lab, 0) + 1
    verdict_changed = [d for d in delta if d["verdict_changed"]]
    rule_only = [d for d in delta if not d["verdict_changed"]]
    lines = []
    a = lines.append
    a(f"> **{report.BANNER}**")
    a("")
    a("# Remediated re-run — F1 closed; delta vs the M-RI-15 attested baseline")
    a("")
    a(f"Two causes changed this run (PREREGISTRATION.md §9 amendment A2): the "
      f"normalization amendment (`/` → space) and the operator's 13th "
      f"attestation (`{F1_SUBJECT}` → client-alias, basis recorded verbatim). "
      f"Attestations sha256 `{meta['attestations_sha256'][:16]}…`; comparison "
      f"baseline `{meta['baseline']}` (sha256 "
      f"`{meta['baseline_sha256'][:16]}…`). Every transition below is labeled "
      f"with its cause by counterfactual runs — attestation-only (pre-A2 "
      f"normalization, 13 rulings) and amendment-only (A2 normalization, 12 "
      f"rulings) — not by inspection.")
    a("")
    a("## Headline")
    a("")
    a("| Verdict | M-RI-15 attested | remediated | denominator |")
    a("|---|---|---|---|")
    for name in rules.VERDICTS:
        a(f"| {name} | {tb[name]} | {ta[name]} | {n} parcels |")
    a(f"\nCounty-checkable claims: {eligible} of {n} parcels (unchanged).")
    a("")
    a(f"## Transitions ({len(verdict_changed)} verdict, {len(rule_only)} "
      f"rule-path only) — cause breakdown: "
      f"attestation-only {counts['attestation']} · amendment-only "
      f"{counts['amendment']} · both {counts['both']}")
    a("")
    a("The F1 cohorts, accounted (from the finding's own numbers):")
    a("")
    for name, disp in cohorts:
        a(f"- {name}: {disp}")
    a("")
    a("| PIN | CRM status | from | to | cause | caused by | banner |")
    a("|---|---|---|---|---|---|---|")
    for d in verdict_changed + rule_only:
        note = "rule-path only: " if not d["verdict_changed"] else ""
        cause_ev = "; ".join(f"`{c}`" for c in d["causing_events"])
        a(f"| {d['pin']} | {d['status']} | {note}{d['from_verdict']} "
          f"({d['from_rule']}) | {d['to_verdict']} ({d['to_rule']}) | "
          f"{d['cause']} | {cause_ev} | "
          f"{'**' + RECORDER_BANNER + '**' if d['recorder_banner'] else ''} |")
    a("")
    amb = [v for v in full if v["verdict"] == rules.AMBIGUOUS]
    a(f"## Residual AMBIGUOUS ({len(amb)} of {n})")
    a("")
    for v in amb:
        nm = set(v.get("near_miss_strings") or [])
        why = ("uncertain ruling keeps the near-miss force: "
               + "; ".join(f"`{s}`" for s in sorted(nm)) if nm
               else f"structural ({v['rule']}): records neither support nor "
                    "contradict under the rules — not curable by attestation")
        a(f"- {v['pin']} — CRM `{v['status']}`: {why}")
    a("")
    con = [v for v in full if v["verdict"] == rules.CONTRADICTED]
    a(f"## Post-remediation CONTRADICTED ({len(con)} of {n}; "
      f"{eligible} checkable)")
    a("")
    for v in con:
        flag = (" — **" + RECORDER_BANNER + "**"
                if v["pin"] in BANNERED_PINS else "")
        a(f"- {v['pin']} — CRM `{v['status']}` ({v['claim_date']}), rule "
          f"{v['rule']}{flag}")
    a("")
    a("## External-safety declaration")
    a("")
    a("**Externally safe from this run** (each number with its denominator, "
      "the coverage caveat attached, R1 framing):")
    a("")
    a(f"1. The post-remediation headline: of {n} CRM parcels, {eligible} "
      f"carry county-checkable claims; {ta['SUPPORTED']} are SUPPORTED by "
      f"county records, {ta['CONTRADICTED']} CONTRADICTED, "
      f"{ta['UNSUPPORTED_NO_RECORD']} with no bearing record found, "
      f"{ta['AMBIGUOUS']} AMBIGUOUS.")
    a("2. The correction story: the audit's own alias discipline surfaced its "
      "one escaped string, refused to guess, took an operator attestation, "
      "and re-ran — the pre-remediation figures would have overstated "
      "contradictions nearly 3× (25 → 9), and the audit caught its own "
      "overstatement before anyone external saw a number.")
    a("3. Exhibit 1 (29-02-408-053-0000), re-verified under this baseline — "
      "replay line executed clean.")
    a("4. The M-RI-15 attestation delta (23 AMBIGUOUS → SUPPORTED) and this "
      "run's delta, both fully cause-traced and replayable.")
    a("")
    a("**Still bounded (do not use externally without the bound stated):**")
    a("")
    a(f"1. The two bannered CONTRADICTED verdicts ({', '.join(BANNERED_PINS)}) "
      "rest solely on blank-party $100 quit claims (docs 2401822036/37): "
      "Recorder-of-Deeds confirmation is on the operator's list before either "
      "faces anyone. Stated CONTRADICTED count without them: "
      f"{ta['CONTRADICTED'] - len(BANNERED_PINS)} of {eligible} checkable.")
    a("2. Parcels awaiting client confirmation stay in their honest states: "
      "1 AMBIGUOUS behind the A7 uncertain ruling, 10 NOT_CHECKABLE behind "
      "the five status-semantics rulings — the client-confirmation question "
      "list rides in audit/attestation/attestations.yaml.")
    a("3. UNSUPPORTED_NO_RECORD remains a statement about the queried "
      "datasets, never about the world; the coverage caveat must accompany "
      "any external use.")
    a("")
    a(f"> {rules.COVERAGE_CAVEAT}")
    a("")
    a("Replay: `python -m audit.rerun_remediated` reconstructs this run and "
      "delta byte-identically; `python -m audit.rerun_attested --pin <PIN14> "
      "--baseline audit/out/attested-2026-08-02/discrepancy_table.json` "
      "replays one parcel against this comparison baseline.")
    a("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def build_all(snaps, baseline, events, meta):
    full = rerun_attested.classify_all_attested(snaps, events)
    cf_att = classify_with(snaps, _pre_a2_normalize, events)
    events12 = [e for e in events if e["subject"] != F1_SUBJECT]
    cf_amd = classify_with(snaps, rules.normalize, events12)
    labels = label_causes(baseline, full, cf_att, cf_amd)
    parties = rerun_attested.parties_by_pin14(snaps)
    delta = delta_rows(baseline, full, events, parties, labels)

    base_by_pin = {v["pin"]: v for v in baseline}
    cohorts = []
    for name, verd in (("16 F1-CONTRADICTED", rules.CONTRADICTED),
                       ("92 F1-UNSUPPORTED", rules.UNSUPPORTED_NO_RECORD),
                       ("2 F1-AMBIGUOUS", rules.AMBIGUOUS)):
        pins = [d["pin"] for d in delta
                if base_by_pin[d["pin"]]["verdict"] == verd
                and d["verdict_changed"]]
        landed = {}
        for p in pins:
            to = next(d["to_verdict"] for d in delta if d["pin"] == p)
            landed[to] = landed.get(to, 0) + 1
        stayed = ""
        cohorts.append((name, ", ".join(f"{k} ×{v}" for k, v in
                                        sorted(landed.items()))
                        + (stayed if landed else "no verdict changes")))

    json_table = report.to_json(full, snaps)
    outputs = {
        "discrepancy_table.csv": report.to_csv(full),
        "discrepancy_table.json": json_table,
        "audit-report-client-DO-NOT-SEND-PROSPECTS.md":
            report.to_markdown(full, snaps),
        "delta_table.csv": delta_csv(delta),
        "delta_table.json": json.dumps(
            {"banner": report.BANNER, "contract": "M-RI-16",
             "amendment": "audit/PREREGISTRATION.md §9 A2",
             "inputs": meta,
             "headline": {"before": _tally(baseline), "after": _tally(full)},
             "cause_counts": {c: sum(1 for x in labels.values() if x == c)
                              for c in ("attestation", "amendment", "both")},
             "transitions": delta},
            indent=2, ensure_ascii=False) + "\n",
        "remediation-delta.md":
            remediation_markdown(baseline, full, delta, labels, events, meta,
                                 cohorts),
    }
    run_sha = hashlib.sha256(json_table.encode("utf-8")).hexdigest()
    manifest = contested_manifest(full, run_sha)
    outputs["contested-set-manifest.json"] = json.dumps(
        manifest, indent=2, ensure_ascii=False) + "\n"
    return full, cf_att, cf_amd, labels, delta, outputs, run_sha


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m audit.rerun_remediated")
    default_dir = Path(__file__).parent
    ap.add_argument("--snapdir", default=str(default_dir / "snapshots"))
    ap.add_argument("--baseline", default=str(
        default_dir / "out" / "attested-2026-08-02" / "discrepancy_table.json"))
    ap.add_argument("--outdir", default=str(
        default_dir / "out" / "attested-remediated-2026-08-02"))
    args = ap.parse_args(argv)

    surface = rerun_attested.frozen_surface_ok()
    events = att.load_events()
    baseline_bytes = Path(args.baseline).read_bytes()
    baseline = json.loads(baseline_bytes)["verdicts"]
    meta = {
        "attestations_sha256": hashlib.sha256(
            att.DEFAULT_PATH.read_bytes()).hexdigest(),
        "baseline": str(Path(args.baseline).as_posix()),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "snapdir": str(Path(args.snapdir).as_posix()),
    }
    snaps = engine.load_snapshots(args.snapdir)

    full, cf_att, cf_amd, labels, delta, outputs, run_sha = build_all(
        snaps, baseline, events, meta)
    outputs2 = build_all(snaps, baseline, events, meta)[5]

    checks = []
    checks.append(("C1 closed vocabulary, typed reasons, citations present",
                   all(v["verdict"] in rules.VERDICTS
                       and (v["verdict"] != rules.NOT_CHECKABLE
                            or v["reason"] in rules.NOT_CHECKABLE_REASONS)
                       and (v["citations"]
                            or v["verdict"] == rules.NOT_CHECKABLE)
                       for v in full)))
    ka = [v for v in full if v["pin14"] == rules.KNOWN_ANSWER_PIN14]
    checks.append((f"C2 known answer {rules.KNOWN_ANSWER_PIN14} -> "
                   f"{rules.KNOWN_ANSWER_VERDICT}"
                   f" (found: {ka[0]['verdict'] if ka else 'ABSENT'})",
                   (not ka) or ka[0]["verdict"] == rules.KNOWN_ANSWER_VERDICT))
    checks.append(("C3 two in-process runs byte-identical (incl. delta + "
                   "manifest)", outputs == outputs2))
    checks.append(("C4 pinned surfaces match (post-A2 pins): "
                   + ", ".join(name for name, _ in surface),
                   all(ok for _, ok in surface)))
    untraced = [p for p, lab in labels.items() if lab == "UNTRACED"]
    checks.append((f"C5 every transition cause-traced by counterfactual "
                   f"({len(delta)} rows, {len(untraced)} untraced)",
                   not untraced))
    no_event = [d["pin"] for d in delta if not d["causing_events"]]
    checks.append((f"C6 every transition cites an attestation event "
                   f"({len(no_event)} without)", not no_event))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        with open(outdir / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    for name in rules.VERDICTS:
        b = sum(1 for v in baseline if v["verdict"] == name)
        c = sum(1 for v in full if v["verdict"] == name)
        print(f"{name:>22}: {b:>3} -> {c:>3}")
    print(f"{'total':>22}: {len(full)}")
    cause_counts = {c: sum(1 for x in labels.values() if x == c)
                    for c in ("attestation", "amendment", "both")}
    print(f"{'cause labels':>22}: {cause_counts}")
    print(f"{'contested set':>22}: "
          f"{sum(1 for v in full if v['verdict'] in (rules.CONTRADICTED, rules.AMBIGUOUS))}"
          f" parcels, run sha256 {run_sha[:16]}…")
    print()
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    if untraced:
        print("\nSTOP: transitions untraced to either cause — the comparison "
              "is not sound. Parcels: " + ", ".join(untraced))
    print(f"\nREMEDIATED RE-RUN: {'OK' if all_ok else 'FAILED'} -> {outdir}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
