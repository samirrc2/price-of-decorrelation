"""Phase 1 — emit the frozen grid to appendix/grid.csv and validate constraints.

Columns: cell_id, ticker, sector, date, regime.
Validates: every date strictly AFTER the latest USED-model knowledge cutoff and
ON/BEFORE 2026-06-01 (forward window closed). Aborts on violation.
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path

import io_paths

import yaml

_HERE = io_paths.repo_root()
LAST_VALID_DATE = date(2026, 6, 1)


def used_models(cfg):
    keys = set()
    for slots in cfg["configs"].values():
        for s in slots:
            keys.add(s["model"])
    return keys


def main():
    cfg = yaml.safe_load(io_paths.default_config_path().read_text())
    ticker_sector = {}
    for sec, tks in cfg["sectors"].items():
        for t in tks:
            ticker_sector[t] = sec

    # validate date constraints against USED models only
    cutoffs = {m: date.fromisoformat(cfg["models"][m]["knowledge_cutoff"])
               for m in used_models(cfg)}
    latest_cut = max(cutoffs.values())
    problems = []
    for d in cfg["dates"]:
        dd = date.fromisoformat(d)
        if dd <= latest_cut:
            problems.append(f"{d} not strictly after latest used-model cutoff {latest_cut}")
        if dd > LAST_VALID_DATE:
            problems.append(f"{d} is after 2026-06-01 (forward window may not have closed)")
    if problems:
        print("GRID VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        print(f"(latest used-model cutoff = {latest_cut}; cutoffs: "
              f"{ {k: str(v) for k,v in cutoffs.items()} })")
        return 2

    out = io_paths.data_root() / "appendix" / "grid.csv"
    out.parent.mkdir(exist_ok=True)
    regimes = cfg.get("date_regimes", {})
    n = 0
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell_id", "ticker", "sector", "date", "regime"])
        for t in cfg["tickers"]:
            for d in cfg["dates"]:
                w.writerow([f"{t}|{d}", t, ticker_sector.get(t, "?"), d,
                            regimes.get(d, "")])
                n += 1
    print(f"Wrote {out} : {n} cells "
          f"({len(cfg['tickers'])} tickers x {len(cfg['dates'])} dates).")
    print(f"Date floor OK: all dates > {latest_cut} and <= {LAST_VALID_DATE}.")
    # sector balance
    from collections import Counter
    bal = Counter(ticker_sector[t] for t in cfg["tickers"])
    print("Sector balance:", dict(bal))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
