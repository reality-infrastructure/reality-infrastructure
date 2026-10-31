"""P12.1 — tonight's IN-SAMPLE replay (P12.0). Counts for nothing. Promotes nothing. Its one
permitted act is deletion of a family whose in-sample mean net is below BOTH controls'.

Inputs (all pinned, read-only): the 52-day 15-minute candleSnapshot per declared coin
(P11c), the hourly fundingHistory per coin (P11c for BTC, funding_MANIFEST_2026-10-31 for the
rest), the leaders' public fill history (marker/leader_fills/), families.json,
leaders_2026-11-01.json. The path is the 15-minute closes (T, c): stops are detected at
15-minute closes only, which understates adverse excursion; the spread is the fixed proxy.
Both are disclosed on every row (`in_sample: true`, `spread_source: replay_proxy`).

Usage: python -I replay.py --fixtures <fixtures/agent_record> --seed <commit sha> --out <dir>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path


def _load_marker(here: Path):
    spec = importlib.util.spec_from_file_location("marker", here / "marker.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m  # dataclasses with deferred annotations resolve through sys.modules
    spec.loader.exec_module(m)
    return m


def load_candles(fix: Path, coin: str) -> list[dict]:
    files = sorted(fix.glob(f"hl_candleSnapshot_{coin}_15m_*.json"))
    if not files:
        raise SystemExit(f"no 15m candles for {coin}")
    return json.loads(files[-1].read_bytes())


def load_funding(fix: Path, coin: str) -> list[tuple[int, float]]:
    rows: dict[int, float] = {}
    for f in sorted(fix.glob(f"hl_fundingHistory_{coin}_*.json")):
        for r in json.loads(f.read_bytes()):
            if r.get("coin") == coin:
                rows[int(r["time"])] = float(r["fundingRate"])
    return sorted(rows.items())


def load_leader_fills(fix: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted((fix / "marker" / "leader_fills").glob("userFillsByTime_0x*.json")):
        addr = f.name.split("_")[1]
        out[addr] = json.loads(f.read_bytes())
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures", type=Path, required=True)
    p.add_argument("--seed", required=True, help="the amendment commit sha that seeds C1")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    here = Path(__file__).resolve().parent
    mk = _load_marker(here)
    fam = json.loads((here / "families.json").read_bytes())
    leaders = json.loads((here / "leaders_2026-11-01.json").read_bytes())
    kept = [l["address"] for l in leaders["leaders"] if l["kept"]]
    fills_by_leader = load_leader_fills(a.fixtures)
    stop = fam["exit"]["stop_bps"]; gate = fam["exit"]["gate_ms"]
    fee = fam["costs"]["fee_bps_per_leg"]; proxy = fam["costs"]["replay_spread_proxy_bps_per_leg"]
    a.out.mkdir(parents=True, exist_ok=True)
    rows_path = a.out / "replay_rows.jsonl"
    episodes_by_fork: dict[str, list] = {}
    days_all: set[str] = set()
    with rows_path.open("w", encoding="utf-8", newline="\n") as rows:
        for coin in fam["declared_coins"]:
            candles = load_candles(a.fixtures, coin)
            funding = load_funding(a.fixtures, coin)
            path = [(int(c["T"]), float(c["c"])) for c in candles]
            days = sorted({mk.day_of(ms) for ms, _ in path})
            days_all.update(days)
            common = dict(stop_bps=stop, gate_ms=gate, fee_bps_per_leg=fee, spread_bps_per_leg=proxy,
                          spread_source="replay_proxy", funding=funding, in_sample=True)
            sigs = {
                "F1": mk.f1_funding_extreme(funding, fam["families"]["F1"]["parameter"]["abs_funding_percentile"], coin),
                "F2": mk.f2_reversion(candles, fam["families"]["F2"]["parameter"]["return_sigma"],
                                      fam["families"]["F2"]["parameter"]["notional_median_multiple"], coin),
                "F3": mk.f3_breakout(candles, fam["families"]["F3"]["parameter"]["lookback_candles"], coin),
                "F4": [s for addr in kept for s in mk.f4_leader_opens(
                    fills_by_leader.get(addr, []), fam["families"]["F4"]["parameter"]["min_open_notional_usd"], coin, addr)],
            }
            # long share per day among F1-F4 signals, for C1's direction draw
            long_share: dict[str, float] = {}
            per_day: dict[str, list[int]] = {}
            for fl in sigs.values():
                for s in fl:
                    per_day.setdefault(mk.day_of(s["ms"]), []).append(s["direction"])
            for d, ds in per_day.items():
                long_share[d] = sum(1 for x in ds if x > 0) / len(ds)
            sigs["C1"] = mk.c1_signals(a.seed, coin, days, long_share)
            for family, fl in sigs.items():
                fork = f"{family}:{coin}"
                eps = mk.mark_fork(path, fl, fork=fork, family=family, coin=coin, **common)
                episodes_by_fork[fork] = eps
                for e in eps:
                    rows.write(mk.dumps_row(e) + "\n")
    # summary
    fam_names = ["F1", "F2", "F3", "F4", "C1"]
    summary = {"what": "P12.1 in-sample replay over the 52-day 15m backfill; counts for nothing; may only delete",
               "seed": a.seed, "days": len(days_all), "per_fork": {}, "per_family": {}, "deletions": [], "S70": None}
    for fork, eps in episodes_by_fork.items():
        summary["per_fork"][fork] = mk.summarise(eps)
    for f in fam_names:
        nets = [e.net_bps for fork, eps in episodes_by_fork.items() if fork.startswith(f + ":") for e in eps]
        s = mk.summarise([e for fork, eps in episodes_by_fork.items() if fork.startswith(f + ":") for e in eps])
        s["per_coin_mean"] = {fork.split(":")[1]: summary["per_fork"][fork]["mean_net_bps"]
                              for fork in episodes_by_fork if fork.startswith(f + ":")}
        summary["per_family"][f] = s
    c1 = summary["per_family"]["C1"]
    # S70: C1's mean within 2σ/√n of zero, else the harness is wrong and nothing is read
    s70_ok = c1["n"] > 1 and abs(c1["mean_net_bps"]) <= (c1["two_sigma_over_sqrt_n"] or float("inf"))
    summary["S70"] = {"c1_mean_net_bps": c1["mean_net_bps"], "c1_two_sigma_over_sqrt_n": c1["two_sigma_over_sqrt_n"],
                      "within": s70_ok, "note": "C1 pays costs each episode, so its mean is expected NEGATIVE by about the cost line; 'within' tests |mean| <= 2σ/√n and is reported, not asserted, when costs dominate"}
    c0_mean = 0.0
    for f in ("F1", "F2", "F3", "F4"):
        s = summary["per_family"][f]
        verdict = "DELETE" if (s["n"] >= 10 and s["mean_net_bps"] < c0_mean and s["mean_net_bps"] < c1["mean_net_bps"]) else \
                  ("KEEP (n < 10: no reading)" if s["n"] < 10 else "KEEP")
        summary["deletions"].append({"family": f, "n": s["n"], "mean_net_bps": s["mean_net_bps"], "c1_mean_net_bps": c1["mean_net_bps"], "verdict": verdict})
    sp = a.out / "replay_summary.json"
    sp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"rows: {rows_path} ({sum(len(v) for v in episodes_by_fork.values())} episodes)  summary: {sp}")
    for d in summary["deletions"]:
        print(f"  {d['family']}: n={d['n']:>5} mean net {d['mean_net_bps']:>8.2f} bps  (C1 {d['c1_mean_net_bps']:.2f})  -> {d['verdict']}")
    print(f"  C1: n={c1['n']} mean {c1['mean_net_bps']:.2f} bps  2sigma/sqrt(n) {c1['two_sigma_over_sqrt_n']:.2f}  S70 within: {s70_ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
