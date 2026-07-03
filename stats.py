"""Inferential layer: cluster bootstrap CI on Delta-kappa, run-to-run variance /
sampling-nondeterminism bias, and the power / cells-needed calculation.
"""
from __future__ import annotations
import math
import random
from collections import defaultdict

import metrics as M


# --------------------------------------------------------------------------- #
# Cluster bootstrap over tickers -> 95% CI on Delta-kappa
# --------------------------------------------------------------------------- #
def _kappa_for_ticker_subset(rows, config, tickers_multiset):
    """Average within-run Fleiss kappa restricted to a (possibly repeated) set of
    tickers. Repeats are honoured by suffixing a replica id so a ticker drawn
    twice contributes as two independent clusters."""
    # group usable rows by (ticker,date,run)
    by = defaultdict(list)
    for r in M.usable(rows):
        if r["config"] != config:
            continue
        by[(r["ticker"], r["date"], int(r["run_idx"]))].append(r["direction"])
    runs = sorted({k[2] for k in by})
    ks = []
    for run in runs:
        cells = {}
        for rep, t in enumerate(tickers_multiset):
            for (tt, d, rr), dirs in by.items():
                if tt == t and rr == run:
                    cells[(rep, t, d)] = dirs  # rep keeps duplicate draws distinct
        k = M.fleiss_kappa(cells)
        if k is not None:
            ks.append(k)
    return sum(ks) / len(ks) if ks else None


def cluster_bootstrap_pair(rows, tickers, cfg_a, cfg_b, draws=2000, seed=42):
    """Cluster bootstrap (resample TICKERS) for Δκ = κ(cfg_a) − κ(cfg_b).
    Generalizes the HOM−HET bootstrap to any config pair (for the 3-config frontier)."""
    rng = random.Random(seed)
    pa = _kappa_for_ticker_subset(rows, cfg_a, tickers)
    pb = _kappa_for_ticker_subset(rows, cfg_b, tickers)
    point = (pa - pb) if (pa is not None and pb is not None) else None
    deltas = []
    n = len(tickers)
    for _ in range(draws):
        sample = [tickers[rng.randrange(n)] for _ in range(n)]
        ka = _kappa_for_ticker_subset(rows, cfg_a, sample)
        kb = _kappa_for_ticker_subset(rows, cfg_b, sample)
        if ka is None or kb is None:
            continue
        deltas.append(ka - kb)
    deltas.sort()
    if len(deltas) < 20:
        return {"pair": f"{cfg_a}-{cfg_b}", "point": point, "ci_low": None,
                "ci_high": None, "kappa_a": pa, "kappa_b": pb, "n_valid": len(deltas)}
    return {"pair": f"{cfg_a}-{cfg_b}", "point": point,
            "ci_low": deltas[int(0.025 * len(deltas))],
            "ci_high": deltas[int(0.975 * len(deltas)) - 1],
            "kappa_a": pa, "kappa_b": pb, "n_valid": len(deltas)}


def cluster_bootstrap_delta_kappa(rows, tickers, draws=2000, seed=20260703):
    rng = random.Random(seed)
    point_hom = _kappa_for_ticker_subset(rows, "HOM", tickers)
    point_het = _kappa_for_ticker_subset(rows, "HET", tickers)
    point_delta = (point_hom - point_het) if (point_hom is not None and point_het is not None) else None

    deltas = []
    n = len(tickers)
    for _ in range(draws):
        sample = [tickers[rng.randrange(n)] for _ in range(n)]
        kh = _kappa_for_ticker_subset(rows, "HOM", sample)
        ke = _kappa_for_ticker_subset(rows, "HET", sample)
        if kh is None or ke is None:
            continue
        deltas.append(kh - ke)
    deltas.sort()
    if len(deltas) < 20:
        return {"point_delta": point_delta, "ci_low": None, "ci_high": None,
                "kappa_hom": point_hom, "kappa_het": point_het,
                "n_valid_draws": len(deltas)}
    lo = deltas[int(0.025 * len(deltas))]
    hi = deltas[int(0.975 * len(deltas)) - 1]
    return {"point_delta": point_delta, "ci_low": lo, "ci_high": hi,
            "kappa_hom": point_hom, "kappa_het": point_het,
            "n_valid_draws": len(deltas)}


# --------------------------------------------------------------------------- #
# Run-to-run variance + sampling-nondeterminism bias
# --------------------------------------------------------------------------- #
def run_variance_and_bias(rows):
    """For each config: variance of per-run kappa across the 3 seeds, plus the
    within-run vs cross-run kappa comparison that reveals the direction of the
    sampling-nondeterminism artifact.

    Interpretation: within-run pools 5 agents produced under ONE sampling draw;
    cross-run pools 15 agents across independent draws. If nondeterminism inflates
    HOM agreement, within-run κ_HOM will sit ABOVE cross-run κ_HOM (identical model
    agrees with itself more within a single stochastic context than across draws).
    A positive (within - cross) gap for HOM therefore signals upward bias in κ_HOM.
    """
    out = {}
    for cfg in ("HOM", "HET"):
        avg, ks = M.kappa_per_run_avg(rows, cfg)
        cross = M.kappa_cross_run(rows, cfg)
        var = None
        if len(ks) >= 2:
            m = sum(ks) / len(ks)
            var = sum((k - m) ** 2 for k in ks) / (len(ks) - 1)
        gap = (avg - cross) if (avg is not None and cross is not None) else None
        out[cfg] = {
            "kappa_within_run_avg": avg,
            "kappa_per_run": ks,
            "kappa_cross_run_pooled": cross,
            "run_variance": var,
            "within_minus_cross": gap,
        }
    return out


# --------------------------------------------------------------------------- #
# Power / cells-needed
# --------------------------------------------------------------------------- #
def _norm_ppf(p):
    # Acklam's rational approximation to the inverse normal CDF.
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def paired_cell_agreement_diffs(rows):
    """Per (ticker,date): mean-over-runs pairwise agreement for HOM minus HET.
    This per-cell paired difference is the operational effect the power calc sizes.
    Returns list of diffs."""
    def agree_by_cell(cfg):
        by = M.cells_by_run(rows, cfg)
        acc = defaultdict(list)
        for (t, d, _run), dirs in by.items():
            pa = M.pairwise_agreement(dirs)
            if pa is not None:
                acc[(t, d)].append(pa)
        return {k: sum(v) / len(v) for k, v in acc.items()}
    hom = agree_by_cell("HOM")
    het = agree_by_cell("HET")
    diffs = [hom[k] - het[k] for k in hom if k in het]
    return diffs


def power_calc(rows, alpha=0.05, target=0.80):
    """Cells needed for `target` power at two-sided `alpha`, using the observed
    per-cell paired agreement difference (proxy for Delta-kappa at the cell level).
    """
    diffs = paired_cell_agreement_diffs(rows)
    n = len(diffs)
    if n < 2:
        return {"error": "insufficient cells for power calc", "n_cells_observed": n}
    mean = sum(diffs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (n - 1))
    if sd == 0 or mean == 0:
        return {"observed_mean_diff": mean, "observed_sd": sd,
                "dz": None, "cells_needed": None,
                "note": "zero effect or zero variance — effect not resolvable/ trivially resolved",
                "n_cells_observed": n}
    dz = abs(mean) / sd            # standardized paired effect size
    z_a = _norm_ppf(1 - alpha / 2)
    z_b = _norm_ppf(target)
    cells = ((z_a + z_b) / dz) ** 2
    cells_needed = int(math.ceil(cells))
    return {"observed_mean_diff": mean, "observed_sd": sd, "dz": dz,
            "z_alpha": z_a, "z_beta": z_b,
            "cells_needed": cells_needed, "n_cells_observed": n}
