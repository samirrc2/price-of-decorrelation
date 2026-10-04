"""Reviewer-requested analyses for the revision. Reads only frozen data; $0.

Each block is keyed to the comment it answers. Writes results/revision_metrics.json
and prints a summary. Nothing here changes analyze.py, which remains the frozen
confirmatory pipeline.

  R3.2  bootstrap unit: ticker (primary), date, and two-way equity/date clustering
  R1.4  cluster-bootstrap CIs on the post-hoc unanimous-incorrect statistic
  R1.5  independence diagnostic restricted to different-model agent pairs
  R1.1 / R3.4  selective prediction: risk-coverage curve and AURC
"""
from __future__ import annotations
import csv, itertools, json, math, os, random, sys, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_paths, metrics as M                                    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DRAWS, SEED = 2000, 42


def load_rows(p): 
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        return [r for r in csv.DictReader(f) if r["ok"] == "True"]


def kappa_sub(rows, cfg, keep):
    sub = [r for r in rows if r["config"] == cfg and keep(r)]
    k, _ = M.kappa_per_run_avg(sub, cfg)
    return k


# ---------------------------------------------------------------- R3.2 clustering
def clustering(rows):
    tick = sorted({r["ticker"] for r in rows})
    date = sorted({r["date"] for r in rows})
    out = {}

    def delta(keep):
        a = kappa_sub(rows, "HOM", keep); b = kappa_sub(rows, "HET", keep)
        return None if (a is None or b is None) else a - b

    point = delta(lambda r: True)

    def boot(mode):
        rng = random.Random(SEED); d = []
        for _ in range(DRAWS):
            if mode == "ticker":
                s = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
                keep = lambda r: s.get(r["ticker"], 0) > 0
            elif mode == "date":
                s = collections.Counter(date[rng.randrange(len(date))] for _ in date)
                keep = lambda r: s.get(r["date"], 0) > 0
            else:  # two-way: resample both margins independently
                st = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
                sd = collections.Counter(date[rng.randrange(len(date))] for _ in date)
                keep = lambda r: st.get(r["ticker"], 0) > 0 and sd.get(r["date"], 0) > 0
            v = delta(keep)
            if v is not None: d.append(v)
        d.sort()
        return (d[int(.025*len(d))], d[int(.975*len(d))-1], len(d)) if len(d) >= 20 else (None, None, len(d))

    for mode, n_cl in (("ticker", len(tick)), ("date", len(date)), ("two_way", len(tick)*len(date))):
        lo, hi, n = boot(mode)
        out[mode] = {"point": point, "ci": [lo, hi], "n_clusters": n_cl, "draws_used": n}
    return out


# ------------------------------------------------------- R1.4 unanimous-incorrect
def unanimous_wrong(rows, signs):
    tick = sorted({r["ticker"] for r in rows})
    def rate(cfg, keep):
        """The manuscript's statistic: unanimous AND directionally wrong, over ALL
        scoreable 5-agent cells -- not conditional on unanimity. Homogeneous
        ensembles are unanimous far more often, which is the point of the claim."""
        cells = collections.defaultdict(list)
        for r in rows:
            if r["config"] == cfg and keep(r): cells[(r["ticker"], r["date"], r["run_idx"])].append(r["direction"])
        n = w = 0
        for (t, d, _), dirs in cells.items():
            s = signs.get((t, d))
            if s is None or s == 0 or len(dirs) != 5: continue
            n += 1
            if len(set(dirs)) == 1 and dirs[0] in ("BUY", "SELL"):
                w += int((1 if dirs[0] == "BUY" else -1) != s)
        return (w / n, n) if n else (None, 0)
    pts = {c: rate(c, lambda r: True) for c in ("HOM", "HET")}
    ratio = (pts["HOM"][0] / pts["HET"][0]) if pts["HET"][0] else None
    rng = random.Random(SEED); rs = []
    for _ in range(DRAWS):
        s = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
        keep = lambda r: s.get(r["ticker"], 0) > 0
        a, _ = rate("HOM", keep); b, _ = rate("HET", keep)
        if a and b: rs.append(a / b)
    rs.sort()
    return {"hom": pts["HOM"], "het": pts["HET"], "ratio": ratio,
            "ratio_ci": [rs[int(.025*len(rs))], rs[int(.975*len(rs))-1]] if len(rs) >= 20 else [None, None]}


# ------------------------------------- R1.5 independence: different-model pairs only
def independence(rows):
    cells = collections.defaultdict(dict)
    for r in rows: cells[(r["config"], r["ticker"], r["date"], r["run_idx"])][int(r["agent_idx"])] = r
    out = {}
    for cfg in ("HOM", "HET-LITE", "HET"):
        same = diff = same_n = diff_n = 0
        for (c, *_k), ag in cells.items():
            if c != cfg: continue
            for i, j in itertools.combinations(sorted(ag), 2):
                a, b = ag[i], ag[j]
                agree = a["direction"] == b["direction"]
                if a["api_model"] == b["api_model"]: same += agree; same_n += 1
                else: diff += agree; diff_n += 1
        out[cfg] = {"same_model_agreement": same/same_n if same_n else None, "same_model_pairs": same_n,
                    "diff_model_agreement": diff/diff_n if diff_n else None, "diff_model_pairs": diff_n}
    return out


# ------------------------------------------- R1.1 / R3.4 selective prediction
def selective(rows, signs):
    """Risk-coverage curve over ensemble decisions ranked by mean agent conviction."""
    out = {}
    for cfg in ("HOM", "HET-LITE", "HET"):
        mv = M.majority_vote([r for r in rows if r["config"] == cfg], cfg)
        conv = collections.defaultdict(list)
        for r in rows:
            if r["config"] == cfg:
                try: conv[(r["ticker"], r["date"])].append(int(r["conviction"]))
                except (TypeError, ValueError): pass
        scored = []
        for (t, d), (direction, _mc, _n) in mv.items():
            s = signs.get((t, d))
            if s is None or s == 0 or direction == "HOLD": continue
            c = sum(conv[(t, d)]) / len(conv[(t, d)]) if conv[(t, d)] else 0
            scored.append((c, int((1 if direction == "BUY" else -1) != s)))
        if not scored: continue
        scored.sort(key=lambda x: -x[0])
        pts, err = [], 0
        for i, (_c, e) in enumerate(scored, 1):
            err += e
            pts.append((i/len(scored), err/i))
        aurc = sum((pts[i][1]+pts[i-1][1])/2*(pts[i][0]-pts[i-1][0]) for i in range(1, len(pts)))
        out[cfg] = {"n": len(scored), "full_coverage_risk": pts[-1][1], "aurc": aurc,
                    "risk_at_50pct_coverage": pts[len(pts)//2][1]}
    return out



# ------------------------------------------------- R3.3 error correlation (phi)
def error_correlation(rows, signs, hold_is_wrong=False):
    """Pearson correlation of two agents' binary error indicators, per config.

    Fleiss' kappa measures agreement on labels regardless of correctness. This
    measures dependence between ERRORS, which is what "de-correlation" asserts.
    Two label treatments: HOLD abstains (the accuracy convention, but the scored
    subset then differs by config), or HOLD counts as wrong (identical subset for
    every config, so no selection).
    """
    cells = collections.defaultdict(dict)
    for r in rows:
        cells[(r["config"], r["ticker"], r["date"], r["run_idx"])][int(r["agent_idx"])] = r
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for (cfg, t_, d_, _run), ag in cells.items():
        s = signs.get((t_, d_))
        if s is None or s == 0: continue
        err = {}
        for i, a in ag.items():
            pred = {"BUY": 1, "SELL": -1}.get(a["direction"])
            if pred is None:
                if hold_is_wrong: err[i] = 1
            else:
                err[i] = 0 if pred == s else 1
        for i, j in itertools.combinations(sorted(err), 2):
            per[cfg][t_].append((err[i], err[j]))

    def phi(v):
        n = len(v)
        if n < 2: return float("nan")
        x = sum(a for a, _ in v)/n; y = sum(b for _, b in v)/n
        den = math.sqrt(x*(1-x)*y*(1-y))
        return (sum((a-x)*(b-y) for a, b in v)/n)/den if den > 1e-12 else float("nan")

    tick = sorted({t_ for cfg in per for t_ in per[cfg]})
    pt = {c: phi([x for t_ in tick for x in per[c].get(t_, [])]) for c in per}
    rng = random.Random(SEED); d = []
    for _ in range(DRAWS):
        s = [tick[rng.randrange(len(tick))] for _ in tick]
        a = phi([x for t_ in s for x in per["HOM"].get(t_, [])])
        b = phi([x for t_ in s for x in per["HET"].get(t_, [])])
        if not (math.isnan(a) or math.isnan(b)): d.append(a-b)
    d.sort()
    return {"phi": pt, "d_phi": pt["HOM"]-pt["HET"],
            "d_phi_ci": [d[int(.025*len(d))], d[int(.975*len(d))-1]] if len(d) >= 20 else [None, None]}


def main() -> int:
    rows = load_rows(io_paths.resolve_data_path("data/confirmatory/latest/runs.csv"))
    cfg = json.loads(json.dumps({}))  # placeholder; signs loaded from cache below
    import yaml
    c = yaml.safe_load((io_paths.data_root()/"configs"/"config.yaml").read_text())
    signs, _err = M.forward_return_signs(c["tickers"], c["dates"], int(c["forward_return_days"]))

    res = {"n_calls": len(rows),
           "R3.3_error_correlation_scored": error_correlation(rows, signs, hold_is_wrong=False),
           "R3.3_error_correlation_strict": error_correlation(rows, signs, hold_is_wrong=True),
           "R3.2_clustering": clustering(rows),
           "R1.4_unanimous_incorrect": unanimous_wrong(rows, signs),
           "R1.5_independence_by_pair_type": independence(rows),
           "R1.1_R3.4_selective_prediction": selective(rows, signs)}

    for k in ("scored", "strict"):
        e = res[f"R3.3_error_correlation_{k}"]
        ph = "  ".join(f"{c}={e['phi'][c]:.4f}" for c in ("HOM","HET-LITE","HET") if c in e["phi"])
        print(f"   R3.3 error correlation ({k:6s}): {ph}   Δφ={e['d_phi']:+.4f} "
              f"CI [{e['d_phi_ci'][0]:+.4f}, {e['d_phi_ci'][1]:+.4f}]")

    d = res["R3.2_clustering"]
    print(f"   R3.2 bootstrap unit (Δκ point = {d['ticker']['point']:+.4f}):")
    for k in ("ticker", "date", "two_way"):
        lo, hi = d[k]["ci"]
        print(f"     {k:8s} clusters={d[k]['n_clusters']:5d}  95% CI [{lo:+.4f}, {hi:+.4f}]  width {hi-lo:.4f}")
    u = res["R1.4_unanimous_incorrect"]
    print(f"   R1.4 unanimous-incorrect: HOM {u['hom'][0]:.4f} (n={u['hom'][1]}) vs HET {u['het'][0]:.4f} "
          f"(n={u['het'][1]}); ratio {u['ratio']:.3f} CI [{u['ratio_ci'][0]:.3f}, {u['ratio_ci'][1]:.3f}]")
    print("   R1.5 agreement by pair type:")
    for k, v in res["R1.5_independence_by_pair_type"].items():
        sm = f"{v['same_model_agreement']:.4f}" if v['same_model_agreement'] is not None else "  n/a "
        dm = f"{v['diff_model_agreement']:.4f}" if v['diff_model_agreement'] is not None else "  n/a "
        print(f"     {k:9s} same-model {sm} (n={v['same_model_pairs']:6,})  diff-model {dm} (n={v['diff_model_pairs']:6,})")
    print("   R1.1/R3.4 selective prediction (rank by conviction):")
    for k, v in res["R1.1_R3.4_selective_prediction"].items():
        print(f"     {k:9s} n={v['n']:5d} risk@100%={v['full_coverage_risk']:.4f} "
              f"risk@50%={v['risk_at_50pct_coverage']:.4f} AURC={v['aurc']:.4f}")

    dest = ROOT/"results"/"revision_metrics.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1))
    print(f"   wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
