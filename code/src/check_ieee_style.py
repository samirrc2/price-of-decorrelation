"""Gate: the two IEEE ordering rules the manuscript has to satisfy.

Both are stated requirements, not house style, and both are invisible to every other gate here:
the claims gates check that numbers are right, not that the front matter and the reference list
are ordered the way IEEE demands.

  Index Terms   IEEE Editorial Style Manual for Authors: "Index Terms appear in alphabetical
                order and as a final paragraph of the Abstract section. Capitalize the first
                word of the Index Terms list; lowercase the rest unless capitalized in text."
                This manuscript was submitted with them unordered -- the list began "Large
                language models, multi-agent systems, ensemble learning, model heterogeneity,
                ..." -- and nothing caught it, because nothing was looking.

  References    IEEE Reference Guide: references are numbered sequentially by order of mention
                in the text, one reference per number, and appear in numerical order of
                mention. Adding a reference that is cited early silently renumbers every later
                one, which is exactly the kind of change a reader diffing two versions sees and
                cannot explain.

The reference check needs the built bibliography, so it reports "not checkable" rather than
passing when paper/main.bbl is absent -- a bibliography that was never built cannot be in order.

  python code/src/check_ieee_style.py
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "paper" / "main.tex"
BBL = ROOT / "paper" / "main.bbl"

# Terms whose first letter is capitalised because the word is a proper noun or an acronym, so
# the "lowercase the rest" rule does not apply to them. Kept explicit: an entry here is a
# claim about the term, not a way to silence the check.
PROPER = set()


def index_terms(tex: str) -> list[str] | None:
    m = re.search(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", tex, re.S)
    if not m:
        return None
    body = " ".join(re.sub(r"%.*", "", m.group(1)).split()).rstrip(".")
    return [t.strip() for t in body.split(",") if t.strip()]


def main() -> int:
    if not TEX.exists():
        print("[ieee-style] paper/main.tex not published in this copy (capsule layout)")
        return 2
    tex = TEX.read_text()
    fails = []

    terms = index_terms(tex)
    if terms is None:
        fails.append("no \\begin{keywords} block: IEEE requires Index Terms on every article")
    else:
        want = sorted(terms, key=lambda t: t.lower())
        if terms != want:
            fails.append("Index Terms are not in alphabetical order, which IEEE requires.\n"
                         f"      found:  {', '.join(terms)}\n"
                         f"      sorted: {', '.join(want)}")
        if terms and not terms[0][:1].isupper():
            fails.append(f"the first Index Term should be capitalised: {terms[0]!r}")
        for t in terms[1:]:
            w = t.split()[0]
            if w[:1].isupper() and w not in PROPER and not w.isupper():
                fails.append(f"Index Term {t!r} is capitalised; IEEE lowercases all but the "
                             f"first unless the word is capitalised in text (add it to PROPER "
                             f"with a reason if it is)")
        print(f"[ieee-style] {len(terms)} Index Terms, alphabetical and capitalised per IEEE")

    # paper/main.bbl is a LaTeX build artifact and is gitignored, so a fresh clone does not have
    # it. Returning 2 there made reproduce.sh report INCOMPLETE on every clean checkout -- the
    # exit-2 contract correctly refusing to call an unrun check a pass. The reference work is
    # therefore split by what each context can actually see: the keys come from source and are
    # checked everywhere, the realised NUMBERING needs a built bibliography and is checked by
    # build_submission.sh, which always has one.
    body = re.sub(r"(?m)(?<!\\)%.*", "", tex)
    cited, seen = [], set()
    for m in re.finditer(r"\\cite[a-z]*\{([^}]*)\}", body):
        for k in (x.strip() for x in m.group(1).split(",")):
            if k and k not in seen:
                seen.add(k); cited.append(k)
    bib = ROOT / "paper" / "references.bib"
    if bib.exists():
        have = set(re.findall(r"@\w+\{([^,]+),", bib.read_text()))
        for k in cited:
            if k not in have:
                fails.append(f"{k} is cited in main.tex but has no entry in references.bib")
        print(f"[ieee-style] {len(cited)} cited keys, all present in references.bib")

    if not BBL.exists():
        print("[ieee-style] paper/main.bbl absent (build artifact, not in a clean checkout): "
              "reference NUMBERING is verified by build_submission.sh, which builds it")
        for f in fails:
            print(f"  {f}")
        return 1 if fails else 0

    body = re.sub(r"(?m)(?<!\\)%.*", "", tex)
    order, seen = [], set()
    for m in re.finditer(r"\\cite[a-z]*\{([^}]*)\}", body):
        for k in (x.strip() for x in m.group(1).split(",")):
            if k and k not in seen:
                seen.add(k)
                order.append(k)
    numbered = re.findall(r"\\bibitem\{([^}]*)\}", BBL.read_text())

    if len(numbered) != len(set(numbered)):
        fails.append("the bibliography assigns a number to the same key twice")
    for k in sorted(set(order) - set(numbered)):
        fails.append(f"{k} is cited in the text but has no entry in the bibliography")
    for k in sorted(set(numbered) - set(order)):
        fails.append(f"{k} appears in the bibliography but is never cited")
    if order and numbered and order != numbered:
        first = next((i for i, (a, b) in enumerate(zip(order, numbered), 1) if a != b), None)
        fails.append("references are not numbered in order of first mention, which IEEE "
                     "requires.\n"
                     f"      position {first}: the text cites {order[first-1]!r} there, "
                     f"the bibliography numbers {numbered[first-1]!r}")
    else:
        print(f"[ieee-style] {len(numbered)} references, numbered 1-{len(numbered)} in order of "
              f"first mention, none uncited, none missing")

    for f in fails:
        print(f"  {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
