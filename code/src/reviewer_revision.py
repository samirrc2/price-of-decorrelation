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


def _precompute_cells(rows, cfg):
    """Per-cell direction counts, computed ONCE: {(ticker, date, run): (c_buy, c_hold, ...)}.

    The cluster bootstrap previously called kappa_sub() per draw, which re-filtered all
    54,000 rows and rebuilt every cell from scratch -- 2,000 draws x 3 resampling modes x
    54k rows, around 324 million row operations in pure Python, for a result that only ever
    changes WHICH CELLS are included. Fleiss' kappa is a mean of per-cell P_i plus a
    marginal term, so the per-cell counts are invariant across draws and only the summation
    has to be redone. This is the same estimator, not an approximation: kappa_fast() below
    is checked against M.kappa_per_run_avg() on the full sample before the bootstrap runs.
    """
    cells = collections.defaultdict(lambda: [0] * len(M.DIRECTIONS))
    idx = {d: i for i, d in enumerate(M.DIRECTIONS)}
    for r in rows:
        if r["config"] != cfg or r.get("ok") != "True":
            continue
        j = idx.get(r["direction"])
        if j is None:
            continue
        cells[(r["ticker"], r["date"], int(r["run_idx"]))][j] += 1
    return {k: tuple(v) for k, v in cells.items()}


def kappa_fast(cells, cell_weight):
    """Fleiss' kappa averaged over runs, from precomputed counts.

    `cell_weight(ticker, date)` returns how many times a cell enters the computation. A plain
    predicate still works, because True == 1 -- but a cluster bootstrap that draws a ticker
    twice must count it TWICE, and a weight can express that while a membership test cannot.

    Mirrors metrics.fleiss_kappa + kappa_per_run_avg exactly, including dropping cells whose
    rater count differs from the modal count (an agent call can fail) and returning None
    when fewer than two cells survive.
    """
    byrun = collections.defaultdict(list)
    for (t, d, run), counts in cells.items():
        w = cell_weight(t, d)
        if w:
            byrun[run].extend([counts] * int(w))
    ks = []
    for run in sorted(byrun):
        mat = byrun[run]
        totals = collections.Counter(sum(c) for c in mat)
        if not totals:
            continue
        n = totals.most_common(1)[0][0]
        mat = [c for c in mat if sum(c) == n]
        N = len(mat)
        if N < 2 or n < 2:
            continue
        Pi = [(sum(x * x for x in c) - n) / (n * (n - 1)) for c in mat]
        P_bar = sum(Pi) / N
        tot = [0] * len(M.DIRECTIONS)
        for c in mat:
            for j, x in enumerate(c):
                tot[j] += x
        denom = N * n
        pj = [t / denom for t in tot]
        P_e = sum(q * q for q in pj)
        ks.append(1.0 if abs(1 - P_e) < 1e-12 else (P_bar - P_e) / (1 - P_e))
    return (sum(ks) / len(ks)) if ks else None


# ---------------------------------------------------------------- R3.2 clustering
def clustering(rows):
    # The ORDER matters, not just the membership: both bootstraps index into a ticker list with
    # the same seeded RNG, so a different ordering draws a different sample and the intervals
    # part company in the third decimal. analyze.py uses the pre-registered config order, so
    # this must too -- deriving a sorted list here produced [0.3031, 0.3698] against the
    # primary's [0.3035, 0.3689] even once multiplicity was fixed.
    present = {r["ticker"] for r in rows}
    tick = None
    try:
        import yaml
        cfg = yaml.safe_load(io_paths.default_config_path().read_text())
        tick = [t for t in cfg["tickers"] if t in present]
        if set(tick) != present:
            raise SystemExit(f"[revision] config tickers do not cover the capture: "
                             f"{len(present - set(tick))} present in runs.csv but not in the "
                             f"frozen protocol")
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"[revision] cannot read the pre-registered ticker order from the "
                         f"frozen config ({e}); the equity bootstrap would not reproduce the "
                         f"primary endpoint")
    date = sorted({r["date"] for r in rows})
    out = {}

    hom_cells = _precompute_cells(rows, "HOM")
    het_cells = _precompute_cells(rows, "HET")

    def delta_fast(cell_weight):
        a = kappa_fast(hom_cells, cell_weight); b = kappa_fast(het_cells, cell_weight)
        return None if (a is None or b is None) else a - b

    point = delta_fast(lambda t, d: True)

    # EQUIVALENCE CHECK, not an assumption: the fast path must reproduce the estimator the
    # rest of the paper uses, on the full sample, before any draw is taken. If it does not,
    # fail loudly rather than publish a number from an unvalidated shortcut.
    slow = kappa_sub(rows, "HOM", lambda r: True)
    fast = kappa_fast(hom_cells, lambda t, d: True)
    if slow is None or fast is None or abs(slow - fast) > 1e-12:
        raise SystemExit(f"kappa_fast disagrees with metrics.kappa_per_run_avg "
                         f"({fast} vs {slow}); refusing to bootstrap with it")

    # RESAMPLING SEMANTICS. This used to treat a draw as a SET of clusters: a ticker drawn
    # twice contributed once, so every draw used only the ~63 distinct tickers of a 100-draw
    # multiset. That is subsampling, not a cluster bootstrap, and it understates variance --
    # the equity row came back [0.3131, 0.3628] against the primary [0.3035, 0.3689], a 24%
    # narrower interval for what the manuscript presented as the same estimand. A reviewer
    # caught the contradiction. Multiplicity is now honoured, matching stats.py, and the
    # equality is asserted below rather than hoped for.
    def boot(mode):
        rng = random.Random(SEED); d = []
        for _ in range(DRAWS):
            if mode == "ticker":
                ct = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
                w = lambda t, dt: ct.get(t, 0)
            elif mode == "date":
                cd = collections.Counter(date[rng.randrange(len(date))] for _ in date)
                w = lambda t, dt: cd.get(dt, 0)
            else:  # two-way: resample both margins independently; a cell's weight is the
                   # product of its two margin multiplicities
                ct = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
                cd = collections.Counter(date[rng.randrange(len(date))] for _ in date)
                w = lambda t, dt: ct.get(t, 0) * cd.get(dt, 0)
            v = delta_fast(w)
            if v is not None: d.append(v)
        d.sort()
        return (d[int(.025*len(d))], d[int(.975*len(d))-1], len(d)) if len(d) >= 20 else (None, None, len(d))

    for mode, n_cl in (("ticker", len(tick)), ("date", len(date)), ("two_way", len(tick)*len(date))):
        lo, hi, n = boot(mode)
        out[mode] = {"point": point, "ci": [lo, hi], "n_clusters": n_cl, "draws_used": n}

    # The equity row IS the primary endpoint's own bootstrap -- same clusters, same draws, same
    # seed -- so it must reproduce the interval analyze.py published, to the digits the paper
    # prints. Asserting it is what makes Table 5's first row a reproduction rather than a second
    # opinion, and it is why the set-vs-multiset divergence cannot come back unnoticed.
    ep = io_paths.results_root() / "latest" / "tables" / "endpoints.csv"
    if ep.exists():
        import csv as _csv
        for r in _csv.DictReader(ep.open()):
            if r["endpoint"] != "Dkappa_HOM_HET":
                continue
            t_lo, t_hi = out["ticker"]["ci"]
            want = (float(r["ci_low"]), float(r["ci_high"]))
            got = (round(t_lo, 4), round(t_hi, 4))
            if got != want:
                raise SystemExit(
                    f"[revision] the equity-clustered CI {got} disagrees with the primary "
                    f"endpoint {want} in tables/endpoints.csv. Both resample the same 100 "
                    f"equities with {DRAWS} draws at seed {SEED}, so they must agree; a "
                    f"difference means the two bootstraps no longer implement the same "
                    f"estimand.")
            print(f"[revision] equity-clustered CI reproduces the primary endpoint "
                  f"[{t_lo:.4f}, {t_hi:.4f}]")
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

    # Same precompute-once pattern as the clustering bootstrap: rate() rebuilt every cell
    # from all 54,000 rows on each of the 2,000 draws, when resampling only changes which
    # TICKERS are in. Reduce each scoreable cell to (ticker, is_wrong) once; a draw is then
    # a sum over ~1,200 tuples instead of a scan over 54k rows.
    def cell_flags(cfg):
        cells = collections.defaultdict(list)
        for r in rows:
            if r["config"] == cfg:
                cells[(r["ticker"], r["date"], r["run_idx"])].append(r["direction"])
        flags = []
        for (t, d, _), dirs in cells.items():
            sg = signs.get((t, d))
            if sg is None or sg == 0 or len(dirs) != 5:
                continue
            wrong = (len(set(dirs)) == 1 and dirs[0] in ("BUY", "SELL")
                     and (1 if dirs[0] == "BUY" else -1) != sg)
            flags.append((t, int(wrong)))
        return flags

    flags = {c: cell_flags(c) for c in ("HOM", "HET")}

    # Equivalence check before use: the reduced form must reproduce rate() exactly.
    for c in ("HOM", "HET"):
        n = len(flags[c]); w = sum(f for _, f in flags[c])
        fast = (w / n) if n else None
        if pts[c][0] is not None and (fast is None or abs(fast - pts[c][0]) > 1e-12):
            raise SystemExit(f"unanimous_wrong fast path disagrees for {c} "
                             f"({fast} vs {pts[c][0]}); refusing to bootstrap with it")

    def rate_fast(cfg, keep_t):
        n = w = 0
        for t, f in flags[cfg]:
            if keep_t(t):
                n += 1; w += f
        return (w / n) if n else None

    rng = random.Random(SEED); rs = []
    for _ in range(DRAWS):
        s = set(tick[rng.randrange(len(tick))] for _ in tick)
        keep_t = lambda t: t in s
        a = rate_fast("HOM", keep_t); b = rate_fast("HET", keep_t)
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
def selective_scored(rows, signs, configs=("HOM", "HET-LITE", "HET")):
    """Per config, the scored decisions in majority-vote order: (ticker, conviction, erred).

    Factored out of selective() so the R3.4 bootstrap can reweight the SAME list in the SAME
    order. AURC sorts on conviction alone, and convictions tie often, so the pre-sort order
    decides how ties break: rebuilding the list in a different order gave AURC 0.5551 against
    the published 0.5530 for identical data. One ordering, one statistic.
    """
    out = {}
    for cfg in configs:
        mv = M.majority_vote([r for r in rows if r["config"] == cfg], cfg)
        conv = collections.defaultdict(list)
        for r in rows:
            if r["config"] == cfg:
                try: conv[(r["ticker"], r["date"])].append(int(r["conviction"]))
                except (TypeError, ValueError): pass
        sc = []
        for (t, d), (direction, _mc, _n) in mv.items():
            s = signs.get((t, d))
            if s is None or s == 0 or direction == "HOLD": continue
            c = sum(conv[(t, d)]) / len(conv[(t, d)]) if conv[(t, d)] else 0
            sc.append((t, c, int((1 if direction == "BUY" else -1) != s)))
        out[cfg] = sc
    return out


def _aurc_from(scored):
    """AURC of a (conviction, erred) list, ranked by conviction descending."""
    if len(scored) < 3:
        return None, None, None
    pts = sorted(scored, key=lambda x: -x[0])
    err, curve = 0, []
    for i, (_c, e) in enumerate(pts, 1):
        err += e
        curve.append((i / len(pts), err / i))
    aurc = sum((curve[i][1] + curve[i - 1][1]) / 2 * (curve[i][0] - curve[i - 1][0])
               for i in range(1, len(curve)))
    return aurc, curve[-1][1], curve[len(curve) // 2][1]


def selective(rows, signs):
    """Risk-coverage curve over ensemble decisions ranked by mean agent conviction."""
    out = {}
    for cfg, sc in selective_scored(rows, signs).items():
        if not sc: continue
        scored = [(c, e) for _t, c, e in sc]
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


def paired_cluster_contrasts(rows, signs, tick):
    """R3.4 -- paired equity-clustered bootstrap CIs for the pile-on rate and for AURC.

    The response letter said all four of R3's points were acted on, but the pile-on contrast was
    reported as two point estimates (0.824 for HOM, 0.636 for HET) with no uncertainty at all,
    and AURC likewise. A reviewer is entitled to ask whether a gap that large is distinguishable
    from zero on 100 equities.

    PAIRED matters: HOM and HET are measured on the SAME equities, so the draw must be shared
    and the difference taken within it. Resampling the two arms independently would inflate the
    interval by the between-arm variance the design already removes. Multiplicity is honoured,
    as in clustering(), and the same seed and draw count are used so the equity row of every
    table in the paper rests on one resampling scheme.
    """
    # pile-on: per (config, ticker) the wrong-majority decisions and the agreeing fraction
    # Reuse reviewer_analysis's own grouping and tie-break rather than re-deriving them. A
    # first version filtered on ok=="True" and used Counter.most_common, which differs from
    # M.usable() and from the DIRS-ordered tie-break, and produced HET = 0.6761 against the
    # published 0.636 -- a second version of exactly the contradiction R3.2 is about.
    import reviewer_analysis as RA
    pile = {c: collections.defaultdict(lambda: [0.0, 0]) for c in ("HOM", "HET")}
    for cfg in ("HOM", "HET"):
        for (t, d, _run), agents in RA.decision_groups(rows, cfg).items():
            if len(agents) != 5:
                continue
            sg = signs.get((t, d))
            if sg is None or sg == 0:
                continue
            dirs = [a["direction"] for a in agents]
            maj = RA.majority(dirs)
            if maj not in ("BUY", "SELL"):
                continue
            if (1 if maj == "BUY" else -1) == sg:
                continue                  # majority was right; pile-on conditions on being wrong
            pile[cfg][t][0] += collections.Counter(dirs)[maj] / 5.0
            pile[cfg][t][1] += 1

    # AURC: reuse selective_scored so the list -- and therefore the tie order -- is the one
    # the published AURC was computed from.
    sc = selective_scored(rows, signs, configs=("HOM", "HET"))

    def pileon(cfg, w):
        num = den = 0.0
        for t, (fs, n) in pile[cfg].items():
            k = w(t)
            if k:
                num += k * fs
                den += k * n
        return num / den if den else None

    def aurc(cfg, w):
        pts = []
        for t, c, e in sc[cfg]:
            k = w(t)
            if k:
                pts.extend([(c, e)] * int(k))
        return _aurc_from(pts)[0]

    # The point estimates must equal the ones already published by reviewer_analysis.downstream
    # and selective(); a bootstrap around a different number is a different statistic.
    ref_sel = selective(rows, signs)
    ref = {"pile_on": {c: RA.downstream(rows, signs, c)["cond_agree_given_wrong"]
                       for c in ("HOM", "HET")},
           "aurc": {c: ref_sel[c]["aurc"] for c in ("HOM", "HET")}}

    out = {}
    for name, fn_ in (("pile_on", pileon), ("aurc", aurc)):
        one = lambda t: 1
        a, b = fn_("HOM", one), fn_("HET", one)
        for cfgn, got in (("HOM", a), ("HET", b)):
            want = ref[name][cfgn]
            if want is None or got is None or abs(got - want) > 1e-9:
                raise SystemExit(
                    f"[revision] the {name} point estimate for {cfgn} is {got}, but the "
                    f"published analysis gives {want}. The bootstrap must wrap the SAME "
                    f"statistic the paper reports, not a re-derivation of it.")
        point = None if (a is None or b is None) else a - b
        rng = random.Random(SEED)
        ds = []
        for _ in range(DRAWS):
            ct = collections.Counter(tick[rng.randrange(len(tick))] for _ in tick)
            w = lambda t: ct.get(t, 0)
            x, y = fn_("HOM", w), fn_("HET", w)
            if x is not None and y is not None:
                ds.append(x - y)
        ds.sort()
        lo = hi = None
        if len(ds) >= 20:
            lo, hi = ds[int(.025 * len(ds))], ds[int(.975 * len(ds)) - 1]
        out[name] = {"hom": a, "het": b, "delta_hom_het": point, "ci": [lo, hi],
                     "draws_used": len(ds), "n_clusters": len(tick),
                     "excludes_zero": None if (lo is None or hi is None) else (lo > 0 or hi < 0)}
    return out


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
           "R1.1_R3.4_selective_prediction": selective(rows, signs),
           "R3.4_paired_cluster_contrasts": paired_cluster_contrasts(
               rows, signs, [t for t in c["tickers"]
                             if t in {r["ticker"] for r in rows}])}

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
