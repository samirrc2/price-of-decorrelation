"""Emit results/latest/claims.json: every number the paper is allowed to assert.

The analysis wrote its numbers only into prose markdown, so nothing could mechanically
compare the manuscript against the computed results -- a stale figure in main.tex would
survive a clean reproduction, which is exactly how Paper 2's build gate earns its keep.

This parses the analysis's own machine-readable outputs (results/latest/tables/*.csv) and
the metrics summary, and writes one flat JSON of named claims. check_claims.py then asserts
the manuscript agrees with it.

Parsing the summary prose is deliberate: those numbers are what a reader sees, so binding
the manuscript to the PROSE catches a drift that binding to an internal structure would
miss. Where a number exists in both the CSV and the prose, the CSV wins and a disagreement
is itself reported.

  python code/src/make_claims.py        # -> results/latest/claims.json
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def from_summary(p: Path) -> dict:
    """The headline endpoint, its CI, the component kappas and the capture counts."""
    t = p.read_text()
    c = {}
    m = re.search(r"\*\*Primary endpoint\s+.{0,40}?=\s*([0-9]+\.[0-9]+)\*\*,\s*"
                  r"95% CI\s*\[([0-9]+\.[0-9]+),\s*([0-9]+\.[0-9]+)\]", t)
    if m:
        c["primary_delta_kappa"] = float(m.group(1))
        c["primary_ci_low"] = float(m.group(2))
        c["primary_ci_high"] = float(m.group(3))
    # [0-9.]+ also matches a trailing sentence period ("0.2154." -> ValueError), so the
    # fractional part is matched explicitly instead.
    _f = r"([0-9]+\.[0-9]+)"
    m = (re.search(r"\\?kappa_HOM=" + _f + r",\s*\\?kappa_HET=" + _f, t)
         or re.search("κ_HOM=" + _f + r",\s*κ_HET=" + _f, t))
    if m:
        c["kappa_hom"] = float(m.group(1)); c["kappa_het"] = float(m.group(2))
    m = re.search(r"Calls logged \(incl\. retries\):\s*([0-9]+)\s*\|\s*usable:\s*([0-9]+)", t)
    if m:
        c["calls_logged"] = int(m.group(1)); c["calls_usable"] = int(m.group(2))
    m = re.search(r"VERDICT:\s*([A-Z]+)", t)
    if m:
        c["verdict"] = m.group(1)
    m = re.search(r"`runs\.csv` SHA-256=`([0-9a-f]{64})`", t)
    if m:
        c["runs_csv_sha256"] = m.group(1)
    m = re.search(r"Grid COMPLETE:\s*([0-9]+)/([0-9]+) cells", t)
    if m:
        c["grid_cells_present"] = int(m.group(1)); c["grid_cells_total"] = int(m.group(2))
    return c


def from_tables(d: Path) -> dict:
    """Secondary contrasts and the cost/kappa frontier, straight from the CSVs."""
    c = {}
    f = d / "endpoints.csv"
    if f.exists():
        # Read whatever the CSV actually calls its columns. An earlier version looked for
        # "contrast"/"delta_kappa", while the file writes "endpoint"/"estimate" -- so all
        # three secondary contrasts and SIX confidence bounds, i.e. the whole of the
        # manuscript's Table 2, were silently dropped from the claims.
        rows = list(csv.DictReader(f.open()))
        for r in rows:
            key = next((r[k] for k in ("endpoint", "contrast", "name") if r.get(k)), "")
            if not key:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            for col, suf in (("estimate", ""), ("delta_kappa", ""), ("dk", ""),
                             ("ci_low", "_ci_low"), ("ci_high", "_ci_high")):
                if col in r and _num(r[col]) is not None:
                    c[f"contrast_{slug}{suf}"] = _num(r[col])
        if rows and not any(k.startswith("contrast_") for k in c):
            raise SystemExit("[claims] endpoints.csv parsed to NOTHING -- its columns are "
                             f"{list(rows[0])}; fix the reader rather than shipping an "
                             "empty gate")
    f = d / "frontier.csv"
    if f.exists():
        for r in csv.DictReader(f.open()):
            cfg = (r.get("config") or "").strip().lower().replace("-", "_")
            if not cfg:
                continue
            for col, name in (("kappa", "kappa"), ("cost_per_decision", "cost"),
                              ("cost_per_decision_usd", "cost"),
                              ("usd_per_ensemble_decision", "cost"),
                              ("heterogeneity_level", "level"), ("level", "level")):
                if col in r and _num(r[col]) is not None:
                    c[f"frontier_{cfg}_{name}"] = _num(r[col])
    return c


def from_revision(root: Path) -> dict:
    """Revision-arm numbers (MMLU replication, reviewer analyses) if those arms have run."""
    c = {}
    for name, f in (("mmlu", root / "results" / "mmlu_replication.json"),
                    ("revision", root / "results" / "revision_metrics.json")):
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text())
        except Exception as e:
            print(f"  [warn] {f.name} unreadable: {e}", file=sys.stderr); continue
        def walk(o, pre):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, f"{pre}_{re.sub(r'[^a-z0-9]+','_',str(k).lower()).strip('_')}")
            elif isinstance(o, (list, tuple)):
                # LISTS WERE SILENTLY SKIPPED. Every confidence interval in these files is a
                # two-element list, so the entire clustering-robustness table -- which the
                # manuscript prints as Table 6 -- was absent from the claims and therefore
                # ungated. A CI pair becomes _low/_high; anything longer is indexed.
                if len(o) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                       for x in o):
                    c[f"{pre}_low"], c[f"{pre}_high"] = float(o[0]), float(o[1])
                else:
                    for i, v in enumerate(o):
                        walk(v, f"{pre}_{i}")
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                c[pre] = o
        walk(d, name)
    return c


def from_capture(runs_csv: Path) -> dict:
    """Request accounting straight from the capture CSV.

    The manuscript states 94,566 requests, 40,566 unsuccessful, and splits those into 40,544
    rate-limit-or-quota and 22 transport-or-schema. Nothing computed that split, so those
    three numbers were unverifiable -- and a first attempt to check them with a narrower
    "rate|429" pattern gave 37,419, which would have read as a discrepancy in the paper
    rather than in the checker. The categories below are the manuscript's own.
    """
    if not runs_csv.exists():
        return {}
    import csv as _csv
    rl = re.compile(r"429|rate.?limit|RESOURCE_EXHAUSTED|quota", re.I)
    total = ok = ratelimit = other = 0
    with runs_csv.open(newline="", encoding="utf-8", errors="replace") as f:
        for r in _csv.DictReader(f):
            total += 1
            if r.get("ok") == "True":
                ok += 1
            elif rl.search(r.get("error") or ""):
                ratelimit += 1
            else:
                other += 1
    return {"capture_requests_total": total,
            "capture_requests_ok": ok,
            "capture_requests_unsuccessful": total - ok,
            "capture_unsuccessful_ratelimit_or_quota": ratelimit,
            "capture_unsuccessful_transport_or_schema": other}


def harvest_tables(path: Path, prefix: str) -> dict:
    """Every numeric cell of every markdown table in a file, keyed section/row/column.

    Hand-written per-table regexes kept missing whole tables -- the within-run/cross-run
    check, the cost-by-provider table, the provider-pair matrix and the accuracy proxy were
    all present in metrics_summary.md and all absent from the claims. A generic harvester
    cannot silently skip a table it was never taught about, and a bracketed interval becomes
    _low/_high rather than being dropped.
    """
    if not path.exists():
        return {}
    out, section = {}, ""
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("#"):
            section = re.sub(r"[^a-z0-9]+", "_", ln.lstrip("# ").lower()).strip("_")[:44]
            i += 1; continue
        if ln.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            hdr = [re.sub(r"[^a-z0-9]+", "_", h.strip().strip("*").lower()).strip("_") or f"c{j}"
                   for j, h in enumerate(ln.strip("|").split("|"))]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip().strip("*") for c in lines[i].strip().strip("|").split("|")]
                row = re.sub(r"[^a-z0-9]+", "_", cells[0].lower()).strip("_") or "row"
                for h, cell in zip(hdr[1:], cells[1:]):
                    base = f"{prefix}_{section}_{row}_{h}" if section else f"{prefix}_{row}_{h}"
                    m = re.match(r"^\[\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\]$", cell)
                    if m:
                        out[f"{base}_low"] = float(m.group(1))
                        out[f"{base}_high"] = float(m.group(2))
                        continue
                    m = re.match(r"^\$?(-?[0-9]+(?:\.[0-9]+)?)", cell)
                    if m:
                        try:
                            out[base] = float(m.group(1))
                        except ValueError:
                            pass
                i += 1
            continue
        i += 1
    return out


def from_supporting(res: Path) -> dict:
    """Numbers from the three supporting analyses the manuscript also cites.

    These were previously unextracted, so roughly a hundred manuscript figures -- the
    HET-SameTier control, the temperature sweep, the alpha/AC1 robustness table, the
    unanimity and hit rates -- were asserted with nothing to check them against.
    """
    c = {}
    f = res / "control_result.md"
    if f.exists():
        t = f.read_text()
        m = re.search(r"kappa_HOM\s*=\s*([0-9.]+);\s*kappa_HET-SAMETIER\s*=\s*([0-9.]+);\s*"
                      r"Delta-kappa\s*=\s*([0-9.]+)\s*\(95% CI \[([0-9.]+),\s*([0-9.]+)\]", t)
        if m:
            c["control_kappa_hom"] = float(m.group(1))
            c["control_kappa_het_sametier"] = float(m.group(2))
            c["control_delta_kappa"] = float(m.group(3))
            c["control_ci_low"] = float(m.group(4))
            c["control_ci_high"] = float(m.group(5))

    f = res / "temp_sweep_result.md"
    if f.exists():
        for row in re.finditer(
                r"^\|\s*(0\.0|0\.7|1\.0)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*"
                r"([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*\[([0-9.]+),\s*([0-9.]+)\]\s*\|\s*"
                r"([0-9.]+)\s*\|", f.read_text(), re.M):
            T = row.group(1).replace(".", "")
            for i, name in enumerate(("kappa_hom", "kappa_het_lite", "kappa_het",
                                      "dk_hom_het", "ci_low", "ci_high", "dk_hom_hetlite"), start=2):
                c[f"temp_T{T}_{name}"] = float(row.group(i))

    f = res / "reviewer_metrics.md"
    if f.exists():
        t = f.read_text()
        # Parse by the table's own HEADER ROW, not by row shape. An earlier version matched
        # "| HOM | num | num | num |" anywhere, so the BUY/HOLD/SELL table silently
        # overwrote the agreement table and HOM's Fleiss kappa was recorded as 0.212
        # instead of 0.5517 -- a gate asserting the wrong number is worse than no gate.
        COLS = {
            "Fleiss": ("fleiss_kappa", "krippendorff_alpha", "gwet_ac1"),
            "BUY": ("share_buy", "share_hold", "share_sell", "n_calls"),
            "scoreable": ("scoreable", "unanimous_rate", "unanimous_wrong_rate",
                          "p_agree_majority_wrong"),
            "low (1-2)": ("hit_low", "hit_mid", "hit_high"),
        }
        lines = t.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("| config") or line.startswith("| Config"):
                names = next((v for k, v in COLS.items() if k in line), None)
                i += 2                                  # skip the |---| separator
                while i < len(lines) and lines[i].startswith("|"):
                    cells = [x.strip() for x in lines[i].strip("|").split("|")]
                    cfg = cells[0].lower().replace("-", "_")
                    if names and cfg in ("hom", "het_lite", "het"):
                        for name, raw in zip(names, cells[1:]):
                            m2 = re.match(r"^([0-9]+(?:\.[0-9]+)?)", raw)
                            if m2:
                                c[f"rev_{cfg}_{name}"] = float(m2.group(1))
                    i += 1
                continue
            i += 1
        # any "label ... = 0.123" or "is 0.123 for HOM, 0.456 for HET-LITE" prose triples
        for m in re.finditer(r"(unanimity rate|hit rates?|incorrect majority|unanimous, directional, and incorrect)"
                             r"[^.]{0,80}?([0-9]\.[0-9]+)\s*for HOM[^.]{0,40}?([0-9]\.[0-9]+)\s*for HET-LITE"
                             r"[^.]{0,40}?([0-9]\.[0-9]+)\s*for HET", t):
            slug = re.sub(r"[^a-z0-9]+", "_", m.group(1).lower()).strip("_")
            for cfg, g in (("hom", 2), ("het_lite", 3), ("het", 4)):
                c[f"rev_{slug}_{cfg}"] = float(m.group(g))
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=None,
                    help="results dir (default: results/latest)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = Path(a.results) if a.results else ROOT / "results" / "latest"
    if not res.exists():
        print(f"[claims] {res} absent -- run the analysis first", file=sys.stderr)
        return 2
    claims = {}
    s = res / "metrics_summary.md"
    if s.exists():
        claims.update(from_summary(s))
    claims.update(from_tables(res / "tables"))
    claims.update(from_supporting(res))
    # generic sweep of every markdown table, so a table nobody wrote a parser for is still
    # extracted and therefore still gateable
    for fn, pref in (("metrics_summary.md", "ms"), ("reviewer_metrics.md", "rm"),
                     ("temp_sweep_result.md", "ts"), ("control_result.md", "cr"),
                     ("headline_check.md", "hc"), ("protocol_exhibit.md", "pe")):
        claims.update(harvest_tables(res / fn, pref))
    claims.update(from_revision(ROOT))
    import os as _os
    _rc = _os.environ.get("POD_RUNS_CSV") or str(ROOT / "data/confirmatory/latest/runs.csv")
    claims.update(from_capture(Path(_rc)))
    if "primary_delta_kappa" not in claims:
        print("[claims] refusing to write: the PRIMARY endpoint did not parse out of "
              "metrics_summary.md -- a claims file without it would gate nothing",
              file=sys.stderr)
        return 1
    out = Path(a.out) if a.out else res / "claims.json"
    out.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n")
    print(f"[claims] {len(claims)} named claims -> {out.relative_to(ROOT)}")
    for k in ("primary_delta_kappa", "primary_ci_low", "primary_ci_high", "verdict",
              "calls_usable"):
        if k in claims:
            print(f"    {k} = {claims[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
