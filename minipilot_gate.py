"""Phase 1.5 — gate on the new model set (reads minipilot/runs.csv only).

Computes independent-draw Δκ(HOM−HET), per-cell effect size, power (cells for 80%),
and the projected 400-cell full-study cost. Writes minipilot_verdict.md.

GATE: proceed to Phase 2 iff cells-for-80%-power ≤ 400 AND projected full-study
cost ≤ $75. If Δκ ≤ 0 or power infeasible: STOP.
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

import yaml

import metrics as M
import stats as S

_HERE = Path(__file__).resolve().parent


def fmt(x, n=4):
    return "n/a" if x is None else f"{x:.{n}f}"


def main():
    cfg = yaml.safe_load((_HERE / "config.yaml").read_text())
    mp = cfg["minipilot"]
    runs_csv = _HERE / mp["paths"]["runs_csv"]
    if not runs_csv.exists():
        print(f"No {runs_csv} — run: python orchestrator.py --phase minipilot")
        return 1
    rows = list(csv.DictReader(runs_csv.open()))
    tickers = mp["tickers"]
    max_cells = int(mp["gate"]["max_cells"])
    max_cost = float(mp["gate"]["max_cost_usd"])
    full_cells = int(cfg["gate"]["max_cells"])   # the planned full study = 400 cells
    n_runs = int(cfg["runs"])

    # primary Δκ(HOM−HET), independent-draw, cluster bootstrap over tickers
    boot = S.cluster_bootstrap_pair(rows, tickers, "HOM", "HET",
                                    draws=int(cfg["bootstrap_draws"]),
                                    seed=int(cfg["bootstrap_seed"]))
    power = S.power_calc(rows, alpha=float(cfg["power_alpha"]), target=float(cfg["power_target"]))
    cells_needed = power.get("cells_needed")

    # projected full-study cost = full_cells × runs × Σ_config cost-per-decision
    cost = M.cost_summary(rows)
    per_cell = n_runs * sum(cost.get(c, {}).get("mean_per_decision_usd", 0.0)
                            for c in cfg["configs"])
    projected = full_cells * per_cell

    dk = boot["point"]
    infeasible = (cells_needed is None)
    if (dk is not None and dk <= 0) or infeasible:
        verdict = "STOP"
    elif cells_needed <= max_cells and projected <= max_cost:
        verdict = "PROCEED"
    else:
        verdict = "STOP"

    L = [f"# Mini-pilot verdict (Phase 1.5) — {verdict}\n",
         f"- Primary **Δκ(HOM−HET) = {fmt(dk)}**  95% CI "
         f"[{fmt(boot['ci_low'])}, {fmt(boot['ci_high'])}] "
         f"(κ_HOM={fmt(boot['kappa_a'])}, κ_HET={fmt(boot['kappa_b'])})",
         f"- Per-cell effect d̄/sd = {fmt(power.get('dz'))} "
         f"(d̄={fmt(power.get('observed_mean_diff'))}, sd={fmt(power.get('observed_sd'))}, "
         f"cells={power.get('n_cells_observed')})",
         f"- **Cells for 80% power = {cells_needed if cells_needed else 'n/a'}** (gate ≤ {max_cells})",
         f"- **Projected full-study cost (at {full_cells} cells) = "
         f"${projected:,.2f}** (gate ≤ ${max_cost:.0f})\n",
         f"## {verdict}\n"]
    if verdict == "PROCEED":
        L.append("Both gate conditions met on the new model set. Proceed to Phase 1 "
                 "freeze (if not already frozen) and Phase 2 single execution.")
    else:
        why = []
        if dk is not None and dk <= 0:
            why.append(f"Δκ ≤ 0 ({fmt(dk)}) — no measurable de-correlation on these models")
        if infeasible:
            why.append("power infeasible (zero/degenerate effect or variance)")
        if cells_needed is not None and cells_needed > max_cells:
            why.append(f"cells-for-power {cells_needed} > {max_cells}")
        if projected > max_cost:
            why.append(f"projected cost ${projected:,.2f} > ${max_cost:.0f}")
        L.append("Do NOT proceed. Reason(s): " + "; ".join(why) + ".")
        L.append("\nAwait instruction (per spec — no scope expansion without sign-off).")

    # independence sanity note
    L.append("\n---\nRun `python verify_independence.py` on minipilot/runs.csv "
             "(point PATH there) to confirm same-model agents produced distinct raw "
             "completions before trusting κ_HOM.")
    (_HERE / "minipilot_verdict.md").write_text("\n".join(L) + "\n")
    print(f"VERDICT: {verdict}  (cells={cells_needed}, projected=${projected:,.2f}, "
          f"Δκ={fmt(dk)})")
    print("Wrote minipilot_verdict.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
