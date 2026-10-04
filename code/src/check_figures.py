"""Gate: the figures the manuscript compiles are the figures the analysis just produced.

build_paper.sh syncs results/latest/figures into paper/figures before compiling.
build_submission.sh does not -- it runs pdflatex in paper/ directly -- so every deliverable it
builds uses whatever is sitting in paper/figures. That silently shipped a two-month-old
fig2_protocol.png: the analysis had been rewritten to plot two like-for-like pilot bars, the
manuscript text and caption described two bars, and the PDF still showed the superseded
three-bar version with an empty third category. Nothing compared the two directories.

A figure is a reported result. If the one in the paper is not the one the pipeline produced,
that is the same defect as a stale number, and it is invisible to every text-based gate.

  python code/src/check_figures.py
"""
from __future__ import annotations
import hashlib
from pathlib import Path

import io_paths

ROOT = io_paths.repo_root()
PAPER = ROOT / "paper" / "figures"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    res = io_paths.results_root() / "latest" / "figures"
    if not res.exists():
        print("[figures] results/latest/figures absent -- run the analysis first")
        return 2
    if not PAPER.exists():
        print("[figures] paper/figures not published in this copy (capsule layout)")
        return 2

    produced = sorted(p for p in res.glob("*.png"))
    if not produced:
        print("[figures] the analysis produced no PNGs -- matplotlib may have been unavailable")
        return 2

    fails, checked = [], 0
    for p in produced:
        q = PAPER / p.name
        if not q.exists():
            # A figure the analysis makes but the paper does not carry is not necessarily an
            # error -- the manuscript may not include it -- so it is reported, not failed.
            print(f"     [figures] {p.name} produced but not present in paper/figures "
                  f"(not included in the manuscript?)")
            continue
        checked += 1
        if sha(p) != sha(q):
            fails.append(f"paper/figures/{p.name} differs from the one the analysis just "
                         f"produced; the manuscript would compile a stale figure "
                         f"(run: bash code/scripts/build_paper.sh, or copy it across)")

    print(f"[figures] {checked - len(fails)}/{checked} manuscript figures match the analysis "
          f"output")
    for f in fails:
        print(f"  {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
