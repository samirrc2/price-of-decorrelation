#!/usr/bin/env python3
"""Gate: the response letter and the manuscript must tell the reviewers the same story.

The three defects the author caught by reading the PDFs in this revision were all of one kind:
the letter and the paper disagreeing. The letter listed Index Terms the paper no longer had; the
letter said causal attribution had been removed while two sentences still asserted it; the letter
described the phi computation one way in R2.2 and the correct way in R3.3. None of the numeric or
structural gates can see any of those, because every individual number and pointer was fine.

This gate checks the agreements that can be stated mechanically:

  1. the Index Terms the letter quotes are the Index Terms in the manuscript, in that order;
  2. every phrase the letter claims to have REMOVED is absent from the manuscript;
  3. every phrase the letter claims the manuscript now CONTAINS is present in it;
  4. the letter contradicts itself nowhere on the phi estimand: no sentence may say phi is
     computed per agent pair except the one that says it is not.

Rules 2 and 3 are a table, because the letter's prose cannot be parsed into claims reliably --
and a table a human maintains is honest about its coverage, where a parser would silently cover
less than its name suggests. Each entry names the concern it comes from.

Exit 0 passed, 1 failed, 2 could not be checked here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "paper" / "main.tex"
LETTER = ROOT / "submission" / "response_to_reviewers.txt"

# (concern, phrase the letter says is GONE from the manuscript)
REMOVED = [
    ("R3.1", "the effect of cross-provider heterogeneity on within-ensemble agreement"),
    ("R3.1", "cross-provider heterogeneity affects"),
    ("R3.1", "Heterogeneity reduces ensemble agreement"),
    ("R3.1", "heterogeneity de-correlates ensembles"),
    ("R3.3", "For every pair of agents"),
    ("R3.5", "2026-07-03T20:41:51"),
    ("R2.2", "This article does not propose"),
]
# (concern, phrase the letter says the manuscript NOW CONTAINS). A phrase listed in HEADINGS
# must appear as a \section or \subsection title, not merely somewhere in the prose: renaming
# \subsection{Selective prediction} to "Risk-coverage analysis" left the words "selective
# prediction" in the body and passed the first version of this gate.
HEADINGS = {
    "Heterogeneity and ensemble agreement (primary)",
    "Relation to existing ensemble methods",
    "Selective prediction",
    "Agreement, error correlation, and decorrelation",
    "Cross-domain replication: clinical knowledge",
}
PRESENT = [
    ("R3.1", "the association between cross-provider heterogeneity and within-ensemble agreement"),
    ("R3.1", "Heterogeneity and ensemble agreement (primary)"),
    ("R2.2", "This research paper does not propose a new ensemble algorithm"),
    ("R2.2", "Relation to existing ensemble methods"),
    ("R1.1", "Selective prediction"),
    ("R3.3", "Agreement, error correlation, and decorrelation"),
    ("R3.6", "Cross-domain replication: clinical knowledge"),
    ("R3.5", "timestamped cryptographic freeze receipts"),
    ("R3.2", "pigeonhole"),
    ("R2.2", "diversity and ensemble accuracy are related"),
]
# the one sentence in the letter allowed to contain "per agent pair"
PHI_CORRECTION = "rather than one per agent pair"


def sq(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> int:
    if not TEX.exists() or not LETTER.exists():
        print("[response-consistency] INCOMPLETE: manuscript or letter missing", file=sys.stderr)
        return 2
    tex = TEX.read_text(errors="replace")
    tex_sq = sq(tex)
    letter = LETTER.read_text(errors="replace")
    letter_flat = " ".join(letter.split())
    fails: list[str] = []

    # 1. Index Terms agree, in order
    m = re.search(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", tex, re.S)
    if not m:
        fails.append("the manuscript has no keywords block, so the letter's Index Terms claim "
                     "cannot be checked")
    else:
        terms = [t.strip(" .\n") for t in re.split(r"[,;]", " ".join(m.group(1).split())) if
                 t.strip(" .\n")]
        lm = re.search(r"Index Terms were revised to:\s*(.+?)\.\s", letter_flat)
        if not lm:
            fails.append("the letter never states the revised Index Terms, so a reviewer cannot "
                         "check them against the paper")
        else:
            quoted = [t.strip() for t in re.split(r",| and ", lm.group(1)) if t.strip()]
            if [sq(t) for t in quoted] != [sq(t) for t in terms]:
                fails.append(f"Index Terms disagree -- manuscript: {terms}; letter: {quoted}")

    # 2/3. phrases the letter says are gone, and phrases it says are there
    for concern, phrase in REMOVED:
        if sq(phrase) in tex_sq:
            fails.append(f'{concern}: the letter reports "{phrase}" removed, but it is still in '
                         f'the manuscript')
    heads = {sq(m.group(1)) for m in
             re.finditer(r"\\(?:sub)?section\*?\{((?:[^{}]|\{[^{}]*\})*)\}", tex)}
    for concern, phrase in PRESENT:
        if phrase in HEADINGS:
            if sq(phrase) not in heads:
                fails.append(f'{concern}: the letter names "{phrase}" as a section of the '
                             f'manuscript, but no heading has that title')
        elif sq(phrase) not in tex_sq:
            fails.append(f'{concern}: the letter reports the manuscript now contains "{phrase}", '
                         f'but it does not')

    # 4. the letter must not contradict itself on the phi estimand
    for m in re.finditer(r"per agent pair", letter_flat):
        window = letter_flat[max(0, m.start() - 60):m.end()]
        if PHI_CORRECTION not in window:
            fails.append(f'the letter says phi is computed "per agent pair" outside the sentence '
                         f'that corrects it: ...{window[-90:]}')

    if fails:
        for f in fails:
            print("  " + f, file=sys.stderr)
        print(f"[response-consistency] FAILED: {len(fails)} disagreement(s) between the letter "
              f"and the manuscript", file=sys.stderr)
        return 1
    print(f"[response-consistency] Index Terms agree; {len(REMOVED)} phrase(s) the letter reports "
          f"removed are absent from the manuscript and {len(PRESENT)} it reports present are "
          f"there ({len(HEADINGS)} of them required to be headings, not prose); the letter states "
          f"the phi estimand consistently")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
