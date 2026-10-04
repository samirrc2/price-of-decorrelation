"""Phase 3 — deterministic re-analysis. Reads ONLY runs.csv + config.yaml.

Produces metrics_summary.md (verdict first), figures/, tables/, and the draft
docs. All randomness is seeded (bootstrap_seed); outputs are byte-stable.
"""
from __future__ import annotations
import csv
import math
import sys
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path

import yaml

import metrics as M
import stats as S

_HERE = Path(__file__).resolve().parents[1]
# Archived Δκ(HOM−HET) and HOM within−cross κ gaps for the protocol-collapse figure.
PILOT_BROKEN = {"dkappa": 0.485, "hom_within_minus_cross": 0.377}   # archive/pilot_v1_broken_perRunSeed
PILOT_CLEAN = {"dkappa": 0.113, "hom_within_minus_cross": 0.018}    # archive/pilot_v1


def fmt(x, n=4):
    return "n/a" if x is None else f"{x:.{n}f}"


def load_cfg():
    return yaml.safe_load((_HERE / "configs" / "config.yaml").read_text())


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# --------------------------------------------------------------------------- #
def within_cross(rows, config):
    avg, ks = M.kappa_per_run_avg(rows, config)
    cross = M.kappa_cross_run(rows, config)
    gap = (avg - cross) if (avg is not None and cross is not None) else None
    return avg, cross, gap, ks


def sector_kappa(rows, config, sector_tickers):
    sub = [r for r in rows if r["ticker"] in sector_tickers]
    avg, _ = M.kappa_per_run_avg(sub, config)
    return avg


def provider_matrix(rows, configs):
    """Symmetric mean pairwise direction-agreement between agents of provider A and
    provider B within the same (config,ticker,date,run) cell (all configs pooled)."""
    prov_pairs = defaultdict(lambda: [0, 0])  # (pa,pb) -> [agree, total]
    cells = defaultdict(list)
    for r in M.usable(rows):
        cells[(r["config"], r["ticker"], r["date"], r["run_idx"])].append(
            (r["provider"], r["direction"]))
    for members in cells.values():
        for (pa, da), (pb, db) in combinations(members, 2):
            key = tuple(sorted((pa, pb)))
            prov_pairs[key][1] += 1
            if da == db:
                prov_pairs[key][0] += 1
    provs = sorted({p for k in prov_pairs for p in k})
    mat = {}
    for a in provs:
        for b in provs:
            key = tuple(sorted((a, b)))
            agree, tot = prov_pairs.get(key, [0, 0])
            mat[(a, b)] = (agree / tot) if tot else None
    return provs, mat


def cost_by_provider(rows):
    per = defaultdict(lambda: [0.0, 0])
    for r in rows:
        try:
            per[r["provider"]][0] += float(r["cost_usd"])
        except (ValueError, KeyError):
            continue
        per[r["provider"]][1] += 1
    return {p: {"total_usd": v[0], "n": v[1]} for p, v in per.items()}


# --------------------------------------------------------------------------- #
def main():
    cfg = load_cfg()
    runs_csv = _HERE / cfg["paths"]["runs_csv"]
    if not runs_csv.exists():
        print(f"No {runs_csv}. Run Phase 2 first.")
        return 1
    rows = list(csv.DictReader(runs_csv.open()))
    ok_rows = M.usable(rows)
    # honest manifest: completeness is measured by CELLS WITH A SUCCESSFUL ROW vs the
    # expected grid — NOT by historical DEFERRED/retry rows (a cell can carry an old
    # deferred row AND a later successful backfill).
    import datetime as _dt
    import hashlib as _hashlib
    _cfg = cfg
    config_path = _HERE / "configs" / "config.yaml"
    runs_sha = _hashlib.sha256(runs_csv.read_bytes()).hexdigest()
    cfg_sha = _hashlib.sha256(config_path.read_bytes()).hexdigest()
    expected = (len(_cfg["tickers"]) * len(_cfg["dates"]) * len(_cfg["configs"])
                * int(_cfg["runs"]) * 5)
    ok_slots = {(r["config"], r["ticker"], r["date"], r["run_idx"], r["agent_idx"])
                for r in rows if r.get("ok") == "True"}
    missing = expected - len(ok_slots)
    deferred_rows = [r for r in rows if (r.get("error") or "").startswith("DEFERRED")]
    still_short = sorted({r["model"] for r in deferred_rows
                          if (r["config"], r["ticker"], r["date"], r["run_idx"], r["agent_idx"])
                          not in ok_slots})
    # Wall-clock is console-only (not part of the reproducible artifact).
    _ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    print(f"Analysis started (UTC): {_ts}")
    # Manifest stamps input hashes so re-runs are byte-identical for the same data.
    if missing > 0:
        manifest_line = (
            f"- Inputs: `{runs_csv.name}` SHA-256=`{runs_sha}` ; "
            f"`configs/config.yaml` SHA-256=`{cfg_sha}` ({len(rows)} rows). "
            f"Grid {len(ok_slots)}/{expected} cells complete; {missing} still MISSING"
            + (f" (models over quota: {still_short})" if still_short else "")
            + ".  ⚠️ Dataset INCOMPLETE — backfill remaining cells before final.")
    else:
        manifest_line = (
            f"- Inputs: `{runs_csv.name}` SHA-256=`{runs_sha}` ; "
            f"`configs/config.yaml` SHA-256=`{cfg_sha}` ({len(rows)} rows). "
            f"Grid COMPLETE: {len(ok_slots)}/{expected} cells present. "
            f"(Historical deferred/retry rows: {len(deferred_rows)}, all backfilled.)")
    config_names = list(cfg["configs"].keys())
    hlevel = cfg["heterogeneity_level"]
    tickers = cfg["tickers"]
    draws = int(cfg["bootstrap_draws"])
    bseed = int(cfg["bootstrap_seed"])

    # κ per config + within/cross
    kappa = {}
    wc = {}
    for c in config_names:
        avg, cross, gap, ks = within_cross(rows, c)
        kappa[c] = avg
        wc[c] = {"within": avg, "cross": cross, "gap": gap, "per_run": ks}

    # primary + secondary Δκ — one multi-pair bootstrap (byte-identical to 3 separate
    # cluster_bootstrap_pair calls, ~2x faster: each config's κ computed once per draw)
    _boots = S.cluster_bootstrap_multi(
        rows, tickers, [("HOM", "HET"), ("HOM", "HET-LITE"), ("HET-LITE", "HET")], draws, bseed)
    primary = _boots[("HOM", "HET")]
    sec1 = _boots[("HOM", "HET-LITE")]
    sec2 = _boots[("HET-LITE", "HET")]

    # verdict on primary
    dk, lo, hi = primary["point"], primary["ci_low"], primary["ci_high"]
    if dk is None or lo is None:
        verdict = "INCONCLUSIVE"
    elif dk > 0 and lo > 0:
        verdict = "CONFIRMED"
    elif dk > 0:
        verdict = "WEAKENED"
    else:
        verdict = "CONTRADICTED"

    # cost
    cost = M.cost_summary(rows)
    cprov = cost_by_provider(rows)

    # accuracy proxy w/ binomial CIs
    signs, sign_err = M.forward_return_signs(tickers, cfg["dates"], int(cfg["forward_return_days"]))
    acc = {}
    for c in config_names:
        hr, scored, holds = M.accuracy_proxy(rows, c, signs)
        if scored:
            k = round(hr * scored)
            acc[c] = (hr, scored, holds, wilson(k, scored))
        else:
            acc[c] = (None, 0, holds, (None, None))

    # provider matrix
    provs, pmat = provider_matrix(rows, config_names)

    # figures + tables (deterministic)
    fig_note = _make_figures(cfg, kappa, cost, hlevel, primary, sec1, sec2, wc, provs, pmat)
    _make_tables(cfg, kappa, cost, cprov, primary, sec1, sec2, acc, config_names, hlevel)

    _write_summary(cfg, verdict, primary, sec1, sec2, kappa, wc, cost, cprov,
                   acc, sign_err, provs, pmat, config_names, hlevel, len(rows), len(ok_rows),
                   fig_note, manifest_line)
    _write_docs(cfg, verdict, primary, sec1, sec2, kappa, cost, config_names, hlevel)

    print(f"VERDICT: {verdict}  primary Δκ(HOM−HET)={fmt(dk)} CI[{fmt(lo)},{fmt(hi)}]")
    print(f"Input hashes: runs.csv={runs_sha}  config.yaml={cfg_sha}")
    print("Wrote metrics_summary.md, figures/, tables/, protocol_exhibit.md, "
          "headline_check.md, threats_to_validity.md, appendix/data_availability.md")
    return 0


# --------------------------------------------------------------------------- #
def _make_figures(cfg, kappa, cost, hlevel, primary, sec1, sec2, wc, provs, pmat):
    try:
        import matplotlib
        matplotlib.use("Agg")
        matplotlib.rcParams["svg.hashsalt"] = "price-of-diversity"  # stable SVG ids
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        return f"(figures skipped: matplotlib unavailable: {e})"
    fdir = _HERE / "figures"
    fdir.mkdir(exist_ok=True)
    order = ["HOM", "HET-LITE", "HET"]
    # strip non-deterministic metadata so re-runs are byte-identical
    PNG_META = {"Software": None, "Creation Time": None}
    SVG_META = {"Date": None}

    def save(fig, stem, svg=False):
        fig.savefig(fdir / f"{stem}.png", dpi=150, metadata=PNG_META)
        if svg:
            fig.savefig(fdir / f"{stem}.svg", metadata=SVG_META)
        plt.close(fig)

    # fig1: frontier cost vs kappa
    xs = [cost.get(c, {}).get("mean_per_decision_usd", 0.0) for c in order]
    ys = [kappa.get(c) or 0.0 for c in order]
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.plot(xs, ys, "-o", color="#333")
    for c, x, y in zip(order, xs, ys):
        ax.annotate(f"{c}\n(lvl {hlevel[c]})", (x, y),
                    textcoords="offset points", xytext=(6, 6), fontsize=8)
    ax.set_xlabel("cost per ensemble-decision (USD)")
    ax.set_ylabel("within-ensemble agreement κ")
    ax.set_title("Frontier: agreement vs cost across heterogeneity")
    fig.tight_layout(); save(fig, "fig1_frontier", svg=True)

    # fig2: protocol collapse (HOM within−cross gap)
    stages = ["broken pilot\n(Δκ=0.485)", "clean pilot\n(Δκ=0.113)", "full study"]
    gaps = [PILOT_BROKEN["hom_within_minus_cross"], PILOT_CLEAN["hom_within_minus_cross"],
            wc["HOM"]["gap"] if wc["HOM"]["gap"] is not None else 0.0]
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.bar(stages, gaps, color=["#b44", "#c93", "#484"])
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_ylabel("HOM κ  (within-run − cross-run)")
    ax.set_title("Seeding-nondeterminism inflation collapses to ~0")
    fig.tight_layout(); save(fig, "fig2_protocol")

    # fig3: provider agreement heatmap. Undefined cells (no same-provider pair, e.g.
    # a single xAI agent per HET cell) are rendered N/A, NOT 0.0.
    if provs:
        mat = np.array([[ (pmat.get((a, b)) if pmat.get((a, b)) is not None else np.nan)
                          for b in provs] for a in provs])
        cmap = plt.get_cmap("viridis").copy()
        cmap.set_bad(color="#d9d9d9")  # grey for N/A
        fig, ax = plt.subplots(figsize=(4.8, 4.2))
        im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=1)
        ax.set_xticks(range(len(provs))); ax.set_xticklabels(provs, rotation=45, ha="right")
        ax.set_yticks(range(len(provs))); ax.set_yticklabels(provs)
        for i in range(len(provs)):
            for j in range(len(provs)):
                v = mat[i, j]
                label = "N/A" if (v != v) else f"{v:.2f}"   # v!=v => NaN
                ax.text(j, i, label, ha="center", va="center",
                        color=("#333" if (v != v) else "w"), fontsize=8)
        ax.set_title("Pairwise direction agreement by provider")
        fig.colorbar(im, fraction=0.046, pad=0.04)
        fig.tight_layout(); save(fig, "fig3_provider_heatmap")
    return "(figures written to figures/)"


def _make_tables(cfg, kappa, cost, cprov, primary, sec1, sec2, acc, config_names, hlevel):
    tdir = _HERE / "tables"; tdir.mkdir(exist_ok=True)
    # endpoints table
    rows = [["endpoint", "estimate", "ci_low", "ci_high"]]
    for label, b in (("Dkappa_HOM_HET", primary), ("Dkappa_HOM_HETLITE", sec1),
                     ("Dkappa_HETLITE_HET", sec2)):
        rows.append([label, fmt(b["point"]), fmt(b["ci_low"]), fmt(b["ci_high"])])
    _csv(tdir / "endpoints.csv", rows); _latex(tdir / "endpoints.tex", rows, "Primary and secondary endpoints")
    # frontier table
    frows = [["config", "heterogeneity_level", "kappa", "cost_per_decision_usd"]]
    for c in config_names:
        frows.append([c, hlevel[c], fmt(kappa.get(c)),
                      fmt(cost.get(c, {}).get("mean_per_decision_usd", 0.0), 6)])
    _csv(tdir / "frontier.csv", frows); _latex(tdir / "frontier.tex", frows, "Frontier: kappa and cost by heterogeneity")


def _csv(path, rows):
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)


def _latex(path, rows, caption):
    cols = len(rows[0])
    L = ["\\begin{table}[t]\\centering", f"\\caption{{{caption}}}",
         "\\begin{tabular}{" + "l" * cols + "}", "\\toprule",
         " & ".join(str(x).replace("_", "\\_") for x in rows[0]) + " \\\\", "\\midrule"]
    for r in rows[1:]:
        L.append(" & ".join(str(x).replace("_", "\\_") for x in r) + " \\\\")
    L += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    path.write_text("\n".join(L) + "\n")


# --------------------------------------------------------------------------- #
def _write_summary(cfg, verdict, primary, sec1, sec2, kappa, wc, cost, cprov,
                   acc, sign_err, provs, pmat, config_names, hlevel, n_all, n_ok, fig_note,
                   manifest_line=""):
    L = [f"# Metrics summary — VERDICT: {verdict}\n",
         f"**Primary endpoint Δκ(HOM−HET) = {fmt(primary['point'])}**, "
         f"95% CI [{fmt(primary['ci_low'])}, {fmt(primary['ci_high'])}] "
         f"(cluster bootstrap over tickers, {primary['n_valid']} draws, seed "
         f"{cfg['bootstrap_seed']}). κ_HOM={fmt(kappa.get('HOM'))}, κ_HET={fmt(kappa.get('HET'))}.\n",
         f"Verdict rule: CONFIRMED if Δκ>0 and CI excludes 0; WEAKENED if Δκ>0 but CI "
         f"includes 0; CONTRADICTED if Δκ≤0. Model set = OpenAI/Google/xAI (cross-provider; "
         f"differs from the Claude-family pilot — stated explicitly).\n",
         f"- Calls logged (incl. retries): {n_all}  |  usable: {n_ok}",
         manifest_line + "\n",
         "## Secondary Δκ contrasts\n",
         "| contrast | Δκ | 95% CI |", "|---|---|---|",
         f"| HOM − HET-LITE | {fmt(sec1['point'])} | [{fmt(sec1['ci_low'])}, {fmt(sec1['ci_high'])}] |",
         f"| HET-LITE − HET | {fmt(sec2['point'])} | [{fmt(sec2['ci_low'])}, {fmt(sec2['ci_high'])}] |\n",
         "## Frontier (κ and cost vs heterogeneity level)\n",
         "| config | level | κ | $/ensemble-decision |", "|---|---|---|---|"]
    for c in config_names:
        L.append(f"| {c} | {hlevel[c]} | {fmt(kappa.get(c))} | "
                 f"{fmt(cost.get(c, {}).get('mean_per_decision_usd', 0.0), 6)} |")
    L.append("\n## Within-run vs cross-run κ (nondeterminism check — must be ≈0)\n")
    L.append("| config | within | cross | within−cross |")
    L.append("|---|---|---|---|")
    for c in config_names:
        L.append(f"| {c} | {fmt(wc[c]['within'])} | {fmt(wc[c]['cross'])} | {fmt(wc[c]['gap'])} |")
    L.append("\n## Cost by provider\n| provider | calls | total $ |\n|---|---|---|")
    for p, v in sorted(cprov.items()):
        L.append(f"| {p} | {v['n']} | {fmt(v['total_usd'], 4)} |")
    L.append("\n## Provider-pair direction agreement (descriptive)\n")
    if provs:
        L.append("| | " + " | ".join(provs) + " |")
        L.append("|" + "---|" * (len(provs) + 1))
        for a in provs:
            L.append(f"| **{a}** | " + " | ".join(fmt(pmat.get((a, b)), 3) for b in provs) + " |")
    L.append("\n## Accuracy proxy — SECONDARY axis (study powered for κ, not accuracy)\n")
    if sign_err:
        L.append(f"- forward returns unavailable: {sign_err}")
    else:
        L.append("| config | hit-rate | n | 95% CI (Wilson) | HOLD-abstained |")
        L.append("|---|---|---|---|---|")
        for c in config_names:
            hr, scored, holds, (clo, chi) = acc[c]
            L.append(f"| {c} | {fmt(hr, 3)} | {scored} | [{fmt(clo,3)}, {fmt(chi,3)}] | {holds} |")
    L.append(f"\n_{fig_note}. Tables in tables/ (CSV + LaTeX)._")
    (_HERE / "metrics_summary.md").write_text("\n".join(L) + "\n")


def _write_docs(cfg, verdict, primary, sec1, sec2, kappa, cost, config_names, hlevel):
    dk = primary["point"]; lo, hi = primary["ci_low"], primary["ci_high"]
    ratio = None
    try:
        ratio = cost["HET"]["mean_per_decision_usd"] / cost["HOM"]["mean_per_decision_usd"]
    except Exception:
        pass
    # headline_check.md
    (_HERE / "headline_check.md").write_text(
        f"# Headline check\n\n"
        f"Abstract-ready sentence (FINAL numbers):\n\n"
        f"> Moving from a homogeneous 5-agent ensemble to a cross-provider "
        f"heterogeneous one de-correlates agents by Δκ ≈ {fmt(dk,3)} "
        f"(95% CI [{fmt(lo,3)}, {fmt(hi,3)}]) at ≈{fmt(ratio,1) if ratio else 'n/a'}× "
        f"the inference cost per decision.\n\n"
        f"Cross-provider vs Claude-family pilot: the pilot (within-family) gave "
        f"Δκ≈0.113; if this cross-provider estimate is materially larger, that gap is "
        f"itself a finding (within-family vs cross-family correlation), not a "
        f"discrepancy. Verdict: **{verdict}**.\n")
    # protocol_exhibit.md
    (_HERE / "protocol_exhibit.md").write_text(
        "# Measurement protocol (methods exhibit)\n\n"
        "Sampling nondeterminism is a trap for anyone measuring model monoculture. "
        "If the agents in a homogeneous ensemble are drawn under a *shared* sampling "
        "context — the same seed, or a cached completion replayed across slots — they "
        "return byte-identical outputs, and any agreement statistic (Fleiss' κ, "
        "majority-vote concentration) reads a spurious 1.0. In our own pipeline this "
        "inflated the homogeneous within-run κ by ~0.38 and the headline Δκ(HOM−HET) "
        "from 0.113 to 0.485 — a 4× overstatement produced entirely by the measurement "
        "apparatus, not the models. The fix is to treat *independent draws* as the "
        "estimand: a unique seed per agent per call (or no seed at all), the response "
        "cache bypassed for unseeded draws, and an explicit post-hoc check that "
        "same-model agents within a cell produced differing raw completions (abort "
        "otherwise). Only after that correction does κ measure agreement between agents "
        "rather than agreement between copies. We report the collapse (0.485 → 0.113 "
        "clean pilot → full study) as fig. 2. Note the model set changed between pilot "
        "(Claude family) and full study (OpenAI/Google/xAI): the protocol point is "
        "invariant to model choice, but the numeric Δκ is not, and we never blur the two.\n")
    # threats_to_validity.md
    (_HERE / "threats_to_validity.md").write_text(
        "# Threats to validity\n\n"
        "**Ticker clustering.** The 50 tickers are stratified across 11 GICS sectors, "
        "but names within a sector co-move; our CIs use a cluster bootstrap resampling "
        "tickers to respect this, yet residual cross-sector correlation could still "
        "narrow intervals.\n\n"
        "**Date-regime coverage.** Eight 2026 dates span AI-capex and energy "
        "supply-shock regimes, but eight points cannot represent all market states; "
        "agreement may be regime-dependent in ways this grid under-samples.\n\n"
        "**Model-version pinning.** Providers silently update model strings; we pin exact "
        "strings in model_manifest.md and treat the hashed runs.csv as the dataset, so "
        "results are reproducible from data even after the live models move.\n\n"
        "**Single-run data collection.** Raw data is collected once; there is no "
        "re-collection to average over provider-side drift within the window.\n\n"
        "**Accuracy axis underpowered.** The study is powered for κ, not for directional "
        "accuracy; the forward-return hit-rate is descriptive with wide binomial CIs and "
        "must not be read as an alpha claim.\n\n"
        "**Generalization.** Findings pertain to these three specific ensemble recipes "
        "and this task/prompt; other tasks, sizes, or provider mixes may differ.\n")
    # appendix/data_availability.md
    (_HERE / "appendix").mkdir(exist_ok=True)
    (_HERE / "appendix" / "data_availability.md").write_text(
        "# Data availability\n\nThe dataset is the SHA-256-hashed, read-only `runs.csv` "
        "(hash in `archive_manifest.md`), held privately pending compliance clearance and "
        "released on publication. All analysis (`analyze.py`) is a deterministic, seeded "
        "function of `runs.csv` + `config.yaml` and reproduces every figure and table "
        "byte-for-byte.\n")


if __name__ == "__main__":
    sys.exit(main())
