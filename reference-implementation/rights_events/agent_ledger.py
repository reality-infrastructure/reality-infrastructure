"""THE POPULATION LEDGER (PREREG A21, R105–R107): every fork's status, rung, days alive,
run and 2σ bar, with retirement, as a pure function of the pinned marks files (for each FULL
forward day, the newest reading pinned by the morning the ledger is produced: as-read date
<= as_of + 1, A23's amendment of R105 — a later re-pin enters later ledgers, never a past
one), the frozen marker (k_for, is_candidate, mean_clears_2sigma, DECLARED) and a pinned
promotions file that only an amendment edits.

Statuses, evaluated day by day in date order on the data up to each day (R106):
  CANDIDATE  the marker's is_candidate holds with k = k_for(n_alive at the day's start)
  RETIRED    days alive >= 7 and episodes >= 2 and mean + 2σ/√n < min(0, mean of C1:<coin>);
             sticky; a retired fork's rows are never read again
  PROMOTED   an entry in promotions.json (never automatic; one rung only by amendment, R88)
  ALIVE      otherwise

No clock. No network. No reasoning as input (R96). Nothing opens, sizes or signs.

Usage:
    python -m rights_events.agent_ledger --as-of YYYY-MM-DD --out-prefix PREFIX
        [--vps-dir DIR] [--promotions FILE] [--marker FILE]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
VPS_DIR = _FIXTURES / "vps"
LEDGER_DIR = _FIXTURES / "ledger"
PROMOTIONS = LEDGER_DIR / "promotions.json"
MARKER = _FIXTURES / "marker" / "marker.py"
FIRST_FULL_DAY = "2026-11-01"
FORWARD_FAMILY = "F4"
CONTROL_FAMILY = "C1"
RETIRE_DAYS = 7
INITIAL_RUNG = 0
STATUS_ALIVE, STATUS_CANDIDATE, STATUS_PROMOTED, STATUS_RETIRED = "ALIVE", "CANDIDATE", "PROMOTED", "RETIRED"
LEDGER_KIND = "proof_of_outcome_population_ledger"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_marker(path: Path = MARKER):
    spec = importlib.util.spec_from_file_location("poo_marker_frozen", path)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m          # the marker's dataclasses need their module registered
    spec.loader.exec_module(m)
    return m


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_cutoff(as_of: str) -> str:
    """R105 (A23): the morning the ledger as of `as_of` is produced = as_of + 1 day."""
    return (_dt.date.fromisoformat(as_of) + _dt.timedelta(days=1)).isoformat()


def newest_readings(vps_dir: Path, first_day: str, as_of: str) -> dict[str, Path]:
    """R105 (as amended by A23): for each FULL forward day in [first_day, as_of] the newest
    pinned reading that existed by the morning the ledger is produced:
    marks_<day>_as_read_<date>.jsonl with the latest date <= as_of + 1, else marks_<day>.jsonl
    (pinned on day + 1 <= as_of + 1 by construction). A re-pin dated later is read by the
    ledgers from that date on and by no earlier one: a ledger's points never move."""
    out: dict[str, Path] = {}
    cutoff = read_cutoff(as_of)
    for p in sorted(vps_dir.glob("marks_*.jsonl")):
        m = re.match(r"^marks_(\d{4}-\d{2}-\d{2})(?:_as_read_(\d{4}-\d{2}-\d{2}))?\.jsonl$", p.name)
        if not m:
            continue
        day, read = m.group(1), m.group(2) or ""
        if day < first_day or day > as_of or read > cutoff:
            continue
        cur = out.get(day)
        if cur is None:
            out[day] = p
        else:
            cm = re.match(r"^marks_\d{4}-\d{2}-\d{2}(?:_as_read_(\d{4}-\d{2}-\d{2}))?\.jsonl$", cur.name)
            if read > (cm.group(1) or ""):
                out[day] = p
    return dict(sorted(out.items()))


def _rows(p: Path) -> list[dict]:
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("in_sample", False) or r.get("family") not in (FORWARD_FAMILY, CONTROL_FAMILY):
            continue
        rows.append(r)
    return rows


def ledger(as_of: str, vps_dir: Path = VPS_DIR, promotions_path: Path = PROMOTIONS,
           marker_path: Path = MARKER, coins: list[str] | None = None,
           first_day: str = FIRST_FULL_DAY) -> dict:
    if not _DAY.match(as_of):
        raise AdapterError(f"as_of {as_of!r} is not a YYYY-MM-DD date")
    mk = load_marker(marker_path)
    coins = list(coins if coins is not None else mk.DECLARED)
    forks = [f"{FORWARD_FAMILY}:{c}" for c in coins]
    readings = newest_readings(vps_dir, first_day, as_of)
    days = list(readings)
    rows_by_day = {d: _rows(p) for d, p in readings.items()}
    promotions = json.loads(promotions_path.read_text(encoding="utf-8")) if promotions_path.exists() else []
    if not isinstance(promotions, list):
        raise AdapterError("promotions.json must be a list")

    # day-by-day evaluation (R106)
    retired: dict[str, dict] = {}            # fork -> {day, reason}
    candidate_days: dict[str, list[str]] = {f: [] for f in forks}
    history: list[dict] = []
    n_alive = len(forks)
    for i, day in enumerate(days):
        upto = days[: i + 1]
        k = mk.k_for(n_alive) if n_alive > 0 else None
        daily: dict[str, dict[str, float]] = {}
        nets: dict[str, list[float]] = {}
        for d in upto:
            for r in rows_by_day[d]:
                fk = r["fork"]
                if fk in retired and d >= retired[fk]["day"]:
                    continue
                daily.setdefault(fk, {})[d] = daily.setdefault(fk, {}).get(d, 0.0) + float(r["net_bps"])
                nets.setdefault(fk, []).append(float(r["net_bps"]))
        day_states = {}
        newly_retired = []
        for fork in forks:
            coin = fork.split(":", 1)[1]
            if fork in retired:
                day_states[fork] = {"status": STATUS_RETIRED, "run": 0, "candidate": False}
                continue
            fn = nets.get(fork, [])
            cand, run = mk.is_candidate(daily.get(fork, {}), daily.get(f"{CONTROL_FAMILY}:{coin}", {}),
                                        upto, n_alive, fn)
            clears, mu, bar = mk.mean_clears_2sigma(fn)
            c1n = nets.get(f"{CONTROL_FAMILY}:{coin}", [])
            c1_mean = (sum(c1n) / len(c1n)) if c1n else 0.0
            status = STATUS_CANDIDATE if cand else STATUS_ALIVE
            if cand:
                candidate_days[fork].append(day)
            if len(upto) >= RETIRE_DAYS and len(fn) >= 2 and bar != float("inf") and mu + bar < min(0.0, c1_mean):
                status = STATUS_RETIRED
                newly_retired.append((fork, {"day": day, "reason": (
                    f"after {len(upto)} full forward days, mean net {mu:.2f} bps + 2σ/√n {bar:.2f} "
                    f"= {mu + bar:.2f} < min(0, C1 mean {c1_mean:.2f}) (R106)")}))
            day_states[fork] = {"status": status, "run": run, "candidate": cand, "k": k,
                                "mean_net_bps": mu, "two_sigma_over_sqrt_n": None if bar == float("inf") else bar,
                                "episodes": len(fn)}
        for fork, info in newly_retired:
            retired[fork] = info
        history.append({"day": day, "n_alive_at_start": n_alive, "k": k, "states": day_states})
        n_alive = len(forks) - len(retired)

    # promotions (R106 PROMOTED; S95)
    promoted: dict[str, dict] = {}
    for e in promotions:
        fork, rung, date = e.get("fork"), e.get("rung"), e.get("date")
        if fork not in forks or not isinstance(rung, int) or rung < 1 or not (isinstance(date, str) and _DAY.match(date)):
            raise AdapterError(f"S95: malformed promotion entry {e!r}")
        if date > as_of:
            continue
        if fork in retired and retired[fork]["day"] <= date:
            raise AdapterError(f"S95: {fork} promoted on {date} but RETIRED on {retired[fork]['day']}")
        if not any(d <= date for d in candidate_days[fork]):
            raise AdapterError(f"S95: {fork} promoted on {date} without being CANDIDATE on or before it")
        promoted[fork] = {"rung": rung, "amendment": str(e.get("amendment", "")), "date": date}

    # the ledger as of the last day
    last = history[-1] if history else None
    fork_rows = []
    all_nets: dict[str, list[float]] = {}
    for d in days:
        for r in rows_by_day[d]:
            fk = r["fork"]
            if fk in retired and d >= retired[fk]["day"]:
                continue
            all_nets.setdefault(fk, []).append(float(r["net_bps"]))
    for fork in forks:
        coin = fork.split(":", 1)[1]
        st = last["states"][fork] if last else {"status": STATUS_ALIVE, "run": 0, "candidate": False}
        status = st["status"]
        rung = INITIAL_RUNG
        if fork in promoted and status != STATUS_RETIRED:
            status, rung = STATUS_PROMOTED, promoted[fork]["rung"]
        fn = all_nets.get(fork, [])
        c1n = all_nets.get(f"{CONTROL_FAMILY}:{coin}", [])
        clears, mu, bar = mk.mean_clears_2sigma(fn)
        fork_rows.append({
            "fork": fork, "coin": coin, "status": status, "rung": rung,
            "days_alive": (days.index(retired[fork]["day"]) + 1) if fork in retired else len(days),
            "episodes": len(fn), "sum_net_bps": sum(fn), "mean_net_bps": mu,
            "two_sigma_over_sqrt_n": None if bar == float("inf") else bar,
            "two_sigma_clears": clears,
            "run_days": st.get("run", 0), "k": last["k"] if last else None,
            "candidate": st.get("candidate", False),
            "candidate_days": candidate_days[fork],
            "control_c1": {"episodes": len(c1n), "mean_net_bps": (sum(c1n) / len(c1n)) if c1n else None},
            "retired": retired.get(fork),
            "promotion": promoted.get(fork),
        })
    counts = {s: sum(1 for r in fork_rows if r["status"] == s)
              for s in (STATUS_ALIVE, STATUS_CANDIDATE, STATUS_PROMOTED, STATUS_RETIRED)}
    return {
        "kind": LEDGER_KIND,
        "as_of": as_of,
        "first_full_day": first_day,
        "days": days,
        "readings": {d: p.name for d, p in readings.items()},
        "pins": {**{p.name: sha256_file(p) for p in readings.values()},
                 "marker.py": sha256_file(marker_path),
                 **({promotions_path.name: sha256_file(promotions_path)} if promotions_path.exists() else {})},
        "n_alive_at_start_of_last_day": last["n_alive_at_start"] if last else len(forks),
        "n_alive_now": len(forks) - len(retired),
        "k": last["k"] if last else None,
        "counts": counts,
        "forks": fork_rows,
        "history": history,
        "rules": {"candidate": "marker.is_candidate: trailing run of days beating C0 (0) and C1:<coin> >= k_for(n_alive) and mean > 2σ/√n",
                  "retired": f"days alive >= {RETIRE_DAYS} and episodes >= 2 and mean + 2σ/√n < min(0, C1 mean); sticky",
                  "promoted": "an entry in promotions.json only (an amendment under R88); rungs 0 paper, 1 one unit, 2 four, 3 sixteen",
                  "slot": "a retirement frees one slot, refilled only by a PREREG amendment (R107)"},
        "what_is_not_claimed": "No forecast, no profit: statuses by written rule over pinned forward days.",
    }


def _f(x, nd=2) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def render_markdown(m: dict) -> str:
    out = [f"# Population ledger as of {m['as_of']} (PREREG A21)", ""]
    out.append(f"Full forward days read: {len(m['days'])} ({m['days'][0] if m['days'] else '—'} … {m['days'][-1] if m['days'] else '—'}); "
               f"n_alive {m['n_alive_now']}; k {m['k']}; counts {m['counts']}.")
    out.append("")
    out.append("| fork | status | rung | days alive | episodes | sum net bps | mean net bps | 2σ/√n | run | k | C1 episodes | C1 mean | retired | promotion |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for r in m["forks"]:
        ret = f"{r['retired']['day']}: {r['retired']['reason']}" if r["retired"] else "—"
        pro = f"rung {r['promotion']['rung']} by {r['promotion']['amendment']} on {r['promotion']['date']}" if r["promotion"] else "—"
        out.append(f"| {r['fork']} | {r['status']} | {r['rung']} | {r['days_alive']} | {r['episodes']} | {_f(r['sum_net_bps'])} | "
                   f"{_f(r['mean_net_bps'])} | {_f(r['two_sigma_over_sqrt_n'])} | {r['run_days']} | {r['k']} | "
                   f"{r['control_c1']['episodes']} | {_f(r['control_c1']['mean_net_bps'])} | {ret} | {pro} |")
    out.append("")
    out.append("Rules: " + "; ".join(f"**{k}** {v}" for k, v in m["rules"].items()))
    out.append("")
    out.append("Readings (newest pinned per day): " + ", ".join(f"{d} ← `{n}`" for d, n in m["readings"].items()))
    out.append("")
    out.append("Pins: " + ", ".join(f"`{k}` {v[:16]}…" for k, v in m["pins"].items()))
    out.append("")
    out.append(m["what_is_not_claimed"])
    return "\n".join(out) + "\n"


def ledger_json(m: dict) -> str:
    return json.dumps(m, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.agent_ledger",
                                description="The population ledger (PREREG A21). Pure; no trade.")
    p.add_argument("--as-of", required=True)
    p.add_argument("--out-prefix", required=True)
    p.add_argument("--vps-dir", default=str(VPS_DIR))
    p.add_argument("--promotions", default=str(PROMOTIONS))
    p.add_argument("--marker", default=str(MARKER))
    a = p.parse_args(argv)
    try:
        m = ledger(a.as_of, Path(a.vps_dir), Path(a.promotions), Path(a.marker))
    except AdapterError as exc:
        print(f"LEDGER REFUSED: {exc}")
        return 1
    prefix = Path(a.out_prefix)
    for suffix, text in ((".json", ledger_json(m)), (".md", render_markdown(m))):
        path = prefix.with_name(prefix.name + suffix)
        path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
        print(f"wrote {path} sha256 {sha256_file(path)}")
    print(f"POPULATION LEDGER as of {m['as_of']}: days {len(m['days'])}, n_alive {m['n_alive_now']}, k {m['k']}, counts {m['counts']}")
    for r in m["forks"]:
        print(f"  {r['fork']:9} {r['status']:9} rung {r['rung']} days {r['days_alive']} n {r['episodes']:3d} "
              f"mean {_f(r['mean_net_bps']):>8} run {r['run_days']}/{r['k']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
