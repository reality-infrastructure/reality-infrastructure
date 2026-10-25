"""Day-4 board mirror run — the venue's self-reported week board beside the
operator's verified row (PREREG A3, R20-R25).

Takes the pinned board capture (adapters/agent_board.py), reloads the operator's
committed run files through RightsPipeline.load (signatures re-verify at intake;
a tampered file never reaches the summary — S19), derives the verified-row
summary from the reloaded events, submits BOTH Day-4 events through the
unmodified engine as ONE new log (`run_BOARD_<date>.ri`, beside the untouched
PAPER and LIVE run files — R22), proves inclusion, writes the run file and
reloads it, and renders the mirror (`board_<date>.json` / `.md` / `.html`) as a
pure function of the two events and the capture (R23). No belief is folded; no
trade is executed; no venue number is recomputed (R24).

Usage:
    python -m rights_events.agent_board [--capture CAPTURE] [--run-file RI ...]
        [--out RUN_FILE] [--mirror-out PREFIX]
    python -m rights_events.agent_board --verify --run RUN_FILE
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from decimal import Decimal
from pathlib import Path

from ri_core.serialization import decode
from rights_events.adapters.agent_board import (
    MIRROR_CLAIMANT, STATUS_SELF_REPORTED, STATUS_VERIFIED, VENUE_CLAIMANT,
    parse_board_capture, verified_row_event,
)
from rights_events.adapters.common import AdapterError
from rights_events.pipeline import PipelineError, RightsPipeline
from rights_events.schema import EPType, EventType, RightsEvent
from rights_events.trader_record import _all_inclusions_verify, verify_run

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
RECORD_SOURCE_URL = ("https://github.com/reality-infrastructure/reality-infrastructure/"
                     "tree/contract/agent-record/reference-implementation/rights_events/"
                     "fixtures/agent_record")
VENUE_NAME = "gdex.pro HyperLiquid PnL board"
HL_EXPLORER = "https://app.hyperliquid.xyz/explorer/tx/"
_STATUS_TEXT = {
    STATUS_SELF_REPORTED: ("The venue's displayed figure, carried verbatim from its "
                           "public payload. Not checked against the chain here."),
    STATUS_VERIFIED: ("Every number traces to a signed event in a committed run file "
                      "that re-verifies offline (signatures + inclusion proofs); LIVE "
                      "fills carry their HyperLiquid L1 transaction hashes."),
}


def pinned_board_captures() -> list[Path]:
    return sorted(_FIXTURES.glob("capture_BOARD_*.json"))


def record_run_files() -> list[Path]:
    """The operator's committed PAPER and LIVE run files, never a board run."""
    return sorted(_FIXTURES.glob("run_PAPER_*.ri")) + sorted(_FIXTURES.glob("run_LIVE_*.ri"))


def load_run_events(run_path: Path) -> tuple[RightsPipeline, list[RightsEvent]]:
    """Reload a run file (S19: a file that fails intake is never summarized)."""
    if run_path.name.startswith("run_BOARD_"):
        raise AdapterError(f"{run_path.name}: a board run is never its own evidence (R22)")
    try:
        pipeline = RightsPipeline.load(run_path)
    except PipelineError as exc:
        raise AdapterError(f"{run_path.name} failed to reload (S19): {exc}") from exc
    if not _all_inclusions_verify(pipeline):
        raise AdapterError(f"{run_path.name}: inclusion proofs failed (S19)")
    events = []
    for idx in range(len(pipeline.event_log)):
        obs = decode(pipeline.event_log.entry(idx))
        events.append(RightsEvent.from_dict(obs["payload"]["event"]))
    return pipeline, events


def summarize_record(run_paths: list[Path], actor_id: str) -> tuple[dict, dict]:
    """Pure data about the reloaded run files, for the verified row (R21).
    Returns (summary, {file name: events}) so the trace gate can check it."""
    subject = f"agent:{actor_id}"
    files, loaded = [], {}
    for path in run_paths:
        pipeline, events = load_run_events(path)
        if any(e.subject_ids != (subject,) for e in events):
            raise AdapterError(f"{path.name}: an event is not about {subject}")
        modes = sorted({e.claim["mode"] for e in events
                        if e.event_id.startswith("agent_record:intent:")})
        realized = [e for e in events if e.event_id.startswith("agent_record:realized:")]
        # open leg before close leg (deterministic; log order sorts by event id)
        gaps = sorted((e for e in events if e.event_id.startswith("agent_record:gap:")),
                      key=lambda e: (0 if e.event_id.endswith(":open") else 1, e.event_id))
        signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
        tx_hashes = [h for e in signed for h in e.claim["tx_hashes"]]
        files.append({
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "root": pipeline.event_log.root(len(pipeline.event_log)).hex(),
            "events": len(events),
            "cryptographically_signed": len(signed),
            "modes": modes,
            "realized": [{"event_id": e.event_id, "mode": e.claim["mode"],
                          "realized_pnl_usd": e.claim["realized_pnl_usd"],
                          "fees_usd": e.claim["fees_usd"], "bucket": e.claim["bucket"]}
                         for e in realized],
            "gaps_bps": [e.claim["gap_bps"] for e in gaps],
            "tx_hashes": tx_hashes,
            "explorer_urls": [HL_EXPLORER + h for h in tx_hashes],
        })
        loaded[path.name] = events
    return {"actor_id": actor_id, "run_files": files}, loaded


def build(capture_text: str, run_paths: list[Path]):
    """-> (pipeline, events, indices, doc, summary, loaded)."""
    doc, board = parse_board_capture(capture_text)
    actor_id = doc["actor"]["actor_id"]
    summary, loaded = summarize_record(run_paths, actor_id)
    mirror = verified_row_event(board, summary, RECORD_SOURCE_URL)
    events = sorted([board, mirror], key=lambda e: (e.observed_date, e.event_id))
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)
    return pipeline, events, indices, doc, summary, loaded


def _claim_values(claim) -> set:
    """Every scalar inside a claim, as canonical strings (for the trace gate)."""
    out = set()
    if isinstance(claim, dict):
        for v in claim.values():
            out |= _claim_values(v)
    elif isinstance(claim, (list, tuple)):
        for v in claim:
            out |= _claim_values(v)
    elif isinstance(claim, Decimal):
        out.add(str(claim))
    elif isinstance(claim, (str, int)) and not isinstance(claim, bool):
        out.add(str(claim))
    return out


def trace_verified_row(mirror: RightsEvent, loaded: dict[str, list[RightsEvent]]) -> list[str]:
    """S20: every number the verified row shows must be a claim value of an
    event in a named run file (sums are checked against their addends).
    Returns the list of untraceable values (empty = trace holds)."""
    pool = set()
    for events in loaded.values():
        for e in events:
            pool |= _claim_values(e.claim)
    missing = []
    c = mirror.claim
    for r in c["realized_events"]:
        for key in ("realized_pnl_usd", "fees_usd"):
            if str(r[key]) not in pool:
                missing.append(f"{r['event_id']}.{key}={r[key]}")
    for g in c["gaps_bps"]:
        if str(g) not in pool:
            missing.append(f"gap {g}")
    for h in c["tx_hashes"]:
        if h not in pool:
            missing.append(f"tx {h}")
    for mode, key in (("PAPER", "realized_paper_usd"), ("LIVE", "realized_live_usd")):
        total = sum((r["realized_pnl_usd"] for r in c["realized_events"]
                    if r["mode"] == mode), Decimal(0))
        if total != c[key]:
            missing.append(f"{key} {c[key]} != sum of its addends {total}")
    fees = sum((r["fees_usd"] for r in c["realized_events"] if r["mode"] == "LIVE"),
               Decimal(0))
    if fees != c["fees_live_usd"]:
        missing.append(f"fees_live_usd {c['fees_live_usd']} != {fees}")
    return missing


# --- the mirror, a pure function of (events, capture) -------------------------------

def render_mirror(doc: dict, events: list[RightsEvent], run_file_name: str,
                  run_root_hex: str) -> dict:
    board = next(e for e in events if e.claimant == VENUE_CLAIMANT)
    mirror = next(e for e in events if e.claimant == MIRROR_CLAIMANT)
    obs = doc["observation"]
    rows = [{
        "status": STATUS_SELF_REPORTED,
        "rank": r["rank"],
        "address": r["address"],
        "account_value_usdc": r["account_value_usdc"],
        "week_pnl_usdc": r["week_pnl_usdc"],
        "week_roi": r["week_roi"],
        "week_vlm": r["week_vlm"],
        "verification": _STATUS_TEXT[STATUS_SELF_REPORTED],
    } for r in doc["rows"]]
    c = mirror.claim
    verified = {
        "status": STATUS_VERIFIED,
        "address": c["actor_id"],
        "on_venue_board": c["actor_on_board"],
        "settled_pairs": c["settled_pairs"],
        "realized_paper_usd": str(c["realized_paper_usd"]),
        "realized_live_usd": str(c["realized_live_usd"]),
        "fees_live_usd": str(c["fees_live_usd"]),
        "never_summed_across_modes": True,
        "gaps_bps": [str(g) for g in c["gaps_bps"]],
        "realized_events": [{**r, "realized_pnl_usd": str(r["realized_pnl_usd"]),
                             "fees_usd": str(r["fees_usd"])} for r in c["realized_events"]],
        "run_files": c["run_files"],
        "tx_hashes": c["tx_hashes"],
        "explorer_urls": c["explorer_urls"],
        "verify_command": c["verify_command"],
        "event_id": mirror.event_id,
        "verification": _STATUS_TEXT[STATUS_VERIFIED],
    }
    return {
        "kind": "proof_of_outcome_board_mirror",
        "as_of": board.observed_date,
        "observed_ms": obs["observed_ms"],
        "statuses": dict(_STATUS_TEXT),
        "venue": {
            "name": VENUE_NAME,
            "window": obs["window"],
            "source_url": obs["source_url"],
            "payload_file": obs["payload_file"],
            "payload_sha256": obs["payload_sha256"],
            "rows": obs["rows"],
            "user_agent_rule": obs["user_agent_rule"],
            "what_is_not_done": ("No venue number is recomputed, re-ranked or corrected; "
                                 "no venue address's fills are checked (rung 3)."),
        },
        "actor": {"actor_id": c["actor_id"], "on_venue_board": c["actor_on_board"],
                  "boards_listing_actor": board.claim["boards_listing_actor"]},
        "rows": rows,
        "verified_row": verified,
        "board_run": {"file": run_file_name, "root": run_root_hex,
                      "events": [e.event_id for e in events],
                      "record_source_url": mirror.source_url},
    }


def render_markdown(m: dict) -> str:
    v = m["verified_row"]
    lines = [
        f"# Proof of Outcome — week-board mirror, {m['as_of']}",
        "",
        f"{m['venue']['name']}, `{m['venue']['window']}` window, {m['venue']['rows']} rows "
        f"carried verbatim from `{m['venue']['payload_file']}` "
        f"(sha256 `{m['venue']['payload_sha256']}`), observed ms {m['observed_ms']}.",
        "",
        f"- **self_reported** — {m['statuses']['self_reported']}",
        f"- **verified** — {m['statuses']['verified']}",
        "",
        f"{m['venue']['what_is_not_done']}",
        "",
        "## The venue's board (self_reported)",
        "",
        "| rank | address | week pnl (USDC) | week roi | account value (USDC) | status |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for r in m["rows"]:
        lines.append(f"| {r['rank']} | `{r['address']}` | {r['week_pnl_usdc']} | "
                     f"{r['week_roi']} | {r['account_value_usdc']} | {r['status']} |")
    lines += [
        "",
        "## The operator's row (verified)",
        "",
        f"`{v['address']}` — on the venue's board: **{str(v['on_venue_board']).lower()}**.",
        "",
        "| settled pairs | realized PAPER (USD) | realized LIVE (USD) | LIVE fees (USD) | sim-to-real gaps (bps) |",
        "|---|---:|---:|---:|---|",
        f"| PAPER {v['settled_pairs']['PAPER']} · LIVE {v['settled_pairs']['LIVE']} | "
        f"{v['realized_paper_usd']} | {v['realized_live_usd']} | {v['fees_live_usd']} | "
        f"{', '.join(v['gaps_bps'])} |",
        "",
        "PAPER and LIVE are different positions and are never summed.",
        "",
        "| run file | mode | events | signed | root | sha256 |",
        "|---|---|---:|---:|---|---|",
    ]
    for f in v["run_files"]:
        lines.append(f"| `{f['file']}` | {f['mode']} | {f['events']} | "
                     f"{f['cryptographically_signed']} | `{f['root']}` | `{f['sha256']}` |")
    lines += ["", "Chain fills (HyperLiquid L1):", ""]
    for u in v["explorer_urls"]:
        lines.append(f"- {u}")
    lines += [
        "",
        f"Verify any run file offline: `{v['verify_command']}`",
        "",
        f"This mirror's own run: `{m['board_run']['file']}`, root `{m['board_run']['root']}`, "
        f"events {', '.join('`' + e + '`' for e in m['board_run']['events'])}; "
        f"record source {m['board_run']['record_source_url']}",
        "",
    ]
    return "\n".join(lines)


_CSS = """
:root {
  /* ledger: cool paper, ink with a blue bias, one teal accent; semantic green only on "verified" */
  --bg: #f5f6f8; --surface: #ffffff; --fg: #15202b; --muted: #5b6672; --rule: #d9dee5;
  --accent: #0e6e7a; --verified-bg: #e3f3e8; --verified-fg: #14532d;
  --self-bg: #eef0f3; --self-fg: #44505c;
  --display: "Avenir Next", "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
  --body: "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121820; --surface: #1a222c; --fg: #e6ebf0; --muted: #98a4b1; --rule: #2c3743;
  --accent: #5fc3cf; --verified-bg: #16321f; --verified-fg: #a6e3b8;
  --self-bg: #242e39; --self-fg: #b4bec8; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121820; --surface: #1a222c; --fg: #e6ebf0; --muted: #98a4b1; --rule: #2c3743;
  --accent: #5fc3cf; --verified-bg: #16321f; --verified-fg: #a6e3b8;
  --self-bg: #242e39; --self-fg: #b4bec8; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--body); line-height: 1.5;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 24px 48px; }
main { max-width: 1040px; margin: 0 auto; display: grid; gap: 28px; }
h1 { font-family: var(--display); font-size: clamp(1.6rem, 3.5vw, 2.3rem); letter-spacing: -0.01em;
  margin: 0; text-wrap: balance; }
h2 { font-family: var(--display); font-size: 1.15rem; margin: 0 0 10px; }
p { margin: 0; max-width: 68ch; }
.lead { color: var(--muted); }
.eyebrow { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.chip { display: inline-block; font: 600 0.72rem/1 var(--body); letter-spacing: 0.04em; padding: 5px 8px;
  border-radius: 3px; text-transform: uppercase; white-space: nowrap; }
.chip.self { background: var(--self-bg); color: var(--self-fg); }
.chip.verified { background: var(--verified-bg); color: var(--verified-fg); }
.legend { display: grid; gap: 10px; }
.legend div { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
.wrap { overflow-x: auto; border: 1px solid var(--rule); background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: 0.86rem; font-variant-numeric: tabular-nums; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; }
th { font-weight: 600; color: var(--muted); font-size: 0.74rem; letter-spacing: 0.04em; text-transform: uppercase; }
td.num, th.num { text-align: right; font-family: var(--mono); }
.mono { font-family: var(--mono); font-size: 0.82rem; word-break: break-all; }
tr:last-child td { border-bottom: 0; }
.card { background: var(--surface); border: 1px solid var(--rule); border-left: 4px solid var(--verified-fg);
  padding: 18px; display: grid; gap: 14px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.facts div { min-width: 0; }
.facts .k { font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
.facts .v { font-family: var(--mono); font-size: 1.05rem; font-variant-numeric: tabular-nums; }
a { color: var(--accent); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
code { font-family: var(--mono); font-size: 0.82rem; background: var(--self-bg); padding: 1px 4px; border-radius: 3px; }
footer { color: var(--muted); font-size: 0.86rem; display: grid; gap: 6px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""


def render_html(m: dict) -> str:
    e = html.escape
    v = m["verified_row"]
    venue_rows = "\n".join(
        f"<tr><td class=\"num\">{r['rank']}</td>"
        f"<td class=\"mono\">{e(r['address'])}</td>"
        f"<td class=\"num\">{e(r['week_pnl_usdc'])}</td>"
        f"<td class=\"num\">{e(r['week_roi'])}</td>"
        f"<td class=\"num\">{e(r['account_value_usdc'])}</td>"
        f"<td><span class=\"chip self\">self-reported</span></td></tr>"
        for r in m["rows"])
    run_rows = "\n".join(
        f"<tr><td class=\"mono\">{e(f['file'])}</td><td>{e(f['mode'])}</td>"
        f"<td class=\"num\">{f['events']}</td><td class=\"num\">{f['cryptographically_signed']}</td>"
        f"<td class=\"mono\">{e(f['root'])}</td></tr>"
        for f in v["run_files"])
    tx_items = "\n".join(
        f"<li><a class=\"mono\" href=\"{e(u)}\" rel=\"noopener\">{e(u)}</a></li>"
        for u in v["explorer_urls"])
    gaps = ", ".join(e(g) for g in v["gaps_bps"])
    on_board = "yes" if v["on_venue_board"] else "no"
    return f"""<title>Proof of Outcome Week Board</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{_CSS}</style>
<main>
  <header style="display:grid;gap:10px">
    <div class="eyebrow">Proof of Outcome · mirror of {e(m['venue']['name'])} · {e(m['venue']['window'])} window · as of {e(m['as_of'])}</div>
    <h1>One verified row beside thirty self-reported ones</h1>
    <p class="lead">The venue's public week board, carried verbatim, and the operator's own account as the first row whose every number a stranger can re-verify offline and against the chain. {e(m['venue']['what_is_not_done'])}</p>
  </header>

  <section class="legend" aria-label="What the two statuses mean">
    <div><span class="chip self">self-reported</span><p>{e(m['statuses']['self_reported'])}</p></div>
    <div><span class="chip verified">verified</span><p>{e(m['statuses']['verified'])}</p></div>
  </section>

  <section>
    <h2>The venue's board</h2>
    <p class="lead" style="margin-bottom:10px">{m['venue']['rows']} rows from <code>{e(m['venue']['payload_file'])}</code>, sha256 <span class="mono">{e(m['venue']['payload_sha256'])}</span>, observed ms {m['observed_ms']}. Source: <a href="{e(m['venue']['source_url'])}" rel="noopener">{e(m['venue']['source_url'])}</a>.</p>
    <div class="wrap"><table>
      <thead><tr><th class="num">rank</th><th>address</th><th class="num">week pnl (USDC)</th><th class="num">week roi</th><th class="num">account value (USDC)</th><th>status</th></tr></thead>
      <tbody>
{venue_rows}
      </tbody>
    </table></div>
  </section>

  <section class="card" aria-label="The operator's verified row">
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <span class="chip verified">verified</span>
      <span class="mono">{e(v['address'])}</span>
      <span class="lead">on the venue's board: {on_board}</span>
    </div>
    <div class="facts">
      <div><div class="k">settled pairs</div><div class="v">PAPER {v['settled_pairs']['PAPER']} · LIVE {v['settled_pairs']['LIVE']}</div></div>
      <div><div class="k">realized, LIVE (USD)</div><div class="v">{e(v['realized_live_usd'])}</div></div>
      <div><div class="k">LIVE fees (USD)</div><div class="v">{e(v['fees_live_usd'])}</div></div>
      <div><div class="k">realized, PAPER (USD)</div><div class="v">{e(v['realized_paper_usd'])}</div></div>
      <div><div class="k">sim-to-real gaps (bps)</div><div class="v" style="font-size:0.9rem">{gaps}</div></div>
    </div>
    <p class="lead">PAPER and LIVE are different positions and are never summed. The LIVE result is a loss, and all of it is the fee; the row is here because it can be checked, not because of its sign.</p>
    <div class="wrap"><table>
      <thead><tr><th>run file</th><th>mode</th><th class="num">events</th><th class="num">signed</th><th>event-log root</th></tr></thead>
      <tbody>
{run_rows}
      </tbody>
    </table></div>
    <div>
      <div class="eyebrow" style="margin-bottom:6px">Chain fills, HyperLiquid L1</div>
      <ul style="margin:0;padding-left:18px;display:grid;gap:4px">
{tx_items}
      </ul>
    </div>
    <p>Verify any run file offline: <code>{e(v['verify_command'])}</code></p>
  </section>

  <footer>
    <div>This mirror's own run: <code>{e(m['board_run']['file'])}</code>, root <span class="mono">{e(m['board_run']['root'])}</span>, events <code>{e(m['board_run']['events'][0])}</code> and <code>{e(m['board_run']['events'][1])}</code>.</div>
    <div>Record source: <a href="{e(m['board_run']['record_source_url'])}" rel="noopener">{e(m['board_run']['record_source_url'])}</a>. An independent mirror; not operated by or affiliated with the venue.</div>
  </footer>
</main>
"""


def mirror_json(m: dict) -> str:
    return json.dumps(m, indent=2, default=str) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.agent_board",
        description="Day-4 board mirror run: the venue's self-reported week board "
                    "beside the operator's verified row. No fold; no trade.")
    parser.add_argument("--capture", default=None,
                        help="board capture (default: the single pinned capture_BOARD_*)")
    parser.add_argument("--run-file", action="append", default=None,
                        help="record run file(s) (default: every pinned PAPER/LIVE run)")
    parser.add_argument("--out", default="agent_board_run.ri")
    parser.add_argument("--mirror-out", default=None,
                        help="prefix for board_<date>.json/.md/.html (default: none written)")
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

    if args.capture:
        capture = Path(args.capture)
    else:
        pinned = pinned_board_captures()
        if len(pinned) != 1:
            print(f"ERROR: expected exactly one pinned board capture, found {len(pinned)}; "
                  "name one with --capture")
            return 2
        capture = pinned[0]
    run_paths = [Path(p) for p in args.run_file] if args.run_file else record_run_files()
    text = capture.read_text(encoding="utf-8")

    print("=" * 70)
    print("AGENT-RECORD BOARD MIRROR RUN -- END TO END (PREREG A3, Day 4)")
    print(f"BOARD capture: {capture.name}")
    for p in run_paths:
        print(f"record run file: {p.name}")
    print("The venue's week board carried verbatim (self_reported) beside the")
    print("operator's verified row. No venue number is recomputed. No belief is")
    print("folded. No trade is executed.")
    print("=" * 70)
    print()

    pipeline, events, indices, doc, summary, loaded = build(text, run_paths)
    print(f"Subject: {events[0].subject_ids[0]}")
    print("Events submitted through the engine (EP-typed, signed, logged):")
    for event in sorted(events, key=lambda e: indices[e.event_id]):
        print(f"  [{indices[event.event_id]}] {event.event_id}")
        print(f"      {event.event_type.value}, {event.ep_type.value}, "
              f"observed {event.observed_date}, claimant {event.claimant}")
    print()
    board = next(e for e in events if e.claimant == VENUE_CLAIMANT)
    mirror = next(e for e in events if e.claimant == MIRROR_CLAIMANT)
    bc, mc = board.claim, mirror.claim
    print(f"Venue board: {bc['rows']} rows, window {bc['window']}, payload sha256 "
          f"{bc['payload_sha256']}, actor on board: {bc['actor_on_board']}")
    print(f"Verified row: {len(mc['run_files'])} run files, {len(mc['tx_hashes'])} chain "
          f"hashes, settled pairs {mc['settled_pairs']}, realized PAPER "
          f"{mc['realized_paper_usd']} USD, realized LIVE {mc['realized_live_usd']} USD "
          f"(fees {mc['fees_live_usd']}), gaps {[str(g) for g in mc['gaps_bps']]} bps")
    print()

    root = pipeline.event_log.root(len(pipeline.event_log))
    run_bytes = pipeline.save(args.out)
    missing = trace_verified_row(mirror, loaded)
    inclusions_ok = _all_inclusions_verify(pipeline)
    reload_ok, reload_report = verify_run(args.out)
    logged = set(indices)
    refs_ok = all(ref in logged for e in events for ref in e.prior_event_refs)
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    venue_ok = True
    payload_path = capture.parent / bc["payload_file"]
    if payload_path.exists():
        raw = payload_path.read_bytes()
        venue_ok = (hashlib.sha256(raw).hexdigest() == bc["payload_sha256"])
        week = json.loads(raw.decode("utf-8"))["topTraders"]["week"]
        for r, src in zip(doc["rows"], week):
            wk = dict(src["windowPerformances"])["week"]
            venue_ok = venue_ok and r["address"] == src["ethAddress"] and \
                str(r["account_value_usdc"]) == str(src["accountValue"]) and \
                str(r["week_pnl_usdc"]) == str(wk["pnl"]) and \
                str(r["week_roi"]) == str(wk["roi"]) and str(r["week_vlm"]) == str(wk["vlm"])
        venue_ok = venue_ok and len(week) == len(doc["rows"])
    checks = [
        (f"C1 adapter produced {len(events)} events: 1 board (self_asserted), 1 verified "
         f"row (third_party_attested), {len(disputes)} dispute, {len(signed)} "
         f"cryptographically_signed",
         len(events) == 2 and board.ep_type is EPType.SELF_ASSERTED
         and mirror.ep_type is EPType.THIRD_PARTY_ATTESTED and not disputes and not signed),
        (f"C2 all {len(pipeline.event_log)} inclusion proofs verify against the root",
         inclusions_ok),
        ("C3 saved run reloads; every signature re-verifies; root unchanged",
         reload_ok and reload_report.endswith(root.hex())),
        ("C4 every prior_event_ref resolves inside this run's own log", refs_ok),
        (f"C5 verified row traces: every number is a claim value of a reloaded run-file "
         f"event" + (f" (UNTRACED: {missing})" if missing else ""), not missing),
        ("C6 venue rows carry the pinned payload's strings unchanged"
         + ("" if payload_path.exists() else " (payload not beside capture; skipped)"),
         venue_ok),
    ]
    print(f"Event log root: {root.hex()}")
    print(f"Run file:       {args.out} ({len(run_bytes)} bytes)")
    if args.mirror_out:
        m = render_mirror(doc, events, Path(args.out).name, root.hex())
        prefix = Path(args.mirror_out)
        for suffix, text_out in ((".json", mirror_json(m)), (".md", render_markdown(m)),
                                 (".html", render_html(m))):
            path = prefix.with_name(prefix.name + suffix)
            path.write_bytes(text_out.replace("\r\n", "\n").encode("utf-8"))
            print(f"Mirror:         {path} ({path.stat().st_size} bytes)")
    print()
    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    print()
    print("Verify independently (reload + re-verify signatures + inclusions):")
    print(f"  python -m rights_events.agent_board --verify --run {args.out}")
    print()
    print(f"AGENT-RECORD BOARD RUN: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
