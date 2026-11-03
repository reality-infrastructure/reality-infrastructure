"""THE ARENA run (PREREG A18, R89–R97): Proof of Outcome for any address.

Takes one pinned arena capture (adapters/agent_arena.py), reads every pinned page of fills
and funding (gzip, one HTTP response body a line, byte-for-byte), refuses any page that does
not hash to its pin (S84), grades every cohort address by the founder's document
(SETTLED.md) in a window that opened after the observation, puts the operator's RECORD row
(its own pages under the same grader, plus its committed run files reloaded through
RightsPipeline.load) and the forks' PAPER rows (pinned marks files) in the same table,
submits every event through the unmodified engine as ONE new log (`run_ARENA_<cohort>_<as_of>.ri`),
proves inclusion, writes the run file and reloads it, and renders the arena
(`arena_<cohort>_<as_of>.json` / `.md` / `.html`) as a pure function of the events.

No network. No clock. No reasoning as input (R96). No venue number recomputed. No trade.

Usage:
    python -m rights_events.agent_arena --capture CAPTURE [--run-file RI ...]
        [--out RUN_FILE] [--arena-out PREFIX]
    python -m rights_events.agent_arena --verify --run RUN_FILE
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import sys
from decimal import Decimal
from pathlib import Path

from rights_events.adapters.agent_arena import (
    FILLS_CLAIMANT, GRADER_CLAIMANT, STATUS_FULL, STATUS_NONE, STATUS_PAPER, STATUS_PARTIAL,
    STATUS_RECORD, STATUS_REFUSED, VENUE_CLAIMANT, parse_arena_capture, ranking_event,
    settled_event, sha256_hex,
)
from rights_events.adapters.common import AdapterError
from rights_events.agent_board import record_run_files, summarize_record
from rights_events.pipeline import RightsPipeline
from rights_events.schema import EPType, EventType, RightsEvent
from rights_events.trader_record import _all_inclusions_verify, verify_run

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
RECORD_SOURCE_URL = ("https://github.com/reality-infrastructure/reality-infrastructure/"
                     "tree/contract/agent-record/reference-implementation/rights_events/"
                     "fixtures/agent_record")
HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_EXPLORER = "https://app.hyperliquid.xyz/explorer/tx/"
VENUE_NAME = "gdex.pro HyperLiquid PnL boards"
VERIFY_COMMAND = ("python -m rights_events.agent_arena --verify --run "
                  "rights_events/fixtures/agent_record/<run file>")
STATUS_TEXT = {
    STATUS_FULL: "Every fill in the window the public API holds was served; ranked.",
    STATUS_PARTIAL: ("The public API's horizon (the 10 000 most recent fills) cut the window; "
                     "the figures are of the fills served; unranked."),
    STATUS_NONE: ("Zero fills served in the window: nothing settled under this address on "
                  "the perp L1 as the public API serves it; unranked."),
    STATUS_REFUSED: "A pinned page did not hash to its pin (S84); no figure is shown.",
    STATUS_RECORD: ("The operator's own account: the same grader over its own pages, beside "
                    "its committed run files that re-verify offline with L1 hashes."),
    STATUS_PAPER: ("A paper fork of the contract marked on the environment tape: net basis "
                   "points of its episodes inside the window, never a USD figure."),
}


def read_pages(path: Path) -> list[bytes]:
    """One HTTP response body a line, gzip; returned byte-for-byte (no newline)."""
    with gzip.open(path, "rb") as fh:
        data = fh.read()
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise AdapterError(f"{path.name}: page file does not end with a newline")
    return data[:-1].split(b"\n")


def paper_rows_from_marks(doc: dict, base: Path, window: dict) -> list[dict]:
    """R91 PAPER rows: per fork, the net bps of episodes whose entry is inside the window,
    from pinned marks files (sha-checked), never a USD figure."""
    paper = doc.get("paper") or {}
    files = paper.get("files") or []
    per_fork: dict[str, list[Decimal]] = {}
    used = []
    for f in files:
        path = base / f["file"]
        data = path.read_bytes()
        if sha256_hex(data) != f["sha256"]:
            raise AdapterError(f"{f['file']} does not hash to its pin (S84)")
        used.append({"file": f["file"], "sha256": f["sha256"]})
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line, parse_float=Decimal)
            if r.get("in_sample"):
                continue
            t = int(r["entry_ms"])
            if t < window["t0_ms"] or t > window["t1_ms"]:
                continue
            per_fork.setdefault(str(r["fork"]), []).append(Decimal(str(r["net_bps"])))
    rows = []
    for fork in sorted(per_fork):
        nets = per_fork[fork]
        rows.append({"status": STATUS_PAPER, "fork": fork, "episodes": len(nets),
                     "sum_net_bps": sum(nets, Decimal(0)),
                     "mean_net_bps": sum(nets, Decimal(0)) / Decimal(len(nets))})
    return [{"files": used, "rows": rows}] if files else []


def build(capture_path: Path, run_paths: list[Path] | None = None):
    """-> (pipeline, events, indices, doc, refused, loaded_record)."""
    text = capture_path.read_text(encoding="utf-8")
    doc, boards = parse_arena_capture(text)
    base = capture_path.parent
    actor_id = doc["actor"]["actor_id"]
    settled: list[RightsEvent] = []
    refused: list[dict] = []
    record_settled = None
    rows = doc.get("rows")
    if not isinstance(rows, list):
        raise AdapterError("Document has no rows list")
    for row in rows:
        address = row.get("address") if isinstance(row, dict) else None
        try:
            fills = read_pages(base / row["fills_file"])
            funding = read_pages(base / row["funding_file"])
            ev = settled_event(doc, boards, row, fills, funding, HL_INFO_URL)
        except (AdapterError, OSError, KeyError, TypeError) as exc:
            refused.append({"address": str(address), "reason": str(exc)})
            continue
        if isinstance(address, str) and address.lower() == actor_id.lower():
            record_settled = ev
        else:
            settled.append(ev)
    record_row = None
    loaded = {}
    if record_settled is not None:
        paths = run_paths if run_paths is not None else record_run_files()
        summary, loaded = summarize_record(paths, actor_id)
        c = record_settled.claim
        record_row = {
            "status": STATUS_RECORD, "address": actor_id, "event_id": record_settled.event_id,
            "coverage": c["coverage"], "fills": c["fills"],
            "realized_ex_funding": c["realized_ex_funding"], "funding": c["funding"],
            "net_with_funding": c["net_with_funding"],
            "open_at_window_end": c["open_at_window_end"],
            "first_tx": c["first_tx"], "last_tx": c["last_tx"],
            "run_files": [{**{k: f[k] for k in ("file", "sha256", "root", "events",
                                                "cryptographically_signed")},
                           "mode": "/".join(sorted(set(f["modes"])))}
                          for f in summary["run_files"]],
            "tx_hashes": sorted({h for f in summary["run_files"] for h in f["tx_hashes"]}),
            "settled_pairs_on_record": {
                "PAPER": sum(1 for f in summary["run_files"] for r in f["realized"]
                             if r["mode"] == "PAPER"),
                "LIVE": sum(1 for f in summary["run_files"] for r in f["realized"]
                            if r["mode"] == "LIVE")},
        }
    paper = paper_rows_from_marks(doc, _FIXTURES, boards.claim["window"])
    ranking = ranking_event(boards, settled + ([record_settled] if record_settled else []),
                            refused, record_row, paper, RECORD_SOURCE_URL, VERIFY_COMMAND)
    events = sorted([boards, *settled, *([record_settled] if record_settled else []), ranking],
                    key=lambda e: (e.observed_date, e.event_id))
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)
    return pipeline, events, indices, doc, refused, loaded


def trace_ranking(ranking: RightsEvent, settled: list[RightsEvent]) -> list[str]:
    """S86 (as S20): every figure the ranking shows is a claim value of a settled event and
    every sum equals its addends."""
    by_id = {e.event_id: e for e in settled}
    missing = []
    c = ranking.claim
    for r in c["ranked"] + c["unranked"]:
        e = by_id.get(r["event_id"])
        if e is None:
            missing.append(f"{r['address']}: no settled event")
            continue
        for k in ("realized_ex_funding", "funding", "net_with_funding", "fills"):
            if r[k] != e.claim[k]:
                missing.append(f"{r['address']}.{k} {r[k]} != {e.claim[k]}")
        if e.claim["realized_ex_funding"] != e.claim["closed_pnl"] - e.claim["fees"]:
            missing.append(f"{r['address']}: realized != closedPnl - fees")
        if e.claim["net_with_funding"] != e.claim["realized_ex_funding"] + e.claim["funding"]:
            missing.append(f"{r['address']}: net != realized + funding")
        daily = sum((d["net"] for d in e.claim["daily"]), Decimal(0))
        if daily != e.claim["net_with_funding"]:
            missing.append(f"{r['address']}: daily series {daily} != net {e.claim['net_with_funding']}")
    for i, r in enumerate(c["ranked"]):
        if r["rank"] != i + 1:
            missing.append(f"rank {r['rank']} at position {i + 1}")
        if i and c["ranked"][i - 1]["net_with_funding"] < r["net_with_funding"]:
            missing.append(f"ranking not descending at {r['address']}")
    return missing


# --- the arena, a pure function of the events ----------------------------------------------

def _s(x) -> str:
    if isinstance(x, Decimal):
        return format(x, "f")
    return str(x)


def render_arena(doc: dict, events: list[RightsEvent], run_file_name: str,
                 run_root_hex: str) -> dict:
    boards = next(e for e in events if e.claimant == VENUE_CLAIMANT)
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    settled = {e.event_id: e for e in events if e.claimant == FILLS_CLAIMANT}
    shown = {a["address"].lower(): a for a in boards.claim["addresses_verbatim"]}
    rc = ranking.claim

    def displayed(address: str) -> dict:
        a = shown.get(address.lower())
        if not a:
            return {}
        return {w: {"rank": d["rank"], "pnl": _s(d["pnl"]), "roi": _s(d["roi"]),
                    "vlm": _s(d["vlm"])} for w, d in a["displayed"].items()}

    def row(r: dict, status: str) -> dict:
        e = settled[r["event_id"]]
        c = e.claim
        return {
            "status": status, "rank": r.get("rank"), "address": c["address"],
            "displayed_at_observation": displayed(c["address"]),
            "account_value_at_observation": _s(shown[c["address"].lower()]["account_value"])
            if c["address"].lower() in shown else None,
            "fills": c["fills"], "fills_served": c["fills_served"],
            "closed_pnl": _s(c["closed_pnl"]), "fees": _s(c["fees"]),
            "realized_ex_funding": _s(c["realized_ex_funding"]),
            "funding": _s(c["funding"]), "funding_rows": c["funding_rows"],
            "net_with_funding": _s(c["net_with_funding"]),
            "open_at_window_end": {k: _s(v) for k, v in c["open_at_window_end"].items()},
            "first_tx": c["first_tx"], "last_tx": c["last_tx"],
            "coverage_reason": c["coverage_reason"],
            "daily": [{"day": d["day"], "net": _s(d["net"])} for d in c["daily"]],
            "fills_file": c["fills_file"], "funding_file": c["funding_file"],
            "pages": len(c["fills_pages"]), "event_id": e.event_id,
        }

    rows = [row(r, STATUS_FULL) for r in rc["ranked"]]
    rows += [row(r, r["status"]) for r in rc["unranked"]]
    rows += [{"status": STATUS_REFUSED, "address": r["address"], "reason": r["reason"]}
             for r in rc["refused"]]
    record = None
    if rc["record_row"]:
        rr = rc["record_row"]
        e = settled[rr["event_id"]]
        record = {**row({"event_id": rr["event_id"]}, STATUS_RECORD),
                  "coverage": rr["coverage"], "run_files": rr["run_files"],
                  "tx_hashes": rr["tx_hashes"],
                  "explorer_urls": [HL_EXPLORER + h for h in rr["tx_hashes"]],
                  "settled_pairs_on_record": rr["settled_pairs_on_record"],
                  "event_id": e.event_id}
    paper = []
    for block in rc["paper_rows"]:
        for p in block["rows"]:
            paper.append({**p, "sum_net_bps": _s(p["sum_net_bps"]),
                          "mean_net_bps": _s(p["mean_net_bps"]), "files": block["files"]})
    win = boards.claim["window"]
    return {
        "kind": "proof_of_outcome_arena",
        "cohort_date": boards.claim["cohort_date"],
        "as_of": rc["as_of_date"],
        "window": dict(win),
        "statuses": dict(STATUS_TEXT),
        "venue": {"name": VENUE_NAME, "source_url": boards.source_url,
                  "payload_file": boards.claim["payload_file"],
                  "payload_sha256": boards.claim["payload_sha256"],
                  "observed_ms": boards.claim["observed_ms"],
                  "rows_per_window": boards.claim["rows_per_window"],
                  "addresses": boards.claim["addresses"],
                  "what_is_not_done": boards.claim["what_is_not_done"]},
        "counts": rc["counts"],
        "median_net_full": _s(rc["median_net_full"]) if rc["median_net_full"] is not None else None,
        "share_positive_full": _s(rc["share_positive_full"]) if rc["share_positive_full"] is not None else None,
        "rows": rows,
        "record_row": record,
        "paper_rows": paper,
        "settled_rule": ("SETTLED.md: realized_ex_funding = sum closedPnl - sum fee (fee includes "
                         "builderFee); net_with_funding adds sum funding.usdc; positions open at "
                         "the window's end are counted, never valued"),
        "arena_run": {"file": run_file_name, "root": run_root_hex,
                      "events": [e.event_id for e in events],
                      "record_source_url": ranking.source_url,
                      "verify_command": rc["verify_command"]},
    }


def render_markdown(m: dict) -> str:
    w = m["window"]
    lines = [
        f"# Proof of Outcome — the arena, cohort {m['cohort_date']}, as of {m['as_of']}",
        "",
        f"{m['venue']['name']}: {m['venue']['addresses']} unique addresses across "
        f"{', '.join(f'{k} {v}' for k, v in m['venue']['rows_per_window'].items())} rows, "
        f"carried verbatim from `{m['venue']['payload_file']}` (sha256 `{m['venue']['payload_sha256']}`), "
        f"observed ms {m['venue']['observed_ms']}.",
        "",
        f"Window: {w['t0_date']} 00:00:00.000Z to {w['t1_date']} 23:59:59.999Z ({w['days']} days; "
        f"started {str(w['started']).lower()}, complete {str(w['complete']).lower()}). "
        "Rows observed on the cohort date are graded on fills from the next day onward, never on that day.",
        "",
        f"{m['settled_rule']}.",
        "",
    ]
    for k, v in m["statuses"].items():
        lines.append(f"- **{k}** — {v}")
    lines += ["", f"Counts: {', '.join(f'{k} {v}' for k, v in m['counts'].items())}. "
              f"Median net of FULL rows: {m['median_net_full']}. Share of FULL rows net-positive: "
              f"{m['share_positive_full']}.", "",
              "## The arena", "",
              "| status | rank | address | displayed week pnl at observation | fills | realized ex funding (USD) | funding (USD) | net with funding (USD) | open at window end | coverage |",
              "|---|---:|---|---:|---:|---:|---:|---:|---|---|"]
    for r in m["rows"]:
        if r["status"] == STATUS_REFUSED:
            lines.append(f"| {r['status']} | | `{r['address']}` | | | | | | | {r['reason']} |")
            continue
        wk = r["displayed_at_observation"].get("week", {}).get("pnl", "")
        lines.append(f"| {r['status']} | {r['rank'] or ''} | `{r['address']}` | {wk} | {r['fills']} | "
                     f"{r['realized_ex_funding']} | {r['funding']} | {r['net_with_funding']} | "
                     f"{', '.join(f'{k} {v}' for k, v in r['open_at_window_end'].items()) or 'none'} | "
                     f"{r['coverage_reason']} |")
    if m["record_row"]:
        r = m["record_row"]
        lines += ["", "## The operator's row (RECORD)", "",
                  f"`{r['address']}` — coverage {r['coverage']}; fills {r['fills']}; realized ex funding "
                  f"{r['realized_ex_funding']} USD; funding {r['funding']}; net with funding "
                  f"{r['net_with_funding']} USD; settled pairs on the record PAPER "
                  f"{r['settled_pairs_on_record']['PAPER']} · LIVE {r['settled_pairs_on_record']['LIVE']}.",
                  "", "| run file | mode | events | signed | root |", "|---|---|---:|---:|---|"]
        for f in r["run_files"]:
            lines.append(f"| `{f['file']}` | {f['mode']} | {f['events']} | {f['cryptographically_signed']} | `{f['root']}` |")
        lines += ["", "Chain fills (HyperLiquid L1):", ""] + [f"- {u}" for u in r["explorer_urls"]]
    if m["paper_rows"]:
        lines += ["", "## The paper population (PAPER, net bps, never USD)", "",
                  "| fork | episodes in window | sum net bps | mean net bps |", "|---|---:|---:|---:|"]
        for p in m["paper_rows"]:
            lines.append(f"| {p['fork']} | {p['episodes']} | {p['sum_net_bps']} | {p['mean_net_bps']} |")
    lines += ["", f"Verify this run offline: `{m['arena_run']['verify_command']}`", "",
              f"This arena's own run: `{m['arena_run']['file']}`, root `{m['arena_run']['root']}`, "
              f"{len(m['arena_run']['events'])} events; record source {m['arena_run']['record_source_url']}", ""]
    return "\n".join(lines)


_CSS = """
:root { --bg:#f5f6f8; --surface:#fff; --fg:#15202b; --muted:#5b6672; --rule:#d9dee5; --accent:#0e6e7a;
  --full-bg:#e3f3e8; --full-fg:#14532d; --partial-bg:#fdf1dc; --partial-fg:#7a4b00; --none-bg:#eef0f3; --none-fg:#44505c;
  --refused-bg:#fbe3e3; --refused-fg:#7f1d1d; --record-bg:#e0ecfb; --record-fg:#1e3a8a; --paper-bg:#efe9fb; --paper-fg:#4c1d95;
  --mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace; --body:"Segoe UI", system-ui, -apple-system, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#121820; --surface:#1a222c; --fg:#e6ebf0; --muted:#98a4b1; --rule:#2c3743; --accent:#5fc3cf;
  --full-bg:#16321f; --full-fg:#a6e3b8; --partial-bg:#3a2a0e; --partial-fg:#f3c77a; --none-bg:#242e39; --none-fg:#b4bec8; --refused-bg:#3b1515; --refused-fg:#f5a3a3;
  --record-bg:#172a4a; --record-fg:#a9c7f5; --paper-bg:#2a1f45; --paper-fg:#cdb8f7; color-scheme: dark } }
:root[data-theme="dark"] { --bg:#121820; --surface:#1a222c; --fg:#e6ebf0; --muted:#98a4b1; --rule:#2c3743; --accent:#5fc3cf;
  --full-bg:#16321f; --full-fg:#a6e3b8; --partial-bg:#3a2a0e; --partial-fg:#f3c77a; --none-bg:#242e39; --none-fg:#b4bec8; --refused-bg:#3b1515; --refused-fg:#f5a3a3;
  --record-bg:#172a4a; --record-fg:#a9c7f5; --paper-bg:#2a1f45; --paper-fg:#cdb8f7; color-scheme: dark }
body { background:var(--bg); color:var(--fg); font-family:var(--body); line-height:1.5; margin:0;
  padding-left:max(16px, env(safe-area-inset-left,0px)); padding-right:max(16px, env(safe-area-inset-right,0px)); padding-block:24px 48px; }
main { max-width:1120px; margin:0 auto; display:grid; gap:26px; }
h1 { font-size:clamp(1.5rem,3.5vw,2.2rem); margin:0; letter-spacing:-0.01em; text-wrap:balance; }
h2 { font-size:1.1rem; margin:0 0 10px; } p { margin:0; max-width:72ch; } .lead { color:var(--muted); }
.eyebrow { font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
.chip { display:inline-block; font:600 .7rem/1 var(--body); letter-spacing:.04em; padding:5px 8px; border-radius:3px; text-transform:uppercase; white-space:nowrap; }
.chip.FULL{background:var(--full-bg);color:var(--full-fg)} .chip.PARTIAL{background:var(--partial-bg);color:var(--partial-fg)}
.chip.NONE{background:var(--none-bg);color:var(--none-fg)} .chip.REFUSED{background:var(--refused-bg);color:var(--refused-fg)}
.chip.RECORD{background:var(--record-bg);color:var(--record-fg)} .chip.PAPER{background:var(--paper-bg);color:var(--paper-fg)}
.legend { display:grid; gap:8px; } .legend div { display:grid; grid-template-columns:auto 1fr; gap:12px; align-items:start; }
.wrap { overflow-x:auto; border:1px solid var(--rule); background:var(--surface); }
table { border-collapse:collapse; width:100%; font-size:.84rem; font-variant-numeric:tabular-nums; }
th, td { padding:7px 9px; border-bottom:1px solid var(--rule); text-align:left; vertical-align:top; }
th { font-weight:600; color:var(--muted); font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; }
td.num, th.num { text-align:right; font-family:var(--mono); } .mono { font-family:var(--mono); font-size:.8rem; word-break:break-all; }
tr:last-child td { border-bottom:0; } .facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
.facts .k { font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); } .facts .v { font-family:var(--mono); font-size:1.02rem; }
.card { background:var(--surface); border:1px solid var(--rule); border-left:4px solid var(--record-fg); padding:18px; display:grid; gap:14px; }
a { color:var(--accent); } code { font-family:var(--mono); font-size:.8rem; background:var(--none-bg); padding:1px 4px; border-radius:3px; }
footer { color:var(--muted); font-size:.85rem; display:grid; gap:6px; } svg text { font-family:var(--mono); font-size:11px; fill:var(--muted); }
figure { margin:0; background:var(--surface); border:1px solid var(--rule); padding:12px; } figcaption { color:var(--muted); font-size:.85rem; margin-top:6px; }
"""


def _chart(series: list[tuple[str, list[dict]]], days: list[str], title: str) -> str:
    """One inline SVG: cumulative net per day per series, linear axes, nothing smoothed.
    A pure function of the claims' daily lists."""
    if not series or not days:
        return ""
    W, H, L, R, T, B = 760, 300, 70, 16, 16, 34
    cum: dict[str, list[Decimal]] = {}
    lo = hi = Decimal(0)
    for name, daily in series:
        by = {d["day"]: Decimal(d["net"]) for d in daily}
        run = Decimal(0)
        pts = []
        for d in days:
            run += by.get(d, Decimal(0))
            pts.append(run)
            lo, hi = min(lo, run), max(hi, run)
        cum[name] = pts
    if hi == lo:
        hi = lo + 1
    span = hi - lo

    def x(i: int) -> float:
        return L + (W - L - R) * (i / max(1, len(days) - 1))

    def y(v: Decimal) -> float:
        return T + (H - T - B) * float((hi - v) / span)

    palette = ["#0e6e7a", "#b45309", "#1e3a8a", "#4c1d95", "#14532d", "#7f1d1d", "#5b6672"]
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{html.escape(title)}">']
    zero = y(Decimal(0))
    out.append(f'<line x1="{L}" y1="{zero:.1f}" x2="{W - R}" y2="{zero:.1f}" stroke="currentColor" stroke-opacity=".35"/>')
    for v in (hi, lo):
        out.append(f'<text x="{L - 6}" y="{y(v):.1f}" text-anchor="end" dominant-baseline="middle">{format(v, ".2f")}</text>')
    for i, d in enumerate(days):
        if i == 0 or i == len(days) - 1 or len(days) <= 10:
            out.append(f'<text x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{html.escape(d[5:])}</text>')
    for k, (name, _d) in enumerate(series):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(cum[name]))
        color = palette[k % len(palette)]
        out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        out.append(f'<text x="{W - R - 2}" y="{y(cum[name][-1]):.1f}" text-anchor="end" dominant-baseline="middle" fill="{color}">{html.escape(name)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def render_html(m: dict) -> str:
    e = html.escape
    w = m["window"]
    days = []
    d0 = w["t0_date"]
    from datetime import date, timedelta
    start = date.fromisoformat(d0)
    for i in range(w["days"]):
        days.append((start + timedelta(days=i)).isoformat())
    full_rows = [r for r in m["rows"] if r["status"] == STATUS_FULL]
    legend = "\n".join(f'<div><span class="chip {k}">{e(k)}</span><p>{e(v)}</p></div>'
                       for k, v in m["statuses"].items())

    def tr(r: dict) -> str:
        if r["status"] == STATUS_REFUSED:
            return (f'<tr><td><span class="chip REFUSED">REFUSED</span></td><td></td><td class="mono">{e(r["address"])}</td>'
                    f'<td colspan="7">{e(r["reason"])}</td></tr>')
        wk = r["displayed_at_observation"].get("week", {}).get("pnl", "")
        opened = ", ".join(f"{k} {v}" for k, v in r["open_at_window_end"].items()) or "none"
        return (f'<tr><td><span class="chip {e(r["status"])}">{e(r["status"])}</span></td>'
                f'<td class="num">{r["rank"] or ""}</td><td class="mono">{e(r["address"])}</td>'
                f'<td class="num">{e(wk)}</td><td class="num">{r["fills"]}</td>'
                f'<td class="num">{e(r["realized_ex_funding"])}</td><td class="num">{e(r["funding"])}</td>'
                f'<td class="num"><strong>{e(r["net_with_funding"])}</strong></td><td>{e(opened)}</td>'
                f'<td class="lead">{e(r["coverage_reason"])}</td></tr>')

    rows_html = "\n".join(tr(r) for r in m["rows"])
    chart_cohort = _chart([(r["address"][:10], r["daily"]) for r in full_rows[:7]], days,
                          "Cumulative net with funding, FULL rows, USD") if full_rows else ""
    record_html = ""
    if m["record_row"]:
        r = m["record_row"]
        run_rows = "\n".join(f'<tr><td class="mono">{e(f["file"])}</td><td>{e(f["mode"])}</td><td class="num">{f["events"]}</td>'
                             f'<td class="num">{f["cryptographically_signed"]}</td><td class="mono">{e(f["root"])}</td></tr>'
                             for f in r["run_files"])
        tx = "\n".join(f'<li><a class="mono" href="{e(u)}" rel="noopener">{e(u)}</a></li>' for u in r["explorer_urls"])
        chart_record = _chart([("operator", r["daily"])], days, "Cumulative net with funding, the operator's row, USD")
        record_html = f"""
  <section class="card" aria-label="The operator's row">
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span class="chip RECORD">RECORD</span><span class="mono">{e(r['address'])}</span><span class="lead">coverage {e(r['coverage'])} · the same grader as every row above</span></div>
    <div class="facts">
      <div><div class="k">fills in window</div><div class="v">{r['fills']}</div></div>
      <div><div class="k">realized ex funding (USD)</div><div class="v">{e(r['realized_ex_funding'])}</div></div>
      <div><div class="k">funding (USD)</div><div class="v">{e(r['funding'])}</div></div>
      <div><div class="k">net with funding (USD)</div><div class="v">{e(r['net_with_funding'])}</div></div>
      <div><div class="k">settled pairs on the record</div><div class="v">PAPER {r['settled_pairs_on_record']['PAPER']} · LIVE {r['settled_pairs_on_record']['LIVE']}</div></div>
    </div>
    <figure>{chart_record}<figcaption>The operator's cumulative net with funding by day over the window, USD. Linear, nothing smoothed.</figcaption></figure>
    <div class="wrap"><table><thead><tr><th>run file</th><th>mode</th><th class="num">events</th><th class="num">signed</th><th>event-log root</th></tr></thead><tbody>
{run_rows}
    </tbody></table></div>
    <div><div class="eyebrow" style="margin-bottom:6px">Chain fills on the record, HyperLiquid L1</div><ul style="margin:0;padding-left:18px;display:grid;gap:4px">
{tx}
    </ul></div>
  </section>"""
    paper_html = ""
    if m["paper_rows"]:
        prow = "\n".join(f'<tr><td><span class="chip PAPER">PAPER</span></td><td class="mono">{e(p["fork"])}</td><td class="num">{p["episodes"]}</td>'
                         f'<td class="num">{e(p["sum_net_bps"])}</td><td class="num">{e(p["mean_net_bps"])}</td></tr>' for p in m["paper_rows"])
        files = ", ".join(f'<code>{e(f["file"])}</code>' for f in m["paper_rows"][0]["files"])
        paper_html = f"""
  <section>
    <h2>The paper population, same window</h2>
    <p class="lead" style="margin-bottom:10px">Net basis points of each fork's episodes whose entry falls inside the window, from the pinned marks files {files}. Never a USD figure: paper pays no fill.</p>
    <div class="wrap"><table><thead><tr><th>status</th><th>fork</th><th class="num">episodes</th><th class="num">sum net bps</th><th class="num">mean net bps</th></tr></thead><tbody>
{prow}
    </tbody></table></div>
  </section>"""
    counts = " · ".join(f"{k} {v}" for k, v in m["counts"].items())
    return f"""<title>Proof of Outcome Arena</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{_CSS}</style>
<main>
  <header style="display:grid;gap:10px">
    <div class="eyebrow">Proof of Outcome · the arena · cohort {e(m['cohort_date'])} · as of {e(m['as_of'])}</div>
    <h1>Every listed address, graded by what settled on the chain, after it was listed</h1>
    <p class="lead">{e(m['venue']['name'])}: {m['venue']['addresses']} unique addresses across its four windows, carried verbatim from <code>{e(m['venue']['payload_file'])}</code>. Each is graded on its HyperLiquid L1 fills and funding in the window {e(w['t0_date'])} to {e(w['t1_date'])} ({w['days']} days), which opened after the observation. {e(m['settled_rule'])}. {e(m['venue']['what_is_not_done'])}</p>
  </header>
  <section class="legend" aria-label="What the statuses mean">
{legend}
  </section>
  <section>
    <div class="facts">
      <div><div class="k">counts</div><div class="v" style="font-size:.9rem">{e(counts)}</div></div>
      <div><div class="k">median net, FULL rows (USD)</div><div class="v">{e(str(m['median_net_full']))}</div></div>
      <div><div class="k">share of FULL rows net-positive</div><div class="v">{e(str(m['share_positive_full']))}</div></div>
      <div><div class="k">window</div><div class="v" style="font-size:.9rem">started {str(w['started']).lower()} · complete {str(w['complete']).lower()}</div></div>
    </div>
  </section>
  {('<figure>' + chart_cohort + '<figcaption>Cumulative net with funding by day, the first seven FULL rows, USD. Linear, nothing smoothed, nothing averaged across cohorts.</figcaption></figure>') if chart_cohort else ''}
  <section>
    <h2>The arena</h2>
    <div class="wrap"><table>
      <thead><tr><th>status</th><th class="num">rank</th><th>address</th><th class="num">displayed week pnl at observation</th><th class="num">fills</th><th class="num">realized ex funding (USD)</th><th class="num">funding (USD)</th><th class="num">net with funding (USD)</th><th>open at window end</th><th>coverage</th></tr></thead>
      <tbody>
{rows_html}
      </tbody>
    </table></div>
  </section>
{record_html}
{paper_html}
  <footer>
    <div>Verify this run offline: <code>{e(m['arena_run']['verify_command'])}</code></div>
    <div>This arena's own run: <code>{e(m['arena_run']['file'])}</code>, root <span class="mono">{e(m['arena_run']['root'])}</span>, {len(m['arena_run']['events'])} events. Record source: <a href="{e(m['arena_run']['record_source_url'])}" rel="noopener">{e(m['arena_run']['record_source_url'])}</a>.</div>
    <div>Source of the boards: <a href="{e(m['venue']['source_url'])}" rel="noopener">{e(m['venue']['source_url'])}</a>, sha256 <span class="mono">{e(m['venue']['payload_sha256'])}</span>. Fills and funding: the venue's public info API, pages pinned verbatim beside the run. An independent record; not operated by or affiliated with the venue. No claim about anyone's profit is made: the table prints what the chain's public API served, with its coverage, beside what the venue displayed.</div>
  </footer>
</main>
"""


def arena_json(m: dict) -> str:
    return json.dumps(m, indent=2, default=str) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.agent_arena",
        description="The arena run: every listed address graded by what settled on the chain "
                    "after it was listed. No fold; no trade.")
    parser.add_argument("--capture", default=None)
    parser.add_argument("--run-file", action="append", default=None,
                        help="record run file(s) for the RECORD row (default: every pinned PAPER/LIVE run)")
    parser.add_argument("--out", default="agent_arena_run.ri")
    parser.add_argument("--arena-out", default=None,
                        help="prefix for arena_<cohort>_<as_of>.json/.md/.html (default: none written)")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--run", default=None)
    args = parser.parse_args(argv)

    if args.verify:
        if not args.run:
            print("ERROR: --verify requires --run RUN_FILE")
            return 2
        ok, report = verify_run(args.run)
        print(f"VERIFY {args.run}: {report}")
        print(f"RESULT: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1
    if not args.capture:
        print("ERROR: --capture is required")
        return 2

    capture = Path(args.capture)
    run_paths = [Path(p) for p in args.run_file] if args.run_file else None
    print("=" * 70)
    print("AGENT-RECORD ARENA RUN -- END TO END (PREREG A18)")
    print(f"ARENA capture: {capture.name}")
    print("Every cohort address graded on the chain's fills in a window that opened after")
    print("the observation. Pages verbatim, sha-pinned. No venue number recomputed. No trade.")
    print("=" * 70)
    print()
    pipeline, events, indices, doc, refused, loaded = build(capture, run_paths)
    boards = next(e for e in events if e.claimant == VENUE_CLAIMANT)
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    settled = [e for e in events if e.claimant == FILLS_CLAIMANT]
    print(f"Subject: {boards.subject_ids[0]}")
    print(f"Events submitted through the engine: {len(events)} "
          f"(1 boards, {len(settled)} settled, 1 ranking)")
    rc = ranking.claim
    print(f"Cohort {rc['cohort_date']}: {rc['addresses_in_cohort']} addresses; window "
          f"{rc['window']['t0_date']}..{rc['window']['t1_date']}; counts {rc['counts']}; "
          f"median FULL {rc['median_net_full']}; share positive {rc['share_positive_full']}")
    if rc["record_row"]:
        rr = rc["record_row"]
        print(f"RECORD row: fills {rr['fills']}, realized {rr['realized_ex_funding']}, "
              f"funding {rr['funding']}, net {rr['net_with_funding']}, coverage {rr['coverage']}")
    print()
    root = pipeline.event_log.root(len(pipeline.event_log))
    run_bytes = pipeline.save(args.out)
    missing = trace_ranking(ranking, settled)
    inclusions_ok = _all_inclusions_verify(pipeline)
    reload_ok, reload_report = verify_run(args.out)
    logged = set(indices)
    refs_ok = all(ref in logged for e in events for ref in e.prior_event_refs)
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    payload_path = capture.parent / boards.claim["payload_file"]
    if not payload_path.exists():
        payload_path = _FIXTURES / boards.claim["payload_file"]
    payload_ok = payload_path.exists() and \
        hashlib.sha256(payload_path.read_bytes()).hexdigest() == boards.claim["payload_sha256"]
    checks = [
        (f"C1 adapter produced {len(events)} events: 1 boards (self_asserted), {len(settled)} settled "
         f"(third_party_attested), 1 ranking, {len(disputes)} dispute, {len(signed)} cryptographically_signed",
         boards.ep_type is EPType.SELF_ASSERTED and not disputes and not signed
         and all(e.ep_type is EPType.THIRD_PARTY_ATTESTED for e in settled)),
        (f"C2 all {len(pipeline.event_log)} inclusion proofs verify against the root", inclusions_ok),
        ("C3 saved run reloads; every signature re-verifies; root unchanged",
         reload_ok and reload_report.endswith(root.hex())),
        ("C4 every prior_event_ref resolves inside this run's own log", refs_ok),
        ("C5 ranking traces: every figure is a settled event's claim value and every sum equals its addends"
         + (f" (UNTRACED: {missing[:3]})" if missing else ""), not missing),
        ("C6 the boards payload beside the capture hashes to its pin", payload_ok),
        (f"C7 refused rows: {len(refused)} (S84)" + (f" {[r['address'][:10] for r in refused]}" if refused else ""),
         True),
    ]
    print(f"Event log root: {root.hex()}")
    print(f"Run file:       {args.out} ({len(run_bytes)} bytes)")
    if args.arena_out:
        m = render_arena(doc, events, Path(args.out).name, root.hex())
        prefix = Path(args.arena_out)
        for suffix, text_out in ((".json", arena_json(m)), (".md", render_markdown(m)),
                                 (".html", render_html(m))):
            path = prefix.with_name(prefix.name + suffix)
            path.write_bytes(text_out.replace("\r\n", "\n").encode("utf-8"))
            print(f"Arena:          {path} ({path.stat().st_size} bytes)")
    print()
    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    print()
    print("Verify independently (reload + re-verify signatures + inclusions):")
    print(f"  python -m rights_events.agent_arena --verify --run {args.out}")
    print()
    print(f"AGENT-RECORD ARENA RUN: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
