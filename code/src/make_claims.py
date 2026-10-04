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
        for r in csv.DictReader(f.open()):
            key = (r.get("contrast") or r.get("name") or "").strip()
            if not key:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            for col, suf in (("delta_kappa", ""), ("dk", ""), ("ci_low", "_ci_low"),
                             ("ci_high", "_ci_high")):
                if col in r and _num(r[col]) is not None:
                    c[f"contrast_{slug}{suf}"] = _num(r[col])
    f = d / "frontier.csv"
    if f.exists():
        for r in csv.DictReader(f.open()):
            cfg = (r.get("config") or "").strip().lower().replace("-", "_")
            if not cfg:
                continue
            for col, name in (("kappa", "kappa"), ("cost_per_decision", "cost"),
                              ("usd_per_ensemble_decision", "cost"), ("level", "level")):
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
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                c[pre] = o
        walk(d, name)
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
    claims.update(from_revision(ROOT))
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
