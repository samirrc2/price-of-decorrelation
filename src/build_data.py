"""Offline data builder — deterministic, no-lookahead price-derived context.

Reads datacache/prices.json (from fetch_prices.py). For each (ticker, date) cell it
builds a context snippet from ONLY the price history up to the as-of date (the prior
trading day), and computes the 20-trading-day forward-return sign for the accuracy
proxy. No news, no network, no lookahead. Scales to any grid.

Snippet features (all as-of the prior trading day): last close, trailing 1w/1m/3m
returns, 21-day annualized realized volatility, and position within the 63-day range.
"""
from __future__ import annotations
import json
import math
from datetime import date
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parents[1]
MIN_HISTORY = 25   # trading days required before as-of to build a snippet


def load_cfg():
    return yaml.safe_load((_HERE / "configs" / "config.yaml").read_text())


def _ret(closes, n):
    if len(closes) <= n:
        return None
    return closes[-1] / closes[-1 - n] - 1.0


def _pct(x):
    return "n/a" if x is None else f"{x*100:+.1f}%"


def build_snippet(ticker, asof, closes):
    """closes: list of daily closes up to and INCLUDING the as-of day (ascending)."""
    last = closes[-1]
    r1w, r1m, r3m = _ret(closes, 5), _ret(closes, 21), _ret(closes, 63)
    # 21-day annualized realized vol
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(max(1, len(closes) - 21), len(closes))]
    vol = (math.sqrt(252) * (sum((x - sum(rets) / len(rets)) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
           if len(rets) > 1 else None)
    window = closes[-63:] if len(closes) >= 63 else closes
    hi, lo = max(window), min(window)
    from_hi = last / hi - 1.0 if hi else None
    abv_lo = last / lo - 1.0 if lo else None
    text = (
        f"Price context for {ticker} as of {asof} (uses only data on/before this date). "
        f"Last close ${last:.2f}. Trailing returns: 1-week {_pct(r1w)}, 1-month {_pct(r1m)}, "
        f"3-month {_pct(r3m)}. 21-day annualized volatility "
        f"{('%.0f%%' % (vol*100)) if vol is not None else 'n/a'}. "
        f"Price is {_pct(from_hi)} from its 63-day high and {_pct(abv_lo)} above its 63-day low."
    )
    return text


def main():
    cfg = load_cfg()
    dc = _HERE / "datacache"
    prices = json.loads((dc / "prices.json").read_text())
    inputs_dir = _HERE / cfg["paths"]["inputs_dir"]
    inputs_dir.mkdir(exist_ok=True)
    fwd = int(cfg["forward_return_days"])

    n_snip = n_skip = 0
    fwd_returns = {}
    for ticker in cfg["tickers"]:
        series = prices.get(ticker)
        if not series:
            n_skip += len(cfg["dates"]); continue
        days = sorted(series)
        for d in cfg["dates"]:
            prior = [x for x in days if x < d]
            if len(prior) < MIN_HISTORY:
                n_skip += 1; continue
            asof = prior[-1]
            closes = [series[x] for x in prior]
            (inputs_dir / f"{ticker}_{d}.json").write_text(json.dumps({
                "headline": build_snippet(ticker, asof, closes),
                "fundamentals": "",
                "asof": asof,
                "source": "price_derived",
            }, indent=2))
            n_snip += 1
            # forward-return sign: first trading day >= d, +fwd td
            on_after = [x for x in days if x >= d]
            fr = None
            if on_after:
                i0 = days.index(on_after[0]); i1 = i0 + fwd
                if i1 < len(days):
                    p0, p1 = series[days[i0]], series[days[i1]]
                    r = (p1 - p0) / p0
                    fr = {"p0": p0, "p0_date": days[i0], "p1": p1, "p1_date": days[i1],
                          "ret": round(r, 5), "sign": 1 if r > 0 else (-1 if r < 0 else 0)}
            fwd_returns[f"{ticker}|{d}"] = fr

    (dc / "forward_returns.json").write_text(json.dumps(fwd_returns, indent=2))
    realized = sum(1 for v in fwd_returns.values() if v)
    print(f"Wrote {n_snip} price-derived snippets to {inputs_dir}  "
          f"(skipped {n_skip} cells lacking history/coverage).")
    print(f"forward_returns.json: {realized}/{len(fwd_returns)} cells realized ({fwd} td).")


if __name__ == "__main__":
    main()
