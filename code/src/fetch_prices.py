"""Fetch EOD close prices for all grid tickers -> datacache/prices.json (via FMP).

Pure stdlib + `requests` and your FMP key. NO numpy/pandas/yfinance. Uses FMP's
CURRENT "stable" endpoint (historical-price-eod/light) first, with the legacy v3
endpoint as fallback, so it works on both new and old keys. Prints the raw response
for the first ticker so any auth/plan issue is visible immediately.

Key: FMP_API_KEY=... in API Keys/keys.env.txt (or exported in the shell).
"""
from __future__ import annotations
import json
import time
from pathlib import Path

import io_paths

import requests
import yaml

import secrets as secretstore

_HERE = io_paths.repo_root()
START = "2025-12-01"
END = "2026-07-01"

ENDPOINTS = [
    # (url_template, kind)  kind: "light" -> list of {date,price}; "full" -> {"historical":[{date,close}]}
    ("https://financialmodelingprep.com/stable/historical-price-eod/light"
     "?symbol={sym}&from={start}&to={end}&apikey={key}", "light"),
    ("https://financialmodelingprep.com/api/v3/historical-price-full/{sym}"
     "?from={start}&to={end}&apikey={key}", "full"),
]


def _key() -> str:
    k = secretstore.get_raw("FMP_API_KEY")
    if not k:
        raise SystemExit("No FMP_API_KEY found. Add FMP_API_KEY=... to "
                         "API Keys/keys.env.txt (next to the other keys).")
    return k


def _parse(payload, kind):
    out = {}
    rows = payload.get("historical") if (kind == "full" and isinstance(payload, dict)) else payload
    if not isinstance(rows, list):
        return None
    for row in rows:
        try:
            d = row["date"]
            c = row.get("price", row.get("close"))
            out[d] = round(float(c), 4)
        except (KeyError, ValueError, TypeError):
            continue
    return out or None


def fetch_one(ticker: str, key: str, debug=False):
    for url_t, kind in ENDPOINTS:
        url = url_t.format(sym=ticker, start=START, end=END, key=key)
        for _ in range(2):
            try:
                r = requests.get(url, timeout=30)
                if debug:
                    print(f"    [debug] {kind} status={r.status_code} body[:200]={r.text[:200]!r}")
                if r.status_code != 200:
                    time.sleep(0.6); continue
                got = _parse(r.json(), kind)
                if got:
                    return got
                break  # 200 but unparseable -> try next endpoint
            except Exception as e:
                if debug:
                    print(f"    [debug] {kind} exception: {type(e).__name__}: {e}")
                time.sleep(0.6)
    return None


def main():
    key = _key()
    cfg = yaml.safe_load(io_paths.default_config_path().read_text())
    tickers = cfg["tickers"]
    out, missing = {}, []
    for i, t in enumerate(tickers, 1):
        s = fetch_one(t, key, debug=(i == 1))   # verbose on the very first ticker
        if s and len(s) > 30:
            out[t] = s
        else:
            missing.append(t)
        if i % 10 == 0:
            print(f"  ...{i}/{len(tickers)} tickers ({len(missing)} missing)")
        time.sleep(0.12)
    dc = io_paths.data_root() / "datacache"; dc.mkdir(exist_ok=True)
    (dc / "prices.json").write_text(json.dumps(out, indent=0))
    print(f"Wrote datacache/prices.json: {len(out)}/{len(tickers)} tickers.")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
