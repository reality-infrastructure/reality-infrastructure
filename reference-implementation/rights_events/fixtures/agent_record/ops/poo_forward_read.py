"""poo_forward_read.py - the forward day READER (A17; lines and void days by rule, A26). Reads, never decides.

Given the published day files (branch vps/poo-files of this repo, or a local pull), it prints the
record's reading for a UTC day exactly as P12.0/P12.2 pre-registered it and nothing else:

  * per fork: n, mean gross bps, mean net bps, stop-first share, sum net bps (from marks_<day>.jsonl)
  * per fork: the trailing run of forward days beating BOTH controls (C0 = 0, C1 = the seeded
    random entry on the same coin), k from marker.k_for(N alive), and whether the 2-sigma/sqrt(n)
    clause clears - through the FROZEN marker.py (is_candidate / mean_clears_2sigma / k_for);
    no rule lives here
  * the sensor's health from manifest.json (services, tape freshness) and the state's void_days
  * sha256 of every input file read, so the amendment can pin what was read

A26 (R115): a day-file line is a row, the row-suffix of a glued torn line (the fragment counted,
its row lost and never reconstructed) or an in-flight tail; anything else refuses the file (S98)
and nothing is computed. A26 (R116): a day whose marks carry the marker's own void mark (S72) is
disclosed and counted for nothing - it is removed from the pass line's days before the frozen
marker is called. Files are never repaired; every pin is the sha256 of the file as served.

Stdlib only. No network. No wall clock. Does not import forward.py.
Usage:
  python poo_forward_read.py --dir <folder with marker/ and manifest.json> --day 2026-11-01 \
      [--days 2026-10-31 2026-11-01] [--n-alive 6] [--json]
Exit 1 and `REFUSED S98 ...` on a file that R115 cannot read.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER_DIR = HERE.parent / "marker"
FORWARD_FAMILIES = ("F4", "C1")        # R84: F1-F3 deleted for the week
TORN_HEAD_CHARS = 60                   # R115: how much of a discarded fragment is disclosed
VOID_TYPE = "void"                     # the marker's S72 mark inside a marks file


class Refused(Exception):
    """S98: a day file R115 cannot read; the reader computes nothing."""


def load_marker(path: Path = MARKER_DIR / "marker.py"):
    spec = importlib.util.spec_from_file_location("marker", path)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _object(text: str) -> dict | None:
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def read_day_lines(p: Path, kind: str) -> tuple[list[dict], list[dict], dict]:
    """R115. `kind` is "marks" or "signals". Returns (rows, void_marks, alignment).

    A line that parses to an object is a row. A line that does not, but has a suffix starting at
    a `{` that parses to an object, is a torn fragment glued to a whole row: the row is the suffix
    from the leftmost such `{`, verbatim; the fragment is counted and its row is lost. A line that
    matches neither way and is the file's last non-empty line is an in-flight append: dropped and
    counted. Any other line raises Refused (S98). In a marks file a row is an episode (`fork` and
    `family`) or the marker's void mark (`type` == "void"); anything else raises Refused (S98).
    """
    if kind not in ("marks", "signals"):
        raise ValueError(kind)
    align = {"file": p.name, "lines": 0, "rows": 0, "void_marks": 0, "torn_fragments": [],
             "lost_rows": 0, "in_flight": 0}
    if not p.exists():
        return [], [], align
    lines = p.read_text(encoding="utf-8").splitlines()
    align["lines"] = len(lines)
    last = max((i for i, l in enumerate(lines) if l.strip()), default=-1)
    rows: list[dict] = []
    voids: list[dict] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        obj = _object(line)
        if obj is None:
            cut = None
            for j, ch in enumerate(line):
                if ch == "{":
                    cand = _object(line[j:])
                    if cand is not None:
                        cut, obj = j, cand
                        break
            if cut is None:
                if i == last:
                    align["in_flight"] += 1
                    continue
                raise Refused("S98: %s line %d is neither a row, a glued torn line nor an in-flight tail" % (p.name, i + 1))
            align["torn_fragments"].append({"line": i + 1, "head": line[:cut][:TORN_HEAD_CHARS]})
            align["lost_rows"] += 1
        assert obj is not None
        if kind == "marks":
            if obj.get("type") == VOID_TYPE:
                voids.append(obj)
                align["void_marks"] += 1
                continue
            if "fork" not in obj or "family" not in obj:
                raise Refused("S98: %s line %d is neither an episode nor a void mark" % (p.name, i + 1))
        rows.append(obj)
    align["rows"] = len(rows)
    return rows, voids, align


def read_jsonl(p: Path) -> list[dict]:
    """Rows of a day file under R115 (void marks excluded); kept for callers of the A17 name."""
    kind = "marks" if p.name.startswith("marks_") else "signals"
    return read_day_lines(p, kind)[0]


def fork_table(rows: list[dict]) -> dict[str, dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["fork"]].append(r)
    out = {}
    for fork in sorted(by):
        v = by[fork]
        n = len(v)
        out[fork] = {
            "family": v[0]["family"], "coin": v[0]["coin"], "n": n,
            "mean_gross_bps": statistics.fmean(r["gross_bps"] for r in v),
            "mean_net_bps": statistics.fmean(r["net_bps"] for r in v),
            "sum_net_bps": sum(r["net_bps"] for r in v),
            "stop_first_share": sum(1 for r in v if r["exit_reason"] == "stop") / n,
            "funding_applied": all(r.get("funding_bps", 0.0) != 0.0 for r in v),
            "proxy_rows": sum(1 for r in v if "unavailable" in str(r.get("spread_source", ""))),
        }
    return out


def pass_line(mk, rows_by_day: dict[str, list[dict]], days: list[str], n_alive: int) -> dict[str, dict]:
    """Per fork F4:<coin>: trailing run of days beating C0 and C1:<coin>, k, 2-sigma clause, candidate.
    `days` are the pass-line days: the caller has already removed void days (R116)."""
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    nets: dict[str, list[float]] = defaultdict(list)
    for day in days:
        for r in rows_by_day.get(day, []):
            daily[r["fork"]][day] = daily[r["fork"]].get(day, 0.0) + r["net_bps"]
            nets[r["fork"]].append(r["net_bps"])
    k = mk.k_for(n_alive)
    out = {}
    for fork in sorted(daily):
        fam, coin = fork.split(":", 1)
        if fam == "C1":
            continue
        cand, run = mk.is_candidate(daily[fork], daily.get("C1:" + coin, {}), days, n_alive, nets[fork])
        clears, mu, bar = mk.mean_clears_2sigma(nets[fork])
        out[fork] = {"run_days": run, "k": k, "two_sigma_clears": clears, "mean_net_bps": mu,
                     "two_sigma_over_sqrt_n": None if bar == float("inf") else bar,
                     "candidate": cand, "n_episodes": len(nets[fork])}
    return out


def health(manifest: dict | None, state: dict | None, day: str, void_by_row: bool = False) -> dict:
    h = {"manifest_generated_at": None, "poo_tape": None, "poo_marker": None, "tape_newest_mtime": None,
         "void_days": [], "day_void": False, "day_void_by_state": False, "day_void_by_row": void_by_row,
         "tick_errors": None}
    if manifest:
        h["manifest_generated_at"] = manifest.get("generated_at")
        for k in ("poo_tape", "poo_marker", "tape_newest_mtime"):
            h[k] = manifest.get(k)
    if state:
        vd = state.get("void_days", [])
        vd_list = list(vd) if isinstance(vd, (list, dict, set)) else []
        h["void_days"] = sorted(vd_list)
        h["day_void_by_state"] = day in vd_list
        h["tick_errors"] = state.get("tick_errors", state.get("tick_error_count"))
    h["day_void"] = bool(h["day_void_by_state"] or void_by_row)      # R116: either source; the row decides
    return h


def _disclosure(rows: list[dict]) -> dict:
    """What a void day's rows were, counted for nothing (R116)."""
    by: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by[r["fork"]].append(r["net_bps"])
    return {"episodes": len(rows), "sum_net_bps": sum(sum(v) for v in by.values()),
            "forks": {f: {"n": len(v), "sum_net_bps": sum(v)} for f, v in sorted(by.items())}}


def read(dir_: Path, day: str, days: list[str], n_alive: int, mk=None) -> dict:
    mk = mk or load_marker()
    mdir = dir_ / "marker"
    pins = {}
    rows_by_day: dict[str, list[dict]] = {}
    void_marks: dict[str, list[dict]] = {}
    alignment: dict[str, dict] = {}
    for d in days:
        p = mdir / ("marks_%s.jsonl" % d)
        rows, voids, al = read_day_lines(p, "marks")
        rows_by_day[d] = [r for r in rows if r["family"] in FORWARD_FAMILIES and not r.get("in_sample", False)]
        if voids:
            void_marks[d] = voids
        if p.exists():
            pins[p.name] = sha256_file(p)
            alignment[p.name] = al
    void_days_by_row = [d for d in days if d in void_marks]
    pass_days = [d for d in days if d not in void_marks]
    sig_p = mdir / ("signals_%s.jsonl" % day)
    signals, _, sig_al = read_day_lines(sig_p, "signals")
    if sig_p.exists():
        pins[sig_p.name] = sha256_file(sig_p)
        alignment[sig_p.name] = sig_al
    man_p, st_p = dir_ / "manifest.json", mdir / "marker_state.json"
    manifest = json.loads(man_p.read_bytes()) if man_p.exists() else None
    state = json.loads(st_p.read_bytes()) if st_p.exists() else None
    for p in (man_p, st_p):
        if p.exists():
            pins[p.name] = sha256_file(p)
    sig_types: dict[str, int] = defaultdict(int)
    for s in signals:
        sig_types[s.get("type", "?")] += 1
    rows = rows_by_day.get(day, [])
    return {
        "day": day, "days": days, "n_alive": n_alive, "k": mk.k_for(n_alive),
        "episodes": len(rows), "forks": fork_table(rows),
        "pass_line": pass_line(mk, rows_by_day, pass_days, n_alive),
        "pass_line_days": pass_days,
        "void_days_by_row": void_days_by_row,
        "void_marks": {d: [{"ms": v.get("ms"), "reason": v.get("reason")} for v in void_marks[d]] for d in void_days_by_row},
        "void_day_disclosure": {d: _disclosure(rows_by_day[d]) for d in void_days_by_row},
        "alignment": alignment,
        "signals": dict(sorted(sig_types.items())),
        "health": health(manifest, state, day, void_by_row=day in void_marks),
        "pins": dict(sorted(pins.items())),
        "marker_sha256": sha256_file(MARKER_DIR / "marker.py"),
    }


def markdown(r: dict) -> str:
    L = ["**Forward day %s** - episodes %d, N alive %d -> k = %d; marker.py `%s...`%s"
         % (r["day"], r["episodes"], r["n_alive"], r["k"], r["marker_sha256"][:8],
            " - **VOID by the marker's own mark (S72, R116): counted for nothing**" if r["day"] in r["void_days_by_row"] else ""),
         "", "| fork | n | mean gross bps | mean net bps | stop-first | sum net bps |", "|---|---|---|---|---|---|"]
    for f, v in r["forks"].items():
        L.append("| %s | %d | %+.2f | %+.2f | %.0f%% | %+.1f |"
                 % (f, v["n"], v["mean_gross_bps"], v["mean_net_bps"], 100 * v["stop_first_share"], v["sum_net_bps"]))
    L += ["", "Pass-line days (R116): %s%s" % (", ".join(r["pass_line_days"]) or "none",
          ("; void by the marker's own mark, counted for nothing: " + ", ".join(
              "%s (%d marks, %d episodes, sum %+.1f bps)" % (d, len(r["void_marks"][d]), r["void_day_disclosure"][d]["episodes"],
                                                            r["void_day_disclosure"][d]["sum_net_bps"]) for d in r["void_days_by_row"]))
          if r["void_days_by_row"] else "")]
    L += ["", "| fork | run of days beating C0 and C1 | k | 2-sigma clause | candidate |", "|---|---|---|---|---|"]
    for f, v in r["pass_line"].items():
        L.append("| %s | %d | %d | %s | %s |" % (f, v["run_days"], v["k"],
                 "clears" if v["two_sigma_clears"] else "no", "YES" if v["candidate"] else "no"))
    h = r["health"]
    L += ["", "Health: poo-tape %s, poo-marker %s, tape newest %s, manifest %s, void_days %s, this day void: %s (by state %s, by row %s)"
          % (h.get("poo_tape"), h.get("poo_marker"), h.get("tape_newest_mtime"), h.get("manifest_generated_at"),
             h.get("void_days"), h.get("day_void"), h.get("day_void_by_state"), h.get("day_void_by_row")),
          "Signals: %s" % r["signals"], "", "Alignment (R115), file: rows / void marks / torn fragments [lines] / lost rows / in-flight:"]
    for name, al in r["alignment"].items():
        L.append("- `%s`: %d / %d / %d %s / %d / %d" % (name, al["rows"], al["void_marks"], len(al["torn_fragments"]),
                 [t["line"] for t in al["torn_fragments"]], al["lost_rows"], al["in_flight"]))
    L += ["", "Pins (sha256):"]
    L += ["- `%s` %s" % (k, v) for k, v in r["pins"].items()]
    return "\n".join(L)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True, type=Path, help="folder holding manifest.json and marker/")
    p.add_argument("--day", required=True, help="UTC day to read, YYYY-MM-DD")
    p.add_argument("--days", nargs="*", default=None, help="the forward days in order for the pass line (default: --day only)")
    p.add_argument("--n-alive", type=int, default=6, help="R85 N alive (default 6 -> k = 5)")
    p.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    a = p.parse_args(argv)
    days = a.days or [a.day]
    try:
        r = read(a.dir, a.day, days, a.n_alive)
    except Refused as exc:
        print("REFUSED %s" % exc)
        return 1
    print(json.dumps(r, indent=1, sort_keys=True) if a.json else markdown(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
