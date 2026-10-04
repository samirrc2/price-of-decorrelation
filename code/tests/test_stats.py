"""Simple unit tests for cluster-bootstrap helpers."""
from __future__ import annotations

import stats as S


def _toy_rows():
    """Tiny synthetic log: 2 tickers x 2 dates x 2 configs x 1 run x 3 agents."""
    rows = []
    for ticker in ("AAA", "BBB"):
        for date in ("2024-01-01", "2024-01-02"):
            # HOM: all BUY (high agreement)
            for agent in range(3):
                rows.append({
                    "ok": "True",
                    "direction": "BUY",
                    "config": "HOM",
                    "ticker": ticker,
                    "date": date,
                    "run_idx": "0",
                    "agent_idx": str(agent),
                })
            # HET: mixed (lower agreement)
            for agent, d in enumerate(["BUY", "SELL", "HOLD"]):
                rows.append({
                    "ok": "True",
                    "direction": d,
                    "config": "HET",
                    "ticker": ticker,
                    "date": date,
                    "run_idx": "0",
                    "agent_idx": str(agent),
                })
    return rows


def test_cluster_bootstrap_seed_stable():
    rows = _toy_rows()
    tickers = ["AAA", "BBB"]
    a = S.cluster_bootstrap_pair(rows, tickers, "HOM", "HET", draws=40, seed=7)
    b = S.cluster_bootstrap_pair(rows, tickers, "HOM", "HET", draws=40, seed=7)
    assert a["point"] == b["point"]
    assert a["ci_low"] == b["ci_low"]
    assert a["ci_high"] == b["ci_high"]


def test_cluster_bootstrap_hom_higher_than_het():
    rows = _toy_rows()
    out = S.cluster_bootstrap_pair(
        rows, ["AAA", "BBB"], "HOM", "HET", draws=40, seed=1
    )
    assert out["point"] is not None
    assert out["point"] > 0  # κ_HOM - κ_HET
    assert out["kappa_a"] is not None
    assert out["kappa_b"] is not None
    assert out["kappa_a"] > out["kappa_b"]
