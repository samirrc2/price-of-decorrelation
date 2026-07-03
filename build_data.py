"""Offline data builder — turns cached real data into the pipeline's inputs.

Reads (all committed, no network needed at run time):
  datacache/news_cache.json   real dated headlines per (ticker, date)
  datacache/prices.json       real EOD closes per ticker

Writes:
  inputs/<TICKER>_<DATE>.json           no-lookahead context snippet per cell
  datacache/forward_returns.json        20-trading-day forward-return sign per cell

Deterministic and idempotent. Run once before orchestrator.py (or any time to
regenerate). Enforces: snippet as-of date is a real trading day strictly BEFORE
the analysis date (no lookahead).
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent


def load_cfg():
    return yaml.safe_load((_HERE / "config.yaml").read_text())


def prior_trading_day(prices_ticker: dict, analysis_date: str) -> str:
    """Latest trading day in the price history strictly before analysis_date."""
    days = sorted(d for d in prices_ticker if d < analysis_date)
    if not days:
        raise ValueError(f"no trading day before {analysis_date} in price cache")
    return days[-1]


def forward_sign(prices_ticker: dict, analysis_date: str, fwd: int):
    """(p0, p0_date, p1, p1_date, ret, sign) using `fwd` trading days forward from
    the first trading day >= analysis_date."""
    days = sorted(prices_ticker)
    on_or_after = [d for d in days if d >= analysis_date]
    if not on_or_after:
        return None
    d0 = on_or_after[0]
    i0 = days.index(d0)
    i1 = i0 + fwd
    if i1 >= len(days):
        return None
    d1 = days[i1]
    p0, p1 = prices_ticker[d0], prices_ticker[d1]
    ret = (p1 - p0) / p0
    sign = 1 if ret > 0 else (-1 if ret < 0 else 0)
    return {"p0": p0, "p0_date": d0, "p1": p1, "p1_date": d1,
            "ret": round(ret, 5), "sign": sign}


def main():
    cfg = load_cfg()
    dc = _HERE / "datacache"
    news = json.loads((dc / "news_cache.json").read_text())
    prices = json.loads((dc / "prices.json").read_text())
    inputs_dir = _HERE / cfg["paths"]["inputs_dir"]
    inputs_dir.mkdir(exist_ok=True)
    fwd = int(cfg["forward_return_days"])

    n_snip = 0
    n_skip = 0
    fwd_returns = {}
    for ticker in cfg["tickers"]:
        if ticker not in prices:
            n_skip += len(cfg["dates"])
            continue
        for d in cfg["dates"]:
            # Skip cells with no price coverage yet (e.g. dates outside the cached
            # window). Full-study cells are populated post-gate by the connector fetch.
            if not any(day < d for day in prices[ticker]):
                n_skip += 1
                continue
            # ---- snippet (no lookahead) ----
            asof = prior_trading_day(prices[ticker], d)
            assert date.fromisoformat(asof) < date.fromisoformat(d)
            cell_news = news.get(ticker, {}).get(d)
            if cell_news:
                headline = " | ".join(cell_news["headlines"])
                fundamentals = cell_news.get("fundamentals", "")
            else:
                headline = ""
                fundamentals = ""
            (inputs_dir / f"{ticker}_{d}.json").write_text(json.dumps({
                "headline": headline,
                "fundamentals": fundamentals,
                "asof": asof,
                "source": "financial_mcp_news_cache",
            }, indent=2))
            n_snip += 1

            # ---- forward-return sign ----
            fr = forward_sign(prices[ticker], d, fwd)
            fwd_returns[f"{ticker}|{d}"] = fr

    (dc / "forward_returns.json").write_text(json.dumps(fwd_returns, indent=2))
    realized = sum(1 for v in fwd_returns.values() if v)
    print(f"Wrote {n_snip} snippets to {inputs_dir}  (skipped {n_skip} cells lacking price coverage)")
    print(f"Wrote forward_returns.json: {realized}/{len(fwd_returns)} cells realized "
          f"({fwd} trading days).")
    # quick view
    for k, v in fwd_returns.items():
        if v:
            print(f"  {k}: {v['p0_date']} {v['p0']} -> {v['p1_date']} {v['p1']} "
                  f"ret={v['ret']:+.3f} sign={v['sign']:+d}")


if __name__ == "__main__":
    main()
