"""Independence check — did the 5 agents in each cell actually produce DISTINCT draws?

The estimand is independent agent draws. If agents share a seed (or the provider
caches/ignores sampling), their raw completions come back identical and within-run
κ is spuriously 1.0. This script quantifies that directly from runs.csv by comparing
the raw completions (and directions) of the 5 agents within each (config, ticker,
date, run) cell.

Reports, per config:
  - fraction of cells where ALL 5 raw completions are byte-identical
  - fraction of cells where all 5 directions agree
  - mean distinct raw completions per cell (5 = fully independent outputs)
A high identical-raw fraction under seed_mode=per_agent/none points at provider-side
determinism or prompt caching, not a genuine ensemble.
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "runs.csv"
    runs = Path(arg) if Path(arg).is_absolute() else (_HERE / arg)
    if not runs.exists():
        print(f"No {runs} — run orchestrator.py first (or pass the right path).")
        return 1
    rows = [r for r in csv.DictReader(runs.open()) if r.get("ok") == "True"]
    if not rows:
        print("No usable rows.")
        return 1

    seed_modes = sorted({r.get("seed_mode", "?") for r in rows})
    print(f"seed_mode(s) present in log: {seed_modes}\n")

    # group by cell
    cells = defaultdict(list)  # (config,ticker,date,run) -> list of rows
    for r in rows:
        cells[(r["config"], r["ticker"], r["date"], r["run_idx"])].append(r)

    per_cfg = defaultdict(lambda: {"cells": 0, "identical_raw": 0,
                                   "identical_dir": 0, "distinct_sum": 0,
                                   "seed_collision": 0})
    for (cfg, t, d, run), members in cells.items():
        if len(members) < 2:
            continue
        raws = [m.get("raw_response", "") for m in members]
        dirs = [m.get("direction", "") for m in members]
        seeds = [m.get("seed", "") for m in members]
        s = per_cfg[cfg]
        s["cells"] += 1
        s["distinct_sum"] += len(set(raws))
        if len(set(raws)) == 1:
            s["identical_raw"] += 1
        if len(set(dirs)) == 1:
            s["identical_dir"] += 1
        if len(set(seeds)) < len(seeds):
            s["seed_collision"] += 1

    print(f"{'config':6} {'cells':>5} {'identical_raw':>14} {'identical_dir':>14} "
          f"{'mean_distinct/5':>16} {'seed_collisions':>16}")
    for cfg in sorted(per_cfg):
        s = per_cfg[cfg]
        n = s["cells"] or 1
        print(f"{cfg:6} {s['cells']:5d} "
              f"{s['identical_raw']/n:13.2%} "
              f"{s['identical_dir']/n:13.2%} "
              f"{s['distinct_sum']/n:15.2f} "
              f"{s['seed_collision']:16d}")

    print("\nInterpretation:")
    print("  identical_raw high  -> agents are NOT independent (seed sharing, provider")
    print("                         caching, or sampling ignored). within-run κ inflated.")
    print("  mean_distinct ~5    -> genuinely independent draws (good).")
    print("  seed_collisions >0  -> two agents in a cell were sent the same seed (bug).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
