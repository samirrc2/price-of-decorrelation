"""Analyze the HET-SameTier confound-control run (data/control/runs.csv).

Computes kappa for HOM and HET-SAMETIER (efficient-tier, cross-provider), the
Delta-kappa contrast, and its cluster-bootstrap 95% CI (equities, seed 42) using the
SAME method as the main study. If HOM->HET-SAMETIER still shows a substantial,
significant kappa drop, the primary de-correlation is provider-driven, not a
capability-tier artifact.  Usage: python control_kappa.py
"""
from __future__ import annotations
import csv
from pathlib import Path

import io_paths
import yaml
import metrics as M
import stats as S

_HERE = io_paths.repo_root()


def fmt(x, n=4):
    return "n/a" if x is None else f"{x:.{n}f}"


def main():
    cfg = yaml.safe_load(io_paths.resolve_config_path("configs/config_control.yaml").read_text())
    runs_csv = io_paths.resolve_data_path(cfg["paths"]["runs_csv"])
    if not runs_csv.exists():
        print(f"No {runs_csv}. Run: python src/orchestrator.py --config configs/config_control.yaml --phase full")
        return 1
    rows = list(csv.DictReader(runs_csv.open()))
    tickers = cfg["tickers"]
    k_hom, _ = M.kappa_per_run_avg(rows, "HOM")
    k_st, _ = M.kappa_per_run_avg(rows, "HET-SAMETIER")
    boot = S.cluster_bootstrap_multi(
        rows, tickers, [("HOM", "HET-SAMETIER")],
        int(cfg["bootstrap_draws"]), int(cfg["bootstrap_seed"]))[("HOM", "HET-SAMETIER")]
    dk, lo, hi = boot["point"], boot["ci_low"], boot["ci_high"]
    usable = len(M.usable(rows))
    print(f"CONTROL (capability-matched, cross-provider)  usable rows: {usable}")
    print(f"  kappa_HOM         = {fmt(k_hom)}")
    print(f"  kappa_HET-SAMETIER= {fmt(k_st)}")
    print(f"  Delta-kappa(HOM - HET-SAMETIER) = {fmt(dk)}  95% CI [{fmt(lo)}, {fmt(hi)}]")
    if dk is not None and lo is not None:
        if dk > 0 and lo > 0:
            print("  => Provider diversity de-correlates even at matched capability "
                  "(CI excludes 0): confound largely ruled out.")
        elif dk > 0:
            print("  => Positive but CI includes 0: weak/ambiguous at matched capability.")
        else:
            print("  => No drop at matched capability: original effect may be capability-driven.")
    # write a one-paragraph result for the paper
    (_HERE / "control_result.md").write_text(
        f"# HET-SameTier control result\n\n"
        f"kappa_HOM = {fmt(k_hom)}; kappa_HET-SAMETIER = {fmt(k_st)}; "
        f"Delta-kappa = {fmt(dk)} (95% CI [{fmt(lo)}, {fmt(hi)}]), "
        f"cluster bootstrap over equities, seed 42, {usable} usable rows.\n")
    print("Wrote control_result.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
