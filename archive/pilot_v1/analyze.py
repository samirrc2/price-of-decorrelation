"""Read runs.csv -> write metrics_summary.md, power_calc.md, verdict.md.

Pure post-processing: makes NO API calls. Safe to re-run any time.
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

import yaml

import metrics as M
import stats as S

_HERE = Path(__file__).resolve().parent


def load_cfg():
    return yaml.safe_load((_HERE / "config.yaml").read_text())


def load_rows(runs_csv: Path):
    with runs_csv.open() as f:
        return list(csv.DictReader(f))


def fmt(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


def main():
    cfg = load_cfg()
    runs_csv = _HERE / cfg["paths"]["runs_csv"]
    if not runs_csv.exists():
        print(f"No {runs_csv}. Run orchestrator.py first.")
        return 1
    rows = load_rows(runs_csv)
    ok_rows = M.usable(rows)
    n_total = len(rows)
    n_ok = len(ok_rows)

    # ---- agreement ----
    k_hom, hom_ks = M.kappa_per_run_avg(rows, "HOM")
    k_het, het_ks = M.kappa_per_run_avg(rows, "HET")
    dkappa = (k_hom - k_het) if (k_hom is not None and k_het is not None) else None

    # ---- bootstrap CI ----
    boot = S.cluster_bootstrap_delta_kappa(
        rows, cfg["tickers"], draws=int(cfg["bootstrap_draws"]),
        seed=int(cfg["seed_master"]))

    # ---- variance + bias ----
    vb = S.run_variance_and_bias(rows)

    # ---- cost ----
    cost = M.cost_summary(rows)

    # ---- accuracy proxy ----
    signs, sign_err = M.forward_return_signs(
        cfg["tickers"], cfg["dates"], int(cfg["forward_return_days"]))
    acc_hom = M.accuracy_proxy(rows, "HOM", signs)
    acc_het = M.accuracy_proxy(rows, "HET", signs)

    # ---- power ----
    power = S.power_calc(rows, alpha=float(cfg["power_alpha"]),
                         target=float(cfg["power_target"]))

    # ---- projected full-study cost ----
    runs_per_cell = int(cfg["runs"])
    cpd_hom = cost.get("HOM", {}).get("mean_per_decision_usd", 0.0)
    cpd_het = cost.get("HET", {}).get("mean_per_decision_usd", 0.0)
    cost_per_cell = runs_per_cell * (cpd_hom + cpd_het)
    cells_needed = power.get("cells_needed")
    projected_cost = (cells_needed * cost_per_cell) if cells_needed else None

    _write_metrics_md(cfg, rows, n_total, n_ok, k_hom, hom_ks, k_het, het_ks,
                      dkappa, boot, vb, cost, signs, sign_err, acc_hom, acc_het)
    _write_power_md(cfg, power, cost_per_cell, cost_per_cell, cells_needed,
                    projected_cost, cpd_hom, cpd_het, runs_per_cell)
    verdict = _write_verdict_md(cfg, boot, cells_needed, projected_cost, power)

    print("Wrote metrics_summary.md, power_calc.md, verdict.md")
    print(f"VERDICT: {verdict}")
    return 0


def _write_metrics_md(cfg, rows, n_total, n_ok, k_hom, hom_ks, k_het, het_ks,
                      dkappa, boot, vb, cost, signs, sign_err, acc_hom, acc_het):
    L = []
    L.append("# Metrics summary\n")
    L.append(f"- Calls logged: **{n_total}**  |  usable (ok + valid direction): **{n_ok}**")
    parse_fail = n_total - n_ok
    L.append(f"- Unusable (API error or JSON parse failure): **{parse_fail}**\n")

    snip_sources = {}
    for r in rows:
        snip_sources[r.get("snippet_source", "?")] = snip_sources.get(r.get("snippet_source", "?"), 0) + 1
    L.append(f"- Context snippet provenance: {snip_sources}")
    if snip_sources.get("constructed_placeholder"):
        L.append("  - ⚠️ Some/all cells used a **neutral constructed placeholder** "
                 "(no curated snippet in inputs/). Agreement then reflects model priors, "
                 "not reaction to shared news — note in threats to validity.\n")

    L.append("\n## 1. Within-ensemble agreement (Fleiss' κ, within-run, averaged)\n")
    L.append("| config | κ (avg) | per-run κ |")
    L.append("|---|---|---|")
    L.append(f"| HOM | {fmt(k_hom)} | {', '.join(fmt(k) for k in hom_ks)} |")
    L.append(f"| HET | {fmt(k_het)} | {', '.join(fmt(k) for k in het_ks)} |")
    L.append(f"\n**Δκ = κ_HOM − κ_HET = {fmt(dkappa)}**")
    L.append("\n> κ_HOM > κ_HET (positive Δκ) is the expected direction: homogeneous "
             "ensembles are more internally correlated. The pilot asks whether Δκ is "
             "large and stable enough to measure affordably.\n")

    L.append("\n### Cluster bootstrap 95% CI on Δκ (resample tickers)\n")
    L.append(f"- point Δκ (full sample): **{fmt(boot['point_delta'])}**")
    L.append(f"- 95% CI: **[{fmt(boot['ci_low'])}, {fmt(boot['ci_high'])}]** "
             f"(from {boot['n_valid_draws']} valid draws of {cfg['bootstrap_draws']})")

    L.append("\n## 2. Majority-vote decisions + mean conviction\n")
    for c in ("HOM", "HET"):
        L.append(f"\n**{c}**")
        L.append("| ticker | date | majority | mean conv | n votes |")
        L.append("|---|---|---|---|---|")
        mv = M.majority_vote(rows, c)
        for (t, d), (dirn, mc, nn) in sorted(mv.items()):
            L.append(f"| {t} | {d} | {dirn} | {fmt(mc,2)} | {nn} |")

    L.append("\n## 3. Cost\n")
    L.append("| config | calls | total $ | mean $/call | mean $/ensemble-decision |")
    L.append("|---|---|---|---|---|")
    for c in ("HOM", "HET"):
        cc = cost.get(c, {})
        L.append(f"| {c} | {cc.get('n_calls',0)} | {fmt(cc.get('total_usd',0),4)} | "
                 f"{fmt(cc.get('mean_per_call_usd',0),6)} | {fmt(cc.get('mean_per_decision_usd',0),6)} |")

    L.append("\n## 4. Accuracy proxy — ⚠️ NOISY, DO NOT DRAW CONCLUSIONS\n")
    L.append("20-trading-day forward-return sign vs pooled majority direction "
             "(HOLD = abstain). Pilot-scale; recorded only.\n")
    if sign_err:
        L.append(f"- forward returns unavailable: {sign_err}")
    else:
        for c, (hr, scored, holds) in (("HOM", acc_hom), ("HET", acc_het)):
            L.append(f"- {c}: hit-rate {fmt(hr,3)} over {scored} directional cells "
                     f"({holds} HOLD-abstained)")

    L.append("\n## 6. Run-to-run variance & sampling-nondeterminism bias\n")
    L.append("| config | κ within-run avg | κ cross-run pooled | within−cross | run variance |")
    L.append("|---|---|---|---|---|")
    for c in ("HOM", "HET"):
        v = vb[c]
        L.append(f"| {c} | {fmt(v['kappa_within_run_avg'])} | {fmt(v['kappa_cross_run_pooled'])} | "
                 f"{fmt(v['within_minus_cross'])} | {fmt(v['run_variance'],6)} |")
    hom_gap = vb["HOM"]["within_minus_cross"]
    if hom_gap is not None:
        direction = ("UPWARD (κ_HOM inflated by within-run sampling correlation)"
                     if hom_gap > 0 else
                     "downward / none (within-run not above cross-run)")
        L.append(f"\n**Direction of bias for κ_HOM: {direction}.** within−cross = {fmt(hom_gap)}. "
                 "A positive gap means a single stochastic sampling context makes identical "
                 "models agree with themselves more than they do across independent draws, "
                 "inflating the naive within-run κ_HOM.")
    (_HERE / "metrics_summary.md").write_text("\n".join(L) + "\n")


def _write_power_md(cfg, power, cost_per_cell_a, cost_per_cell, cells_needed,
                    projected_cost, cpd_hom, cpd_het, runs_per_cell):
    L = []
    L.append("# Power calculation\n")
    L.append("## Method\n")
    L.append("Fleiss' κ is a scalar per config, so power is sized on the **per-cell "
             "paired agreement difference** that underlies Δκ: for each (ticker,date) "
             "cell we take the mean-over-runs pairwise agreement P for HOM and for HET, "
             "and their difference d = P_HOM − P_HET. Under a paired design the "
             "standardized effect is d̄/sd(d); cells for target power at two-sided α "
             "follow n = ((z_{1−α/2} + z_{power}) / (d̄/sd))².\n")
    L.append("## Assumptions & caveats\n")
    L.append("- Cells treated as i.i.d. paired units (ignores ticker/date clustering — "
             "the bootstrap CI in metrics_summary is the clustering-aware check).")
    L.append("- Normal approximation; small-n pilots make d̄/sd itself noisy, so treat "
             "cells-needed as an order-of-magnitude estimate.")
    L.append("- Per-cell pairwise agreement is a proxy for κ at the cell level; it moves "
             "monotonically with κ but is not identical.\n")
    L.append("## Observed inputs\n")
    if power.get("error"):
        L.append(f"- {power['error']} (n cells = {power.get('n_cells_observed')})")
    else:
        L.append(f"- cells observed: {power.get('n_cells_observed')}")
        L.append(f"- mean paired diff d̄: {fmt(power.get('observed_mean_diff'))}")
        L.append(f"- sd(d): {fmt(power.get('observed_sd'))}")
        L.append(f"- standardized effect d̄/sd: {fmt(power.get('dz'))}")
        L.append(f"- z_(1−α/2)={fmt(power.get('z_alpha'),3)}, z_power={fmt(power.get('z_beta'),3)}")
    L.append(f"\n## Result\n")
    L.append(f"- **Cells needed for {int(float(cfg['power_target'])*100)}% power "
             f"at α={cfg['power_alpha']} (two-sided): {cells_needed if cells_needed else 'n/a'}**")
    L.append("\n## Projected full-study cost\n")
    L.append(f"- cost per ensemble-decision: HOM {fmt(cpd_hom,6)}, HET {fmt(cpd_het,6)} USD")
    L.append(f"- runs per cell: {runs_per_cell}  →  cost per cell (both configs): "
             f"{fmt(cost_per_cell,6)} USD")
    L.append(f"- **projected full-study API cost = cells_needed × cost/cell = "
             f"{('$'+format(projected_cost, ',.2f')) if projected_cost is not None else 'n/a'}**")
    (_HERE / "power_calc.md").write_text("\n".join(L) + "\n")


def _write_verdict_md(cfg, boot, cells_needed, projected_cost, power):
    max_cells = int(cfg["gate"]["max_cells"])
    max_cost = float(cfg["gate"]["max_cost_usd"])
    lo, hi = boot.get("ci_low"), boot.get("ci_high")

    # NO-GO if CI un-informative (spans 0 widely / not resolvable) OR power unusable
    ci_uninformative = (lo is None or hi is None or (lo <= 0 <= hi))
    power_unreachable = (cells_needed is None)

    if power_unreachable or (ci_uninformative and (cells_needed is None or cells_needed > max_cells * 5)):
        verdict = "NO-GO"
    elif (cells_needed is not None and cells_needed <= max_cells
          and projected_cost is not None and projected_cost <= max_cost):
        verdict = "GO"
    else:
        verdict = "REDESIGN"

    L = []
    L.append("# Verdict\n")
    L.append(f"- **Cells needed for 80% power: {cells_needed if cells_needed else 'n/a'}** "
             f"(gate ≤ {max_cells})")
    L.append(f"- **Projected full-study cost: "
             f"{('$'+format(projected_cost, ',.2f')) if projected_cost is not None else 'n/a'}** "
             f"(gate ≤ ${max_cost:.0f})\n")
    L.append(f"## {verdict}\n")
    if verdict == "GO":
        L.append("Both gate numbers are within budget: the full study is powered and "
                 "affordable at the current grid resolution. Proceed.")
    elif verdict == "REDESIGN":
        L.append("Power is reachable but at least one gate is exceeded. Cheapest redesign, "
                 "in priority order:")
        L.append("1. **Increase task separation** (curate real, cell-specific news snippets "
                 "in inputs/ rather than neutral placeholders) — this raises Δκ, which "
                 "shrinks cells-needed quadratically, the highest-leverage lever.")
        L.append("2. **Add analysis dates** rather than tickers — dates are free to add to "
                 "the grid and increase paired cells without new tickers.")
        L.append("3. Drop to 2 runs/cell if the within-vs-cross bias analysis shows run "
                 "variance is small, cutting cost ~1/3.")
    else:
        L.append("The cluster-bootstrap CI on Δκ is too wide (spans 0 / not resolvable) for "
                 "any feasible grid to settle the effect at pilot signal levels, or the "
                 "effect/variance make cells-needed explode. Do not scale as designed; "
                 "revisit whether model heterogeneity produces a measurable de-correlation "
                 "at all under this task before committing budget.")
    L.append(f"\n---\n95% CI on Δκ: [{fmt(lo)}, {fmt(hi)}]. "
             f"Gate thresholds from config.yaml: cells ≤ {max_cells}, cost ≤ ${max_cost:.0f}.")
    (_HERE / "verdict.md").write_text("\n".join(L) + "\n")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
