"""Analysis for the cross-domain replication arm (MMLU medical decisions).

Separate from analyze.py, which is frozen for the confirmatory finance study and
depends on forward-return signs that do not exist here. The estimators themselves are
reused unchanged from metrics.py, so the two arms are compared like for like.

Reports, against the pre-registration in docs/preregistration_mmlu.md:
  primary    Δκ(HOM−HET), cluster bootstrap over items
  primary    Δφ(HOM−HET), error correlation between agent pairs
  secondary  the same split by item difficulty (median per-item accuracy)
"""
from __future__ import annotations
import argparse, csv, itertools, json, math, os, random, sys, collections
from pathlib import Path

os.environ.setdefault("POD_LABELS", "A,B,C,D")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics as M                                            # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ["HOM", "HET-LITE", "HET"]


def load(runs_csv: Path):
    with runs_csv.open(newline="", encoding="utf-8", errors="replace") as f:
        return [r for r in csv.DictReader(f) if r["ok"] == "True"]


def kappa(rows, cfg):
    k, _ = M.kappa_per_run_avg(rows, cfg)
    return k


def phi(pairs):
    n = len(pairs)
    if n < 2:
        return float("nan")
    x = sum(a for a, _ in pairs) / n
    y = sum(b for _, b in pairs) / n
    den = math.sqrt(x * (1 - x) * y * (1 - y))
    if den < 1e-12:
        return float("nan")
    return (sum((a - x) * (b - y) for a, b in pairs) / n) / den


def err_pairs(rows, truth, items=None):
    """{config: {item: [(err_i, err_j), ...]}} over agent pairs within a cell."""
    cells = collections.defaultdict(dict)
    for r in rows:
        if items is not None and r["ticker"] not in items:
            continue
        cells[(r["config"], r["ticker"], r["run_idx"])][int(r["agent_idx"])] = r
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for (cfg, item, _run), agents in cells.items():
        e = {i: (0 if a["direction"] == truth[item]["answer"] else 1) for i, a in agents.items()}
        for i, j in itertools.combinations(sorted(e), 2):
            out[cfg][item].append((e[i], e[j]))
    return out


def capability_matched(rows, truth, items, draws, seed):
    """Same-provider vs cross-provider error correlation, holding member accuracy fixed.

    The manuscript asserts this contrast -- member accuracies, phi within and across
    provider, their difference and a CI -- and NO code in the repository computed it. The
    five figures existed only in main.tex, so nothing could regenerate or check them. This
    closes that gap using the same phi and bootstrap primitives as the rest of the file.

    Within the fully heterogeneous configuration every cell holds one agent per provider, so
    a PAIR of agent slots is either same-provider or cross-provider with the item set and
    ensemble composition fixed. Pairs are grouped by (provider_i, provider_j); each group's
    member accuracy is the mean accuracy of the two slots, which is what "capability-matched"
    refers to.
    """
    cells = collections.defaultdict(dict)
    prov = {}
    for r in rows:
        if r["config"] != "HET" or r["ticker"] not in items:
            continue
        key = (r["ticker"], r["run_idx"])
        cells[key][int(r["agent_idx"])] = r
        prov[int(r["agent_idx"])] = r["provider"]

    # per-pair-group: error pairs, and the accuracy of the two slots involved
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    hits = collections.defaultdict(lambda: [0, 0])
    for (item, _run), agents in cells.items():
        e = {i: (0 if a["direction"] == truth[item]["answer"] else 1) for i, a in agents.items()}
        for i in e:
            hits[i][0] += 1 - e[i]; hits[i][1] += 1
        for i, j in itertools.combinations(sorted(e), 2):
            pi, pj = prov.get(i, "?"), prov.get(j, "?")
            kind = "same" if pi == pj else "cross"
            groups[(kind, tuple(sorted((pi, pj))), (i, j))][item].append((e[i], e[j]))

    acc = {i: (h[0] / h[1] if h[1] else float("nan")) for i, h in hits.items()}
    rec = []
    for (kind, provs, slots), byitem in sorted(groups.items(), key=lambda kv: str(kv[0])):
        flat = [p for v in byitem.values() for p in v]
        a = (acc.get(slots[0], float("nan")) + acc.get(slots[1], float("nan"))) / 2
        rec.append({"kind": kind, "providers": list(provs), "slots": list(slots),
                    "member_accuracy": a, "phi": phi(flat), "n_pairs": len(flat),
                    "_byitem": byitem})

    # The capability-matched contrast groups by PROVIDER COMBINATION, not by individual slot
    # pair: a provider combination can occupy more than one slot pair, and the contrast is
    # between provider combinations. (Selecting a single slot pair instead gave phi 0.612
    # against the 0.607 the manuscript reports -- the manuscript pools the two google-xai
    # slot pairs, which is the correct estimator for a provider-level claim.)
    bycombo = collections.defaultdict(list)
    for r in rec:
        bycombo[(r["kind"], tuple(r["providers"]))].append(r)
    combos = []
    for (kind, provs), members in bycombo.items():
        allpairs = [p for m in members for v in m["_byitem"].values() for p in v]
        byitem = collections.defaultdict(list)
        for m in members:
            for it, v in m["_byitem"].items():
                byitem[it].extend(v)
        combos.append({"kind": kind, "providers": list(provs),
                       "member_accuracy": sum(m["member_accuracy"] for m in members) / len(members),
                       "phi": phi(allpairs), "n_pairs": len(allpairs),
                       "n_slot_pairs": len(members), "_byitem": byitem})

    best = None
    for a in (r for r in combos if r["kind"] == "same"):
        for b in (r for r in combos if r["kind"] == "cross"):
            if math.isnan(a["member_accuracy"]) or math.isnan(b["member_accuracy"]):
                continue
            gap = abs(a["member_accuracy"] - b["member_accuracy"])
            if best is None or gap < best[0]:
                best = (gap, a, b)
    out = {"selection_rule": "same/cross PROVIDER COMBINATION minimising "
                             "|member accuracy difference|; slot pairs within a "
                             "combination are pooled",
           "pairs": [{k: v for k, v in r.items() if k != "_byitem"} for r in rec],
           "provider_combinations": [{k: v for k, v in r.items() if k != "_byitem"}
                                     for r in combos]}
    if best is not None:
        gap, a, b = best
        fa = lambda its: phi([p for it in its for p in a["_byitem"].get(it, [])])
        fb = lambda its: phi([p for it in its for p in b["_byitem"].get(it, [])])
        lo, hi = boot_delta(fa, fb, items, draws, seed)
        out["matched"] = {
            "accuracy_gap": gap,
            "same_provider": {"providers": a["providers"], "member_accuracy": a["member_accuracy"],
                              "phi": a["phi"]},
            "cross_provider": {"providers": b["providers"], "member_accuracy": b["member_accuracy"],
                               "phi": b["phi"]},
            "d_phi": a["phi"] - b["phi"], "d_phi_ci": [lo, hi]}
        # the manuscript also asserts EVERY same-provider pair exceeds EVERY cross-provider
        # pair; that is a checkable statement, so compute it rather than restate it
        sp = [r["phi"] for r in rec if r["kind"] == "same" and not math.isnan(r["phi"])]
        cp = [r["phi"] for r in rec if r["kind"] == "cross" and not math.isnan(r["phi"])]
        out["every_same_exceeds_every_cross"] = bool(sp and cp and min(sp) > max(cp))
    return out


def boot_delta(fn_a, fn_b, items, draws, seed):
    rng = random.Random(seed)
    d = []
    for _ in range(draws):
        s = [items[rng.randrange(len(items))] for _ in range(len(items))]
        a, b = fn_a(s), fn_b(s)
        if a is not None and b is not None and not (math.isnan(a) or math.isnan(b)):
            d.append(a - b)
    d.sort()
    if len(d) < 20:
        return None, None
    return d[int(.025 * len(d))], d[int(.975 * len(d)) - 1]


def report(rows, truth, items, draws, seed, label):
    print(f"\n   ===== {label} — {len(items)} items, {len(rows):,} calls =====")
    by_item = collections.defaultdict(list)
    for r in rows:
        by_item[r["ticker"]].append(r)

    print(f"   {'config':10s} {'kappa':>8s} {'phi':>8s} {'accuracy':>9s}")
    ks, ps = {}, {}
    ep = err_pairs(rows, truth, set(items))
    for c in CONFIGS:
        sub = [r for r in rows if r["config"] == c]
        if not sub:
            continue
        ks[c] = kappa(sub, c)
        flat = [x for it in items for x in ep[c].get(it, [])]
        ps[c] = phi(flat)
        acc = sum(1 for r in sub if r["direction"] == truth[r["ticker"]]["answer"]) / len(sub)
        print(f"   {c:10s} {ks[c]:8.4f} {ps[c]:8.4f} {acc:9.4f}")

    # Partial collections are normal while the grid is still filling: the orchestrator
    # writes config-major, so HOM completes before HET exists. Report what is present
    # rather than failing, so progress can be inspected mid-run.
    if not {"HOM", "HET"} <= set(ks):
        print(f"   contrast unavailable: have {sorted(ks)}; need HOM and HET")
        return {"kappa": ks, "phi": ps, "partial": True, "n_items": len(items)}

    def kf(cfg):
        return lambda s: kappa([r for it in s for r in by_item[it] if r["config"] == cfg], cfg)

    def pf(cfg):
        return lambda s: phi([x for it in s for x in ep[cfg].get(it, [])])

    lo, hi = boot_delta(kf("HOM"), kf("HET"), items, draws, seed)
    dk = ks["HOM"] - ks["HET"]
    print(f"   Δκ(HOM−HET) = {dk:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]" if lo is not None
          else f"   Δκ = {dk:+.4f} (CI unavailable)")
    lo2, hi2 = boot_delta(pf("HOM"), pf("HET"), items, draws, seed)
    dp = ps["HOM"] - ps["HET"]
    print(f"   Δφ(HOM−HET) = {dp:+.4f}  95% CI [{lo2:+.4f}, {hi2:+.4f}]" if lo2 is not None
          else f"   Δφ = {dp:+.4f} (CI unavailable)")
    return {"kappa": ks, "phi": ps, "d_kappa": dk, "d_kappa_ci": [lo, hi],
            "d_phi": dp, "d_phi_ci": [lo2, hi2], "n_items": len(items)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=None)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    runs_csv = Path(a.runs) if a.runs else sorted(ROOT.glob("data/mmlu/*/runs.csv"))[-1]
    truth = json.loads((ROOT / "data" / "mmlu_ground_truth.json").read_text())
    rows = load(runs_csv)
    if not rows:
        print("   no successful rows yet"); return 2
    items = sorted({r["ticker"] for r in rows})

    # Record the input RELATIVE to the repository root, plus its SHA-256. An absolute path
    # makes this file unreproducible by construction -- the capsule and a local checkout
    # produced byte-different JSON for identical data, which defeats the whole point of
    # hash-comparing outputs. The hash is what actually identifies the input.
    import hashlib
    try:
        rel = runs_csv.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        rel = runs_csv.name           # input from outside the repo: name only, never a path
    _h = hashlib.sha256()
    with runs_csv.open("rb") as _f:
        for _b in iter(lambda: _f.read(1 << 20), b""):
            _h.update(_b)
    out = {"runs_csv": rel, "runs_csv_sha256": _h.hexdigest(),
           "overall": report(rows, truth, items, a.draws, a.seed, "OVERALL"),
           "capability_matched": capability_matched(rows, truth, items, a.draws, a.seed)}

    # secondary: difficulty split at median per-item accuracy (pre-registered as exploratory)
    acc = {it: sum(1 for r in rows if r["ticker"] == it and r["direction"] == truth[it]["answer"])
               / max(1, sum(1 for r in rows if r["ticker"] == it)) for it in items}
    med = sorted(acc.values())[len(acc) // 2]
    hard = [i for i in items if acc[i] <= med]
    easy = [i for i in items if acc[i] > med]
    if len(hard) > 20 and len(easy) > 20:
        out["hard"] = report([r for r in rows if r["ticker"] in set(hard)], truth, hard,
                             a.draws, a.seed, f"HARD items (accuracy ≤ {med:.2f})")
        out["easy"] = report([r for r in rows if r["ticker"] in set(easy)], truth, easy,
                             a.draws, a.seed, f"EASY items (accuracy > {med:.2f})")

    if out["overall"].get("partial"):
        print("\n   collection still in progress — no result file written")
        return 2

    dest = ROOT / "results" / "mmlu_replication.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n   wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
