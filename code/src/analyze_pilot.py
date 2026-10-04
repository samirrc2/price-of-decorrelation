"""Derive the protocol-collapse figures from the two archived pilot captures.

The manuscript reports that the primary contrast was 0.485 under shared per-run seeding and
0.113 under independent per-agent seeding, and Fig. 2 plots the HOM within-minus-cross kappa
gap across the three stages. Until now all four of those numbers were HARDCODED in
analyze.py:

    PILOT_BROKEN = {"dkappa": 0.485, "hom_within_minus_cross": 0.377}
    PILOT_CLEAN  = {"dkappa": 0.113, "hom_within_minus_cross": 0.018}

and check_coverage.py excused 0.485 and 0.113 as "pilot-dataset value". Both excuses were
unnecessary: the artifact ships the raw captures, so the numbers are recomputable, and a
recomputed number can be gated while a hardcoded one can only be trusted.

Recomputing them also re-derives the paper's claim about the mechanism. Under shared per-run
seeding, kappa_HOM comes back as EXACTLY 1.0 -- five agents handed the same seed returned
byte-identical completions, so the ensemble was measuring one draw five times. That is the
inflation the paper attributes to the protocol, visible in the capture rather than asserted.

  python code/src/analyze_pilot.py
"""
from __future__ import annotations
import csv
import json

import io_paths
import metrics as M

# Both captures predate the current schema (the broken arm has no run_seed/seed_mode column),
# so they are read as plain row dicts and only the columns the estimator needs are touched.
ARMS = {
    "broken": ("data/pilot/broken/runs.csv",
               "shared per-run seeding: all five agents in a cell receive one seed"),
    "clean":  ("data/pilot/clean/runs.csv",
               "independent per-agent seeding: each agent draws its own seed"),
}
# The pilot copies under data/ are what the analysis reads and what the manifest pins; the
# archive/ tree keeps the pilot's original CODE alongside its data. Duplicated bytes drift,
# so the equality is asserted here rather than assumed.
ARCHIVE_MIRROR = {
    "data/pilot/clean/runs.csv": "archive/pilot_v1/runs.csv",
    "data/pilot/broken/runs.csv": "archive/pilot_v1_broken_perRunSeed/runs.csv",
}


def main() -> int:
    root = io_paths.repo_root()

    for live, mirror in ARCHIVE_MIRROR.items():
        lp, mp = root / live, root / mirror
        if not mp.exists():
            continue          # archive/ is not mounted in a /code + /data capsule
        if lp.read_bytes() != mp.read_bytes():
            raise SystemExit(f"[pilot] {live} and {mirror} have diverged. They are the same "
                             f"capture; one of the two has been edited.")

    out = {}
    for arm, (rel, why) in ARMS.items():
        p = root / rel
        if not p.exists():
            print(f"[pilot] {rel} absent -- cannot derive the protocol-collapse figures")
            return 2
        rows = list(csv.DictReader(p.open()))
        kh, per_hom = M.kappa_per_run_avg(rows, "HOM")
        kt, _ = M.kappa_per_run_avg(rows, "HET")
        cross = M.kappa_cross_run(rows, "HOM")
        if kh is None or kt is None or cross is None:
            raise SystemExit(f"[pilot] {rel} yielded no kappa -- the capture is unusable")
        out[arm] = {
            "seeding": why,
            "runs_csv": rel,
            "n_rows": len(rows),
            "kappa_hom": kh,
            "kappa_het": kt,
            "kappa_hom_per_run": per_hom,
            "dkappa": kh - kt,
            "kappa_hom_cross_run": cross,
            "hom_within_minus_cross": kh - cross,
        }

    io_paths.results_root().joinpath("latest").mkdir(parents=True, exist_ok=True)
    dest = io_paths.results_root() / "latest" / "pilot_collapse.json"
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    for arm in ("broken", "clean"):
        d = out[arm]
        print(f"[pilot] {arm:6} dkappa={d['dkappa']:.4f}  kappa_HOM={d['kappa_hom']:.4f}  "
              f"within-cross={d['hom_within_minus_cross']:.4f}  (n={d['n_rows']})")
    print(f"[pilot] wrote {dest.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
