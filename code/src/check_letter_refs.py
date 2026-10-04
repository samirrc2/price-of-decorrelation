#!/usr/bin/env python3
"""Gate: the response letter's bracketed reference numbers must resolve, in the
manuscript's own bibliography, to the source the letter names there.

The failure this exists to catch: the letter cites "[14] Owen's pigeonhole
bootstrap", the reference list is renumbered because a new citation moved an
earlier first mention, and [14] now points at something else. Nothing else in
the pipeline reads the letter, so that drift is silent.

Two checks, both narrow and both stated in the output:
  1. every [n] in the letter sits next to an identifying token for the entry
     that number actually points at -- the author surname, or the term of art
     the letter uses for that source -- and that entry's bibliography text
     carries the surname, so the number, the prose and the bibliography agree;
  2. the converse: wherever the letter names one of these sources it must carry
     that source's number nearby. Without this the gate is one-directional --
     mis-citing "pigeonhole bootstrap [16]" lands on a reference the gate has no
     rule for, and a number-keyed check skips it silently. Fault injection
     caught exactly that.
  3. every reference that is new in this revision is named somewhere in the
     letter, so no added citation goes unexplained to the reviewers.

Exit 0 passed, 1 failed, 2 could not be checked here (no main.bbl).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LETTER = ROOT / "submission" / "response_to_reviewers.txt"

# surname the bibliography entry must carry, and the tokens that may identify
# the source in the letter's prose next to the number (surname or term of art)
ATTRIB = {
    "owen2007pigeonhole":    ("Owen",      ("Owen", "pigeonhole")),
    "cameron2011multiway":   ("Cameron",   ("Cameron", "multiway")),
    "kuncheva2003diversity": ("Kuncheva",  ("Kuncheva", "diversity")),
    "elyaniv2010selective":  ("El-Yaniv",  ("El-Yaniv", "selective", "risk-coverage")),
    "hendrycks2021mmlu":     ("Hendrycks", ("Hendrycks", "MMLU")),
}
WINDOW_BEFORE, WINDOW_AFTER = 200, 90

# unambiguous phrases that name a source in the letter's prose. Wherever one
# appears, the source's own number must appear within ANCHOR_BEFORE chars before
# or ANCHOR_AFTER after it. Deliberately narrower than the tokens above: a bare
# word like "diversity" occurs all over the letter and would false-positive.
ANCHORS = {
    "owen2007pigeonhole":    ("Owen", "pigeonhole bootstrap"),
    "cameron2011multiway":   ("Cameron", "multiway-inference literature"),
    "kuncheva2003diversity": ("Kuncheva",),
    "elyaniv2010selective":  ("El-Yaniv",),
    "hendrycks2021mmlu":     ("Hendrycks", "MMLU professional-medicine"),
}
ANCHOR_BEFORE, ANCHOR_AFTER = 40, 95
# references added in this revision; each must be named in the letter
NEW = set(ATTRIB)


def bbl() -> Path | None:
    for p in (ROOT / "paper" / "main.bbl", ROOT / "submission" / "main.bbl"):
        if p.exists():
            return p
    return None


def main() -> int:
    src = bbl()
    if src is None:
        print("[letter-refs] INCOMPLETE: no main.bbl; run the LaTeX build first, "
              "then this gate can resolve numbers", file=sys.stderr)
        return 2
    raw = src.read_text(errors="replace")
    items = re.split(r"\\bibitem\{([^}]+)\}", raw)[1:]
    order = {k: i for i, (k, _) in enumerate(zip(items[0::2], items[1::2]), start=1)}
    body = dict(zip(items[0::2], items[1::2]))
    by_num = {n: k for k, n in order.items()}

    text = LETTER.read_text(errors="replace")
    fail = []

    # 1. bracketed numbers resolve to the named source
    cited = 0
    for m in re.finditer(r"\[(\d{1,2})\]", text):
        n = int(m.group(1))
        key = by_num.get(n)
        if key is None:
            fail.append(f"letter cites [{n}] but the bibliography has no entry {n}")
            continue
        cited += 1
        if key not in ATTRIB:
            continue  # pre-existing reference; this gate covers the added ones
        surname, tokens = ATTRIB[key]
        near = re.sub(r"\s+", " ",
                      text[max(0, m.start() - WINDOW_BEFORE):m.end() + WINDOW_AFTER])
        squash = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
        if not any(squash(tok) in squash(near) for tok in tokens):
            fail.append(f"[{n}] is {key} but no identifying token "
                        f"({', '.join(tokens)}) appears near it: ...{near[:120]}")
        entry = re.sub(r"\s+", " ", body[key])
        if squash(surname) not in squash(entry):
            fail.append(f"[{n}] -> {key} whose bibliography entry does not contain "
                        f'"{surname}": {entry[:90]}')

    # 2. the converse: a named source must carry its own number nearby
    anchored = 0
    for key, phrases in ANCHORS.items():
        if key not in order:
            fail.append(f"{key} is expected in the bibliography but is not cited there")
            continue
        want = order[key]
        for phrase in phrases:
            for m in re.finditer(re.escape(phrase), text, re.I):
                win = text[max(0, m.start() - ANCHOR_BEFORE):m.end() + ANCHOR_AFTER]
                nums = {int(x) for x in re.findall(r"\[(\d{1,2})\]", win)}
                if not nums:
                    continue  # named without citing: prose, not a citation error
                anchored += 1
                if want not in nums:
                    fail.append(f'"{phrase}" is {key} = [{want}], but the only number(s) near '
                                f"it are {sorted(nums)}: "
                                f"...{re.sub(chr(92)+'s+', ' ', win)[:120]}")

    # 3. every new reference is named in the letter
    flat = re.sub(r"[^a-z]", "", text.lower())
    for key in sorted(NEW):
        surname = ATTRIB[key][0]
        if re.sub(r"[^a-z]", "", surname.lower()) not in flat:
            fail.append(f"{key} is new in this revision but the letter never names "
                        f"{surname}, so the reviewers are not told why it was added")

    if fail:
        for f in fail:
            print("  " + f, file=sys.stderr)
        print(f"[letter-refs] FAILED: {len(fail)} problem(s)", file=sys.stderr)
        return 1
    print(f"[letter-refs] {cited} bracketed citation(s) in the response letter resolve to the "
          f"source the letter names and {anchored} named mention(s) carry the right number; "
          f"all {len(NEW)} references new in this revision are named in it "
          f"({len(order)} bibliography entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
