"""Post-hoc, frozen-data re-analysis for the reviewer-hardening pass.

Reads ONLY runs.csv + config.yaml + datacache/forward_returns.json (no API calls,
no new data). Produces, per config:

  #2 Downstream benefit (exploratory)
     - unanimous directional-wrong rate  (manufactured consensus / tail risk)
     - agent-agreement conditional on the ensemble being wrong (Kim-style)
     - conviction calibration: hit-rate by conviction bucket (per-agent, directional)

  #4 Agreement robustness (prevalence-paradox rebuttal)
     - Krippendorff's alpha (nominal) and Gwet's AC1, per-run-averaged like kappa
     - BUY/HOLD/SELL marginals per config

Writes reviewer_metrics.md and figures/fig5_calibration.png under results/latest
(or POD_OUT_DIR). All numbers are deterministic functions of the frozen inputs.
"""
from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict

import io_paths

import yaml
import metrics as M

DIRS = ["BUY", "HOLD", "SELL"]
CONFIGS = ["HOM", "HET-LITE", "HET"]


def load():
    rows = list(csv.DictReader((io_paths.resolve_dataset_dir("confirmatory") / "runs.csv").open()))
    cfg = yaml.safe_load(io_paths.default_config_path().read_text())
    fr = json.loads((io_paths.data_root() / "datacache" / "forward_returns.json").read_text())
    signs = {tuple(k.split("|")): v.get("sign") for k, v in fr.items()}
    return rows, cfg, signs


# --------------------------------------------------------------------------- #
# ensemble-decision groups: (config,ticker,date,run) -> list of agent dicts
# --------------------------------------------------------------------------- #
def decision_groups(rows, config):
    g = defaultdict(list)
    for r in M.usable(rows):
        if r["config"] != config:
            continue
        g[(r["ticker"], r["date"], r["run_idx"])].append(r)
    return g


def majority(dirs):
    c = Counter(dirs)
    return sorted(c.items(), key=lambda kv: (-kv[1], DIRS.index(kv[0])))[0][0]


# --------------------------------------------------------------------------- #
# #2 downstream benefit
# --------------------------------------------------------------------------- #
def downstream(rows, signs, config):
    g = decision_groups(rows, config)
    n_full = 0                       # 5-agent, scoreable (sign known & nonzero)
    unanimous_dir_wrong = 0          # all 5 same, directional, wrong
    unanimous_any = 0                # all 5 same (any direction), scoreable
    wrong_decisions = 0              # majority directional & wrong
    cond_agree_sum = 0.0             # sum over wrong decisions of frac agents == majority
    for (t, d, _run), agents in g.items():
        if len(agents) != 5:
            continue
        s = signs.get((t, d))
        if s is None or s == 0:
            continue
        n_full += 1
        dirs = [a["direction"] for a in agents]
        maj = majority(dirs)
        c = Counter(dirs)
        if len(c) == 1:
            unanimous_any += 1
            only = dirs[0]
            if only in ("BUY", "SELL"):
                pred = 1 if only == "BUY" else -1
                if pred != s:
                    unanimous_dir_wrong += 1
        if maj in ("BUY", "SELL"):
            pred = 1 if maj == "BUY" else -1
            if pred != s:
                wrong_decisions += 1
                cond_agree_sum += c[maj] / 5.0
    return {
        "n_scoreable": n_full,
        "unanimous_any_rate": unanimous_any / n_full if n_full else None,
        "unanimous_dir_wrong_rate": unanimous_dir_wrong / n_full if n_full else None,
        "unanimous_dir_wrong_n": unanimous_dir_wrong,
        "wrong_decisions": wrong_decisions,
        "cond_agree_given_wrong": cond_agree_sum / wrong_decisions if wrong_decisions else None,
    }


def calibration(rows, signs, config):
    """Per-agent directional calls, hit-rate by conviction bucket."""
    buckets = {"low (1-2)": [0, 0], "mid (3)": [0, 0], "high (4-5)": [0, 0]}
    for r in M.usable(rows):
        if r["config"] != config or r["direction"] == "HOLD":
            continue
        s = signs.get((r["ticker"], r["date"]))
        if s is None or s == 0:
            continue
        try:
            conv = int(r["conviction"])
        except (ValueError, TypeError):
            continue
        b = "low (1-2)" if conv <= 2 else ("mid (3)" if conv == 3 else "high (4-5)")
        pred = 1 if r["direction"] == "BUY" else -1
        buckets[b][1] += 1
        buckets[b][0] += 1 if pred == s else 0
    return {b: (h / n if n else None, n) for b, (h, n) in buckets.items()}


# --------------------------------------------------------------------------- #
# #4 alternative agreement statistics (nominal), per-run then averaged
# --------------------------------------------------------------------------- #
def _unit_counts(rows, config):
    """{(ticker,date,run): [nBUY,nHOLD,nSELL]} for 5-rater units."""
    g = decision_groups(rows, config)
    units = {}
    for k, agents in g.items():
        c = Counter(a["direction"] for a in agents)
        vec = [c.get(x, 0) for x in DIRS]
        if sum(vec) >= 2:
            units[k] = vec
    return units


def _krippendorff_alpha(units):
    """Nominal Krippendorff's alpha via the coincidence matrix (fixed/var raters ok)."""
    q = len(DIRS)
    o = [[0.0] * q for _ in range(q)]
    for vec in units.values():
        n = sum(vec)
        if n < 2:
            continue
        for c in range(q):
            for k in range(q):
                if c == k:
                    o[c][k] += vec[c] * (vec[c] - 1) / (n - 1)
                else:
                    o[c][k] += vec[c] * vec[k] / (n - 1)
    n_c = [sum(o[c]) for c in range(q)]
    n_tot = sum(n_c)
    if n_tot < 2:
        return None
    Do = sum(o[c][k] for c in range(q) for k in range(q) if c != k)
    De = sum(n_c[c] * n_c[k] for c in range(q) for k in range(q) if c != k) / (n_tot - 1)
    if De == 0:
        return 1.0
    return 1 - Do / De


def _gwet_ac1(units):
    """Gwet's AC1 for fixed number of raters per unit (drop to modal n)."""
    counts = [sum(v) for v in units.values()]
    if not counts:
        return None
    n = Counter(counts).most_common(1)[0][0]
    U = [v for v in units.values() if sum(v) == n]
    N = len(U)
    q = len(DIRS)
    if N < 2 or n < 2:
        return None
    p_a = sum(sum(x * (x - 1) for x in v) for v in U) / (N * n * (n - 1))
    pi = [sum(v[c] for v in U) / (N * n) for c in range(q)]
    p_e = sum(p * (1 - p) for p in pi) / (q - 1)
    if abs(1 - p_e) < 1e-12:
        return 1.0
    return (p_a - p_e) / (1 - p_e)


def per_run_avg(rows, config, fn):
    units_all = _unit_counts(rows, config)
    runs = sorted({k[2] for k in units_all})
    vals = []
    for run in runs:
        u = {k: v for k, v in units_all.items() if k[2] == run}
        val = fn(u)
        if val is not None:
            vals.append(val)
    return sum(vals) / len(vals) if vals else None


def marginals(rows, config):
    c = Counter(r["direction"] for r in M.usable(rows) if r["config"] == config)
    tot = sum(c.values())
    return {d: c.get(d, 0) / tot for d in DIRS}, tot


# --------------------------------------------------------------------------- #
def fmt(x, n=4):
    return "n/a" if x is None else f"{x:.{n}f}"


def main():
    out = io_paths.resolve_out_dir(create=True)
    rows, cfg, signs = load()
    lines = ["# Reviewer-hardening re-analysis (frozen data; post-hoc, exploratory)\n"]

    # ---- #4 agreement robustness ----
    lines.append("## Agreement robustness — three statistics agree on the ordering\n")
    lines.append("| config | Fleiss' kappa | Krippendorff's alpha | Gwet's AC1 |")
    lines.append("|---|---|---|---|")
    for cf in CONFIGS:
        k, _ = M.kappa_per_run_avg(rows, cf)
        a = per_run_avg(rows, cf, _krippendorff_alpha)
        ac1 = per_run_avg(rows, cf, _gwet_ac1)
        lines.append(f"| {cf} | {fmt(k)} | {fmt(a)} | {fmt(ac1)} |")
    lines.append("\n### BUY/HOLD/SELL marginals per config (prevalence check)\n")
    lines.append("| config | BUY | HOLD | SELL | n calls |")
    lines.append("|---|---|---|---|---|")
    for cf in CONFIGS:
        m, tot = marginals(rows, cf)
        lines.append(f"| {cf} | {m['BUY']:.3f} | {m['HOLD']:.3f} | {m['SELL']:.3f} | {tot} |")

    # ---- #2 downstream benefit ----
    lines.append("\n## Downstream benefit — manufactured consensus & tail risk\n")
    lines.append("| config | scoreable decisions | unanimous rate | unanimous-&-directional-wrong rate | P(agree with majority \\| majority wrong) |")
    lines.append("|---|---|---|---|---|")
    dd = {}
    for cf in CONFIGS:
        d = downstream(rows, signs, cf)
        dd[cf] = d
        lines.append(f"| {cf} | {d['n_scoreable']} | {fmt(d['unanimous_any_rate'],3)} | "
                     f"{fmt(d['unanimous_dir_wrong_rate'],3)} (n={d['unanimous_dir_wrong_n']}) | "
                     f"{fmt(d['cond_agree_given_wrong'],3)} |")
    if dd["HOM"]["unanimous_dir_wrong_rate"] and dd["HET"]["unanimous_dir_wrong_rate"]:
        ratio = dd["HOM"]["unanimous_dir_wrong_rate"] / dd["HET"]["unanimous_dir_wrong_rate"]
        lines.append(f"\n_HOM unanimous-wrong rate is {ratio:.2f}x the HET rate._")

    # ---- calibration ----
    lines.append("\n## Conviction calibration — per-agent directional hit-rate by conviction\n")
    lines.append("| config | low (1-2) | mid (3) | high (4-5) |")
    lines.append("|---|---|---|---|")
    calib = {}
    for cf in CONFIGS:
        c = calibration(rows, signs, cf)
        calib[cf] = c
        cells = []
        for b in ["low (1-2)", "mid (3)", "high (4-5)"]:
            hr, n = c[b]
            cells.append(f"{fmt(hr,3)} (n={n})")
        lines.append(f"| {cf} | " + " | ".join(cells) + " |")

    (out / "reviewer_metrics.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # ---- calibration figure ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        xs = ["low (1-2)", "mid (3)", "high (4-5)"]
        plt.figure(figsize=(5, 3.2))
        for cf in CONFIGS:
            ys = [calib[cf][b][0] for b in xs]
            plt.plot(xs, ys, marker="o", label=cf)
        plt.ylabel("directional hit-rate"); plt.xlabel("agent conviction bucket")
        plt.ylim(0.3, 0.7); plt.axhline(0.5, ls="--", c="grey", lw=0.8)
        plt.legend(); plt.tight_layout()
        fig_dir = out / "figures"
        fig_dir.mkdir(exist_ok=True)
        fig_path = fig_dir / "fig5_calibration.png"
        plt.savefig(fig_path, dpi=150)
        print(f"\nWrote {fig_path}")
    except Exception as e:
        print(f"\n(figure skipped: {e})")
    print(f"\nWrote {out / 'reviewer_metrics.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
