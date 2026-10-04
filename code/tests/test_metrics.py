"""Simple unit tests for Fleiss' kappa and row filters."""
from __future__ import annotations

import metrics as M


def test_fleiss_perfect_agreement():
    # Every subject: all 5 raters say BUY
    cells = {("T", f"d{i}"): ["BUY"] * 5 for i in range(10)}
    assert M.fleiss_kappa(cells) == 1.0


def test_fleiss_too_few_subjects_returns_none():
    cells = {("T", "d0"): ["BUY", "SELL", "HOLD"]}
    assert M.fleiss_kappa(cells) is None


def test_pairwise_agreement_unanimous():
    assert M.pairwise_agreement(["BUY", "BUY", "BUY"]) == 1.0


def test_pairwise_agreement_split():
    # 2 BUY, 1 SELL -> one agreeing pair out of three
    p = M.pairwise_agreement(["BUY", "BUY", "SELL"])
    assert p is not None
    assert abs(p - (1.0 / 3.0)) < 1e-12


def test_usable_filters_bad_rows():
    rows = [
        {"ok": "True", "direction": "BUY"},
        {"ok": "False", "direction": "BUY"},
        {"ok": "True", "direction": "MAYBE"},
        {"ok": "True", "direction": "SELL"},
    ]
    got = M.usable(rows)
    assert len(got) == 2
    assert {r["direction"] for r in got} == {"BUY", "SELL"}
