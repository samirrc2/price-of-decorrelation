"""Fetch EOD price history for all grid tickers via yfinance -> datacache/prices.json.

Runs on your Mac (open network). Scalable to any ticker/date count. This replaces
the connector news fetch: the per-cell context is derived deterministically from
these prices (see build_data.py), so no proprietary news API is needed.

Range covers enough history before the earliest analysis date to compute trailing
features (~63 trading days) and enough after the latest date for the 20-td forward
return. Adjust HISTORY_START / HISTORY_END if you move the grid.
"""
from __future__ import annotations
import json
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
HISTORY_START = "2025-09-01"   # ~63 td before the earliest 2026 date
HISTORY_END = "2026-07-01"     # after the latest 20-td forward window closes


def main():
    import yfinance as yf
    cfg = yaml.safe_load((_HERE / "config.yaml").read_text())
    tickers = cfg["tickers"]
    out = {}
    missing = []
    for i, t in enumerate(tickers, 1):
        try:
            h = yf.Ticker(t).history(start=HISTORY_START, end=HISTORY_END, auto_adjust=True)
            if h.empty:
                missing.append(t); continue
            out[t] = {d.strftime("%Y-%m-%d"): round(float(c), 4)
                      for d, c in h["Close"].items()}
            if i % 10 == 0:
                print(f"  ...{i}/{len(tickers)} tickers")
        except Exception as e:
            missing.append(t)
            print(f"  ! {t}: {type(e).__name__}: {e}")
    dc = _HERE / "datacache"; dc.mkdir(exist_ok=True)
    (dc / "prices.json").write_text(json.dumps(out, indent=0))
    print(f"Wrote datacache/prices.json: {len(out)}/{len(tickers)} tickers "
          f"({HISTORY_START}..{HISTORY_END}).")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
        print("Fix tickers in config.yaml or re-run; build_data.py skips uncovered cells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
