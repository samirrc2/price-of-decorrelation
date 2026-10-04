"""Per-run metrics: Fleiss' kappa, majority vote, cost, and the NOISY accuracy proxy.

All functions operate on the rows of runs.csv (list of dicts). Only ok==True rows
with a valid direction are used for agreement.
"""
from __future__ import annotations
import math
from collections import defaultdict, Counter
from typing import Iterable

DIRECTIONS = ["BUY", "HOLD", "SELL"]
_DIR_IDX = {d: i for i, d in enumerate(DIRECTIONS)}


# --------------------------------------------------------------------------- #
# Fleiss' kappa
# --------------------------------------------------------------------------- #
def _counts_matrix(cells: dict[tuple, list[str]]) -> list[list[int]]:
    """cells: {subject_key: [direction, direction, ...]} -> N[i][j] count matrix.
    Only subjects with >=2 ratings are usable. Returns rows (one per subject)."""
    rows = []
    for _key, dirs in cells.items():
        if len(dirs) < 2:
            continue
        c = Counter(dirs)
        rows.append([c.get(d, 0) for d in DIRECTIONS])
    return rows


def fleiss_kappa(cells: dict[tuple, list[str]]) -> float | None:
    """Fleiss' kappa over subjects (cells), each rated by n raters (agents).

    Requires a FIXED number of raters per subject. If subjects have differing
    rater counts (e.g. some agent calls failed) we drop to the modal rater count
    to keep the estimator well-defined, and return None if <2 subjects remain.
    """
    rows = _counts_matrix(cells)
    if not rows:
        return None
    rater_counts = [sum(r) for r in rows]
    n = Counter(rater_counts).most_common(1)[0][0]
    rows = [r for r in rows if sum(r) == n]
    N = len(rows)
    if N < 2 or n < 2:
        return None
    # P_i per subject
    Pi = [(sum(x * x for x in r) - n) / (n * (n - 1)) for r in rows]
    P_bar = sum(Pi) / N
    # marginal category proportions
    totals = [0] * len(DIRECTIONS)
    for r in rows:
        for j, x in enumerate(r):
            totals[j] += x
    denom = N * n
    p = [t / denom for t in totals]
    P_e = sum(pj * pj for pj in p)
    if abs(1 - P_e) < 1e-12:
        return 1.0  # perfect/degenerate agreement
    return (P_bar - P_e) / (1 - P_e)


def pairwise_agreement(dirs: list[str]) -> float | None:
    """Per-cell observed agreement P_i (prob two random raters agree). Well-defined
    for a single cell with n>=2 raters — this is the unit used for the power calc."""
    n = len(dirs)
    if n < 2:
        return None
    c = Counter(dirs)
    return (sum(v * v for v in c.values()) - n) / (n * (n - 1))


# --------------------------------------------------------------------------- #
# Grouping helpers
# --------------------------------------------------------------------------- #
def usable(rows: Iterable[dict]) -> list[dict]:
    return [r for r in rows if str(r.get("ok")) == "True" and r.get("direction") in _DIR_IDX]


def cells_by_run(rows, config):
    """{(ticker,date,run): [dirs]} for one config — within-run agreement."""
    out = defaultdict(list)
    for r in usable(rows):
        if r["config"] != config:
            continue
        out[(r["ticker"], r["date"], int(r["run_idx"]))].append(r["direction"])
    return out


def cells_pooled(rows, config):
    """{(ticker,date): [dirs across ALL runs]} — cross-run pooled agreement."""
    out = defaultdict(list)
    for r in usable(rows):
        if r["config"] != config:
            continue
        out[(r["ticker"], r["date"])].append(r["direction"])
    return out


def kappa_per_run_avg(rows, config):
    """Average of the per-run Fleiss kappa (κ as specified: within-run, averaged)."""
    by = cells_by_run(rows, config)
    runs = sorted({k[2] for k in by})
    ks = []
    for run in runs:
        cells = {(t, d): dirs for (t, d, rr), dirs in by.items() if rr == run}
        k = fleiss_kappa(cells)
        if k is not None:
            ks.append(k)
    if not ks:
        return None, []
    return sum(ks) / len(ks), ks


def kappa_cross_run(rows, config):
    """Fleiss kappa with all 3 runs' agents pooled per cell (n≈15 raters)."""
    return fleiss_kappa(cells_pooled(rows, config))


# --------------------------------------------------------------------------- #
# Majority vote + conviction
# --------------------------------------------------------------------------- #
def majority_vote(rows, config):
    """{(ticker,date): (direction, mean_conviction, n_votes)} pooling all runs."""
    votes = defaultdict(list)
    convs = defaultdict(list)
    for r in usable(rows):
        if r["config"] != config:
            continue
        votes[(r["ticker"], r["date"])].append(r["direction"])
        try:
            convs[(r["ticker"], r["date"])].append(int(r["conviction"]))
        except (ValueError, TypeError):
            pass
    out = {}
    for k, ds in votes.items():
        c = Counter(ds)
        top = c.most_common()
        # deterministic tie-break: BUY>HOLD>SELL order preference then alnum
        best = sorted(top, key=lambda kv: (-kv[1], DIRECTIONS.index(kv[0])))[0][0]
        mc = sum(convs[k]) / len(convs[k]) if convs[k] else float("nan")
        out[k] = (best, mc, len(ds))
    return out


# --------------------------------------------------------------------------- #
# Cost
# --------------------------------------------------------------------------- #
def cost_summary(rows):
    """Return per-config cost stats and cost per ensemble-decision.

    cost per ensemble-decision = mean cost to produce ONE 5-agent decision (one
    run of one config on one cell) = sum of the 5 agent-call costs, averaged over
    all (ticker,date,run) groups.
    """
    per_call = defaultdict(list)      # config -> [cost]
    per_decision = defaultdict(lambda: defaultdict(float))  # config -> group -> sum cost
    for r in rows:
        try:
            c = float(r["cost_usd"])
        except (ValueError, TypeError, KeyError):
            continue
        cfg = r["config"]
        per_call[cfg].append(c)
        per_decision[cfg][(r["ticker"], r["date"], r["run_idx"])] += c
    out = {}
    for cfg in per_call:
        calls = per_call[cfg]
        decs = list(per_decision[cfg].values())
        out[cfg] = {
            "n_calls": len(calls),
            "total_usd": sum(calls),
            "mean_per_call_usd": sum(calls) / len(calls) if calls else 0.0,
            "mean_per_decision_usd": sum(decs) / len(decs) if decs else 0.0,
        }
    return out


# --------------------------------------------------------------------------- #
# NOISY accuracy proxy (forward-return sign)
# --------------------------------------------------------------------------- #
def forward_return_signs(tickers, dates, fwd_days):
    """{(ticker,date): sign in {+1,-1,0} or None}.

    Prefers the offline cache datacache/forward_returns.json (built by build_data.py
    from real MCP prices). Falls back to yfinance only if the cache is absent.
    """
    import json
    from pathlib import Path
    cache = Path(__file__).resolve().parent / "datacache" / "forward_returns.json"
    if cache.exists():
        try:
            fr = json.loads(cache.read_text())
            signs = {}
            for t in tickers:
                for d in dates:
                    v = fr.get(f"{t}|{d}")
                    signs[(t, d)] = (v.get("sign") if v else None)
            return signs, None
        except Exception as e:
            return {}, f"forward_returns cache unreadable: {e}"
    try:
        import yfinance as yf  # noqa
        import pandas as pd    # noqa
    except Exception as e:
        return {}, f"no cache and yfinance/pandas not installed: {e}"
    from datetime import date as _date, timedelta
    signs = {}
    try:
        for t in tickers:
            start = min(dates)
            end = (_date.fromisoformat(max(dates)) + timedelta(days=fwd_days * 3 + 10)).isoformat()
            hist = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
            if hist.empty:
                for d in dates:
                    signs[(t, d)] = None
                continue
            closes = hist["Close"]
            idx = closes.index
            for d in dates:
                dd = pd.Timestamp(d, tz=idx.tz) if idx.tz is not None else pd.Timestamp(d)
                pos = idx.searchsorted(dd)
                if pos >= len(closes) or pos + fwd_days >= len(closes):
                    signs[(t, d)] = None
                    continue
                p0 = float(closes.iloc[pos])
                p1 = float(closes.iloc[pos + fwd_days])
                ret = (p1 - p0) / p0
                signs[(t, d)] = 1 if ret > 0 else (-1 if ret < 0 else 0)
        return signs, None
    except Exception as e:
        return {}, f"fetch failed: {e}"


def accuracy_proxy(rows, config, signs):
    """Hit-rate of majority direction vs forward-return sign. HOLD = abstain.
    Returns (hit_rate or None, n_scored, n_hold_abstained)."""
    if not signs:
        return None, 0, 0
    mv = majority_vote(rows, config)
    hits = scored = holds = 0
    for (t, d), (direction, _mc, _n) in mv.items():
        s = signs.get((t, d))
        if s is None:
            continue
        if direction == "HOLD":
            holds += 1
            continue
        pred = 1 if direction == "BUY" else -1
        scored += 1
        if pred == s or (s == 0):  # zero return: neither right nor wrong; count neutral as hit-half? treat as miss-neutral
            hits += 1 if pred == s else 0
    return (hits / scored if scored else None), scored, holds
