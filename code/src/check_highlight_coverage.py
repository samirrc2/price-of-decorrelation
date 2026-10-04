#!/usr/bin/env python3
"""Gate: every word the revision changed is highlighted, and unchanged text is not.

The overlay's other checks verify that the highlighted PDF matches the manuscript line for line
and that the build located every change it was told about. Neither asks the question a reviewer
actually asks: is what is painted the same as what changed? Four defects got past them -- a blank
highlighted line, the author's name marked, a table row half marked, every formula left plain --
and each was found by a person reading the PDF.

This computes the answer independently of the overlay. It compiles the manuscript as submitted
from the `as-submitted` tag, diffs the two RENDERED word streams, and compares that set against
the yellow actually on the page.

  missed      a changed word with no highlight behind it. Always a failure: the reviewer is
              being shown a revision with a change hidden in it.
  over-marked a highlighted word that did not change. Allowed up to a budget, because closing
              short gaps inside a rewritten sentence is deliberate -- a word-level diff keeps
              whatever words a rewrite happens to reuse, and leaving them white reads as a
              mistake. Unbounded, though, it would mean the highlighting says nothing.

Exit 0 passed, 1 failed, 2 could not be checked here.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "submission"))

OVER_MARK_BUDGET = 0.10          # of all changed words


def main() -> int:
    try:
        import pymupdf
        from highlight_overlay import word_stream, changed_words, build_baseline
    except ImportError as e:
        print(f"[highlight-coverage] INCOMPLETE: {e}", file=sys.stderr)
        return 2
    clean = ROOT / "submission" / "main_manuscript.pdf"
    high = ROOT / "submission" / "highlighted_pdf.pdf"
    if not (clean.exists() and high.exists()):
        return 2
    if subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet",
                       "as-submitted^{commit}"], capture_output=True).returncode != 0:
        print("[highlight-coverage] INCOMPLETE: no as-submitted tag in this copy", file=sys.stderr)
        return 2
    base = build_baseline(ROOT, "as-submitted", ROOT / ".baseline_build")
    if base is None:
        print("[highlight-coverage] INCOMPLETE: the baseline manuscript did not build",
              file=sys.stderr)
        return 2

    old = word_stream(pymupdf.open(base))
    new = word_stream(pymupdf.open(clean))
    changed, _moved = changed_words([t[0] for t in old], [t[0] for t in new])

    hl = pymupdf.open(high)

    def yellow(c):
        return (c is not None and not isinstance(c, (int, float)) and len(c) == 3
                and c[0] > 0.9 and c[1] > 0.85 and c[2] < 0.45)

    rects = {i: [d["rect"] for d in hl[i].get_drawings() if yellow(d.get("fill"))]
             for i in range(len(hl))}
    painted = {i for i, t in enumerate(new)
               if any(r.intersects(pymupdf.Rect(t[1][0][1])) for r in rects[t[1][0][0]])}

    missed = sorted(changed - painted)
    over = sorted(painted - changed)
    fails = []
    if missed:
        words = [t[0] for t in new]
        for i in missed[:6]:
            fails.append(f"changed but NOT highlighted, page {new[i][1][0][0] + 1}: "
                         f"...{' '.join(words[max(0, i - 5):i + 6])}...")
        if len(missed) > 6:
            fails.append(f"... and {len(missed) - 6} more unhighlighted changed word(s)")
    budget = int(OVER_MARK_BUDGET * max(1, len(changed)))
    if len(over) > budget:
        fails.append(f"{len(over)} word(s) highlighted that did not change, over the budget of "
                     f"{budget} ({OVER_MARK_BUDGET:.0%} of {len(changed)} changed words)")

    if fails:
        for f in fails:
            print("  " + f, file=sys.stderr)
        print(f"[highlight-coverage] FAILED", file=sys.stderr)
        return 1
    print(f"[highlight-coverage] {len(changed)} changed word(s) against as-submitted, "
          f"{len(missed)} unhighlighted; {len(over)} highlighted that did not change, within the "
          f"budget of {budget}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
