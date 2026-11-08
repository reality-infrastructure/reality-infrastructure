"""THE COPIER'S GRADE — the feed (PREREG A28, R118–R122, S99–S100).

For every address on the venue's boards, one row a day, as a PURE FUNCTION of the pinned arena
outputs: for each cohort directory under arena/, the newest arena_<cohort>_<as_of>.json and, if
present, the newest screen_<cohort>_<as_of>.json; plus SETTLED.md's sha256 and the feed's own
--as-of. No network, no clock, no payload re-read, no venue call, nothing recomputed.

  R119  status by the deploy-or-throw-out rule (the panel, 2026-schulman-millidge-oneill.md @ 45:03):
        window complete:  KEEP      coverage FULL and net_with_funding > 0
                          DROP      coverage FULL and net_with_funding <= 0, or coverage NONE
                          UNDECIDED coverage PARTIAL (the sensor's gap, never a verdict on the leader)
        window open:      OPEN      interim figures shown, no status
  R120  the run across listings: over the cohorts an address was listed in, by cohort date, completed
        windows only: KEEP -> run + 1, DROP -> 0, UNDECIDED -> unchanged. No badge, no threshold.
  R121  beside the grade: the venue's displayed pnl at listing (verbatim), verified net, realized ex
        funding, fills, tx hashes, open positions at the window's end (a count), the coverage reason,
        the screen's verdict and failing letters or "not screened (window open until <t1>)".
  R122  feed_<as_of>.json / .md are the day's pins; feed_latest.json is byte-equal to the newest dated
        file (S100); the arena page carries the same table; the routine writes it daily (step 3e).
  S99   a cohort's newest arena file is newer than the feed's as-of, lacks settled_rule or
        arena_run.root, or its screen's arena_sha256 is not the arena file's -> REFUSED, nothing written.

Usage:
    python -m rights_events.arena_feed --as-of YYYY-MM-DD [--arena-dir DIR] [--out-dir DIR] [--settled FILE]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
ARENA_DIR = _FIXTURES / "arena"
FEED_DIR = ARENA_DIR / "feed"
SETTLED = Path(__file__).resolve().parents[1] / "contracts" / "agent_record" / "SETTLED.md"
FEED_KIND = "proof_of_outcome_copiers_grade"
STATUS_KEEP, STATUS_DROP, STATUS_UNDECIDED, STATUS_OPEN = "KEEP", "DROP", "UNDECIDED", "OPEN"
STATUSES = (STATUS_KEEP, STATUS_DROP, STATUS_UNDECIDED, STATUS_OPEN)
ENDPOINT = ("https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/"
            "contract/agent-record/reference-implementation/rights_events/fixtures/agent_record/arena/feed/feed_latest.json")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ARENA = re.compile(r"^arena_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
_SCREEN = re.compile(r"^screen_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
_DISPLAY_WINDOWS = ("day", "week", "month", "allTime")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def newest_outputs(arena_dir: Path) -> dict[str, dict]:
    """Per cohort directory: the newest arena file by as_of and the newest screen file, if any."""
    out: dict[str, dict] = {}
    for d in sorted(p for p in arena_dir.iterdir() if p.is_dir() and _DAY.match(p.name)):
        arenas, screens = [], []
        for f in d.iterdir():
            m = _ARENA.match(f.name)
            if m and m.group(1) == d.name:
                arenas.append((m.group(2), f))
            m = _SCREEN.match(f.name)
            if m and m.group(1) == d.name:
                screens.append((m.group(2), f))
        if not arenas:
            continue
        out[d.name] = {"arena": max(arenas)[1], "screen": max(screens)[1] if screens else None}
    return out


def _decimal(s) -> Decimal:
    try:
        return Decimal(str(s))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AdapterError(f"S99: not a decimal string: {s!r}") from exc


def status_for(coverage: str, net: str, window_complete: bool) -> tuple[str, str]:
    """R119. Returns (status, reason)."""
    if not window_complete:
        return STATUS_OPEN, "window open: interim figures, no status (R119)"
    if coverage == "FULL":
        if _decimal(net) > 0:
            return STATUS_KEEP, "window complete, coverage FULL, verified net > 0 (R119)"
        return STATUS_DROP, "window complete, coverage FULL, verified net <= 0 (R119)"
    if coverage == "NONE":
        return STATUS_DROP, "window complete, nothing settled under the address in the window (R119)"
    if coverage == "PARTIAL":
        return STATUS_UNDECIDED, "window complete but the sensor did not see the whole window; a statement about the sensor, not the leader (R119)"
    # REFUSED (S84: a page off its pin) carries no figure: the sensor's failure, disclosed, never a verdict
    return STATUS_UNDECIDED, "window complete but a pinned page was refused (S84); no figure; a statement about the pins, not the leader (R119)"


def _displayed(row: dict) -> tuple[str | None, str | None]:
    d = row.get("displayed_at_observation") or {}
    for w in _DISPLAY_WINDOWS:
        if w in d and isinstance(d[w], dict) and d[w].get("pnl") is not None:
            return w, str(d[w]["pnl"])
    for w, v in d.items():
        if isinstance(v, dict) and v.get("pnl") is not None:
            return str(w), str(v["pnl"])
    return None, None


def _row(cohort: str, arena: dict, r: dict, screen_by_addr: dict[str, dict], record: bool) -> dict:
    window = arena["window"]
    complete = bool(window.get("complete"))
    coverage = r.get("coverage") if record else r.get("status")
    if coverage not in ("FULL", "PARTIAL", "NONE", "REFUSED"):
        raise AdapterError(f"S99: cohort {cohort} address {r.get('address')!r} has coverage {coverage!r}")
    status, reason = status_for(coverage, r.get("net_with_funding", "0"), complete)
    dw, dp = _displayed(r)
    sc = screen_by_addr.get(r.get("address"))
    if sc is not None:
        verdict, fails = sc.get("verdict"), list(sc.get("fails") or [])
    else:
        verdict, fails = ("not screened (window open until %s)" % window.get("t1_date")) if not complete else "not screened", []
    open_pos = r.get("open_at_window_end") or {}
    return {
        "cohort_date": cohort, "address": r.get("address"), "record": record,
        "rank": r.get("rank"), "coverage": coverage, "coverage_reason": r.get("coverage_reason"),
        "status": status, "status_reason": reason,
        "displayed_pnl_at_listing": dp, "displayed_window": dw,
        "verified_net": str(r.get("net_with_funding", "0")), "realized_ex_funding": str(r.get("realized_ex_funding", "0")),
        "funding": str(r.get("funding", "0")), "fills": r.get("fills", 0), "fills_served": r.get("fills_served", r.get("fills", 0)),
        "first_tx": r.get("first_tx"), "last_tx": r.get("last_tx"),
        "open_positions_at_window_end": len(open_pos) if isinstance(open_pos, dict) else 0,
        "screen_verdict": verdict, "screen_fails": fails,
        "window": {"t0_date": window.get("t0_date"), "t1_date": window.get("t1_date"), "complete": complete},
        "arena_as_of": arena["as_of"],
    }


def feed(as_of: str, arena_dir: Path = ARENA_DIR, settled_path: Path = SETTLED) -> dict:
    if not _DAY.match(as_of):
        raise AdapterError(f"as_of {as_of!r} is not a YYYY-MM-DD date")
    if not settled_path.exists():
        raise AdapterError("S99: SETTLED.md is missing")
    settled_sha = sha256_bytes(settled_path.read_bytes().replace(b"\r\n", b"\n"))
    outputs = newest_outputs(arena_dir)
    if not outputs:
        raise AdapterError(f"S99: no arena outputs under {arena_dir}")
    cohorts, rows = [], []
    for cohort, files in outputs.items():
        ap: Path = files["arena"]
        arena = json.loads(ap.read_text(encoding="utf-8"))
        if arena.get("as_of", "") > as_of:
            raise AdapterError(f"S99: cohort {cohort}: {ap.name} is as of {arena.get('as_of')}, later than the feed's {as_of}")
        if not arena.get("settled_rule"):
            raise AdapterError(f"S99: cohort {cohort}: {ap.name} carries no settled_rule")
        if not (arena.get("arena_run") or {}).get("root"):
            raise AdapterError(f"S99: cohort {cohort}: {ap.name} carries no arena_run.root")
        if not isinstance(arena.get("window"), dict) or "complete" not in arena["window"]:
            raise AdapterError(f"S99: cohort {cohort}: {ap.name} has no window.complete")
        arena_sha = sha256_file(ap)
        screen_by_addr: dict[str, dict] = {}
        sp: Path | None = files["screen"]
        screen_meta = None
        if sp is not None:
            screen = json.loads(sp.read_text(encoding="utf-8"))
            if screen.get("arena_sha256") != arena_sha or screen.get("arena_file") != ap.name:
                raise AdapterError(f"S99: cohort {cohort}: {sp.name} screened {screen.get('arena_file')!r} "
                                   f"sha {str(screen.get('arena_sha256'))[:12]}…, not {ap.name} sha {arena_sha[:12]}…")
            screen_by_addr = {s["address"]: s for s in screen.get("rows", []) if s.get("address")}
            screen_meta = {"file": sp.name, "sha256": sha256_file(sp), "as_of": screen.get("as_of"), "counts": screen.get("counts")}
        crow = []
        for r in arena.get("rows", []):
            crow.append(_row(cohort, arena, r, screen_by_addr, record=False))
        rr = arena.get("record_row")
        if rr and rr.get("address"):
            crow.append(_row(cohort, arena, rr, screen_by_addr, record=True))
        counts = {s: sum(1 for x in crow if x["status"] == s) for s in STATUSES}
        cov = {c: sum(1 for x in crow if x["coverage"] == c and not x["record"]) for c in ("FULL", "PARTIAL", "NONE", "REFUSED")}
        cohorts.append({"cohort_date": cohort, "arena_as_of": arena["as_of"], "arena_file": ap.name, "arena_sha256": arena_sha,
                        "arena_run_root": arena["arena_run"]["root"], "window": arena["window"], "screen": screen_meta,
                        "counts": counts, "coverage_counts": cov, "rows": len(crow), "venue": (arena.get("venue") or {}).get("name")})
        rows.extend(crow)
    # R120: the run across listings, completed windows only, by cohort date
    by_addr: dict[str, list[dict]] = {}
    for x in rows:
        by_addr.setdefault(x["address"], []).append(x)
    runs: dict[str, dict] = {}
    for addr, xs in by_addr.items():
        xs.sort(key=lambda x: x["cohort_date"])
        run = 0
        statuses = {}
        completed = 0
        for x in xs:
            statuses[x["cohort_date"]] = x["status"]
            if not x["window"]["complete"]:
                continue
            completed += 1
            if x["status"] == STATUS_KEEP:
                run += 1
            elif x["status"] == STATUS_DROP:
                run = 0
        runs[addr] = {"run": run, "cohorts_listed": len(xs), "cohorts_completed": completed, "statuses": statuses}
        for x in xs:
            x["run"] = run
            x["cohorts_listed"] = len(xs)
            x["cohorts_completed"] = completed
    rows.sort(key=lambda x: (x["cohort_date"], STATUSES.index(x["status"]), -float(_decimal(x["verified_net"])), x["address"]))
    return {
        "kind": FEED_KIND, "as_of": as_of, "settled_sha256": settled_sha, "endpoint": ENDPOINT,
        "statuses": {
            STATUS_KEEP: "window complete, coverage FULL, verified net > 0 (the panel @ 45:03: deploy it)",
            STATUS_DROP: "window complete, coverage FULL with verified net <= 0, or NONE (throw that version out)",
            STATUS_UNDECIDED: "window complete, coverage PARTIAL or a refused page: the sensor's gap, not the leader's verdict",
            STATUS_OPEN: "window not complete: interim figures, no status",
        },
        "cohorts": cohorts, "rows": rows, "runs": dict(sorted(runs.items())),
        "rules": {"R118": "a pure function of the newest pinned arena and screen outputs per cohort and SETTLED.md's sha; nothing recomputed",
                  "R119": "KEEP / DROP / UNDECIDED on completed windows, OPEN otherwise; Decimal on the arena's own strings",
                  "R120": "run across listings: KEEP +1, DROP 0, UNDECIDED unchanged; completed windows only; no badge, no threshold",
                  "R121": "displayed pnl at listing beside verified net, fills, tx hashes, open positions, coverage reason, screen verdict",
                  "R122": "feed_<as_of> pins never move; feed_latest.json is byte-equal to the newest dated file (S100)"},
        "what_is_not_claimed": "No forecast, no skill, no badge: a status by written rule over what settled on the chain after each listing, cohort by cohort, never averaged.",
    }


def _f(x) -> str:
    return "—" if x in (None, "") else str(x)


def render_markdown(m: dict) -> str:
    out = [f"# The copier's grade as of {m['as_of']} (PREREG A28)", "",
           f"SETTLED.md `{m['settled_sha256'][:16]}…`; endpoint `{m['endpoint']}`.", ""]
    for c in m["cohorts"]:
        w = c["window"]
        out.append(f"## Cohort {c['cohort_date']} — arena as of {c['arena_as_of']} (`{c['arena_file']}` `{c['arena_sha256'][:16]}…`), "
                   f"window {w.get('t0_date')} … {w.get('t1_date')} {'complete' if w.get('complete') else 'OPEN'}; "
                   f"KEEP {c['counts']['KEEP']} / DROP {c['counts']['DROP']} / UNDECIDED {c['counts']['UNDECIDED']} / OPEN {c['counts']['OPEN']}; "
                   f"coverage FULL {c['coverage_counts']['FULL']} / PARTIAL {c['coverage_counts']['PARTIAL']} / NONE {c['coverage_counts']['NONE']}"
                   + (f"; screen `{c['screen']['file']}`" if c.get("screen") else "; not screened") + ".")
        out.append("")
        out.append("| status | coverage | address | displayed pnl at listing | verified net (USD) | fills | run | screen |")
        out.append("|---|---|---|---:|---:|---:|---:|---|")
        for r in m["rows"]:
            if r["cohort_date"] != c["cohort_date"]:
                continue
            addr = r["address"] + (" (RECORD)" if r["record"] else "")
            sc = r["screen_verdict"] + (" " + ",".join(r["screen_fails"]) if r["screen_fails"] else "")
            out.append(f"| {r['status']} | {r['coverage']} | `{addr}` | {_f(r['displayed_pnl_at_listing'])} | {r['verified_net']} | {r['fills']} | {r['run']} | {sc} |")
        out.append("")
    out.append("Rules: " + "; ".join(f"**{k}** {v}" for k, v in m["rules"].items()))
    out.append("")
    out.append(m["what_is_not_claimed"])
    return "\n".join(out) + "\n"


def render_html_section(m: dict) -> str:
    """The same table for the arena page (R122). Inline-safe HTML, no scripts."""
    import html as _h
    parts = [f'<section id="copiers-grade"><h2>The copier\'s grade as of {_h.escape(m["as_of"])} (A28)</h2>',
             '<p class="lead">For every listed address: what the chain settled after the listing, beside what the board displayed at the listing, '
             'and a status by the deploy-or-throw-out rule. KEEP: window complete, every fill seen, verified net above zero. DROP: window complete and '
             'nothing settled, or net at or below zero. UNDECIDED: the sensor did not see the whole window. OPEN: the window has not closed. '
             f'Machine-readable: <code>{_h.escape(m["endpoint"])}</code>.</p>']
    for c in m["cohorts"]:
        w = c["window"]
        parts.append(f'<h3>Cohort {_h.escape(c["cohort_date"])} · arena as of {_h.escape(c["arena_as_of"])} · window '
                     f'{_h.escape(str(w.get("t0_date")))} to {_h.escape(str(w.get("t1_date")))} {"complete" if w.get("complete") else "open"} · '
                     f'KEEP {c["counts"]["KEEP"]} · DROP {c["counts"]["DROP"]} · UNDECIDED {c["counts"]["UNDECIDED"]} · OPEN {c["counts"]["OPEN"]}</h3>')
        parts.append('<div class="wrap"><table><thead><tr><th>status</th><th>coverage</th><th>address</th><th class="num">displayed pnl at listing</th>'
                     '<th class="num">verified net (USD)</th><th class="num">fills</th><th class="num">run</th><th>screen</th></tr></thead><tbody>')
        for r in m["rows"]:
            if r["cohort_date"] != c["cohort_date"]:
                continue
            sc = r["screen_verdict"] + (" " + ",".join(r["screen_fails"]) if r["screen_fails"] else "")
            parts.append(f'<tr><td><span class="chip {_h.escape(r["status"])}">{_h.escape(r["status"])}</span></td>'
                         f'<td><span class="chip {_h.escape(r["coverage"])}">{_h.escape(r["coverage"])}</span></td>'
                         f'<td class="mono">{_h.escape(r["address"])}{" (RECORD)" if r["record"] else ""}</td>'
                         f'<td class="num">{_h.escape(_f(r["displayed_pnl_at_listing"]))}</td><td class="num"><strong>{_h.escape(r["verified_net"])}</strong></td>'
                         f'<td class="num">{r["fills"]}</td><td class="num">{r["run"]}</td><td class="lead">{_h.escape(sc)}</td></tr>')
        parts.append('</tbody></table></div>')
    parts.append(f'<p class="lead">{_h.escape(m["what_is_not_claimed"])}</p></section>')
    return "\n".join(parts)


def feed_json(m: dict) -> str:
    return json.dumps(m, indent=2) + "\n"


def write_feed(m: dict, out_dir: Path) -> dict[str, str]:
    """R122: the dated pins and feed_latest.json byte-equal to the dated json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    js = feed_json(m).encode("utf-8")
    md = render_markdown(m).encode("utf-8")
    paths = {"json": out_dir / f"feed_{m['as_of']}.json", "md": out_dir / f"feed_{m['as_of']}.md", "latest": out_dir / "feed_latest.json"}
    paths["json"].write_bytes(js)
    paths["md"].write_bytes(md)
    paths["latest"].write_bytes(js)
    return {k: sha256_file(p) for k, p in paths.items()}


def check_latest(feed_dir: Path) -> str:
    """S100: feed_latest.json must be byte-equal to the newest dated feed file. Returns that file's name."""
    dated = sorted(p for p in feed_dir.glob("feed_*.json") if re.match(r"^feed_\d{4}-\d{2}-\d{2}\.json$", p.name))
    if not dated:
        raise AdapterError("S100: no dated feed file")
    latest = feed_dir / "feed_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        raise AdapterError(f"S100: feed_latest.json is not byte-equal to {dated[-1].name}")
    return dated[-1].name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.arena_feed", description="The copier's grade (PREREG A28). Pure; no network.")
    p.add_argument("--as-of", required=True)
    p.add_argument("--arena-dir", default=str(ARENA_DIR))
    p.add_argument("--out-dir", default=str(FEED_DIR))
    p.add_argument("--settled", default=str(SETTLED))
    a = p.parse_args(argv)
    try:
        m = feed(a.as_of, Path(a.arena_dir), Path(a.settled))
        shas = write_feed(m, Path(a.out_dir))
        check_latest(Path(a.out_dir))
    except AdapterError as exc:
        print(f"FEED REFUSED: {exc}")
        return 1
    print(f"COPIER'S GRADE as of {m['as_of']}: cohorts {len(m['cohorts'])}, rows {len(m['rows'])}")
    for c in m["cohorts"]:
        print(f"  {c['cohort_date']}: arena as of {c['arena_as_of']} {'complete' if c['window'].get('complete') else 'OPEN'} "
              f"KEEP {c['counts']['KEEP']} DROP {c['counts']['DROP']} UNDECIDED {c['counts']['UNDECIDED']} OPEN {c['counts']['OPEN']} (rows {c['rows']})")
    for k, v in shas.items():
        print(f"  {k} sha256 {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
