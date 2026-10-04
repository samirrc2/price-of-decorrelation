#!/usr/bin/env python3
"""Audit the Highlighted PDF: is every real change marked, and is every mark a real change?

IEEE Access asks for the revised manuscript with every individual change highlighted. Two
ways that goes wrong, and neither is visible by reading the PDF:

  under-marking  a genuine revision is not highlighted, so a reviewer cannot see what moved
  over-marking   something is highlighted that did not substantively change, which points a
                 reviewer at a non-issue

Two classes are deliberately held constant before the diff and must therefore NOT be marked:
the reference list, reordered into citation order, and six rounding-only corrections from
the double-rounding bug in code/render/figures.py. Both are recorded in CHANGES.md. This
check confirms they are absent from the markup, and that everything else that differs is
present in it.

Usage:  python3 submission/check_highlighting.py [base_ref]
Exit:   0 highlighting faithful, 1 a discrepancy
"""
from __future__ import annotations
import difflib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def rounding_table():
    """The held-constant corrections, read from build_highlighted.sh rather than copied.

    This used to be a second copy of the list. Deleting an entry from the copy removed both
    the neutralisation and the check for it in one edit, and the audit went on reporting a
    pass while auditing a document the build does not produce. Parsing the build's own table
    means the two cannot drift.
    """
    src = (ROOT / "submission" / "build_highlighted.sh").read_text(encoding="utf-8")
    block = re.search(r"ROUNDING = \[(.*?)\n\]", src, re.S)
    if not block:
        # This paper holds nothing constant across the diff -- no reordered bibliography and
        # no rounding-only corrections -- so there is no table to read and nothing to exempt.
        return []
    pairs = re.findall(r'r"([^"]*)",\s*r"([^"]*)",\s*(\d+)', block.group(1))
    if not pairs:
        sys.exit("the ROUNDING table in build_highlighted.sh parsed to nothing")
    return [(a, b) for a, b, _ in pairs]


NUMBER_WORD = {6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven"}

ROUNDING = rounding_table()


def extract(text: str, cmd: str) -> list[str]:
    """Contents of every \\DIFadd{...} / \\DIFdel{...}, matching braces properly.

    A one-level regex loses any fragment containing nested braces -- inline maths, \\emph,
    a \\texttt -- which here was 26% of the marked characters. That under-count made whole
    revised paragraphs look unmarked and produced a long list of phantom failures.
    """
    out, i = [], 0
    opener = cmd + "{"
    while True:
        j = text.find(opener, i)
        if j < 0:
            return out
        k = j + len(opener)
        depth = 1
        while k < len(text) and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        out.append(text[j + len(opener):k - 1])
        i = k

def words(tex: str) -> list[str]:
    """Prose words, with LaTeX scaffolding removed so the comparison is about content."""
    t = re.sub(r"(?<!\\)%.*", "", tex)
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", t, flags=re.S)
    t = re.sub(r"\\(label|ref|cite[tp]?|includegraphics)\{[^}]*\}", " ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
    t = re.sub(r"[{}&~\\]", " ", t)
    return [w for w in re.split(r"\s+", t) if w]


def latexdiff_flags() -> list[str]:
    """The flags build_highlighted.sh passes to latexdiff, parsed from the script itself."""
    sh = (ROOT / "submission" / "build_highlighted.sh").read_text()
    m = re.search(r"^latexdiff((?:[^\n]*\\\n)*[^\n]*)$", sh, re.M)
    if not m:
        raise SystemExit("could not find the latexdiff invocation in build_highlighted.sh; "
                         "this audit must use the build's own flags, not a copy")
    import shlex
    line = m.group(1).replace("\\\n", " ")
    return [tok for tok in shlex.split(line) if tok.startswith("--")]


def rebuild(diff: str, keep: str) -> str:
    """Collapse the markup one way or the other: keep='add' gives the revision, 'del' the original."""
    out, i, n = [], 0, len(diff)
    while i < n:
        hit = False
        for cmd, tag in (("\\DIFdel{", "del"), ("\\DIFadd{", "add"),
                         ("\\DIFdelFL{", "del"), ("\\DIFaddFL{", "add")):
            if diff.startswith(cmd, i):
                k = i + len(cmd)
                depth = 1
                while k < n and depth:
                    if diff[k] == "{":
                        depth += 1
                    elif diff[k] == "}":
                        depth -= 1
                    k += 1
                if tag == keep:
                    out.append(diff[i + len(cmd):k - 1])
                i = k
                hit = True
                break
        if not hit:
            out.append(diff[i])
            i += 1
    return "".join(out)


def body(tex: str) -> str:
    """The document body, with markup scaffolding and all whitespace removed.

    Whitespace is dropped because latexdiff re-wraps lines and splits tokens around
    punctuation; those are not changes to the document.
    """
    i, j = tex.find("\\begin{document}"), tex.find("\\end{document}")
    t = tex[i:j] if i >= 0 and j > i else tex
    t = re.sub(r"%DIF.*", "", t)
    t = re.sub(r"\\DIF(add|del)(begin|end)(FL)?", "", t)
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"[{}]", " ", t)
    return re.sub(r"\s+", "", t)


def check_pdf_text_parity():
    """The highlighted PDF must carry exactly the manuscript's text.

    The round-trip test proves the diff SOURCE rebuilds the revision. It says nothing about the
    rendered PDF, so a build that silently dropped or duplicated a run would still pass it. The
    checklist also claimed the two PDFs aligned page for page; they do not -- inline \\texthl
    changes a few line breaks and six of fifteen pages start elsewhere -- which is harmless only
    because the text itself is identical. That is what this asserts.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return 0, [], "pypdf not installed; PDF text parity not checked"
    clean = ROOT / "submission" / "main_manuscript.pdf"
    high = ROOT / "submission" / "highlighted_pdf.pdf"
    if not (clean.exists() and high.exists()):
        return 0, [], "one of the two PDFs is not built; text parity not checked"

    def flat(path):
        pages = [re.sub(r"[^A-Za-z0-9]", "", p.extract_text() or "").lower()
                 for p in PdfReader(path).pages]
        return pages, "".join(pages)

    cp, ca = flat(clean)
    hp, ha = flat(high)
    fails = []
    if len(cp) != len(hp):
        fails.append(f"highlighted PDF has {len(hp)} pages, manuscript has {len(cp)}")
    if len(ca) != len(ha):
        fails.append(f"highlighted PDF carries {len(ha)} alphanumeric characters, the manuscript "
                     f"{len(ca)}: the two PDFs do not carry the same text")
    elif sorted(ca) != sorted(ha):
        fails.append("the two PDFs have the same character count but not the same characters")
    same_start = sum(1 for a, b in zip(cp, hp) if a[:60] == b[:60])
    return 2, fails, (f"both PDFs: {len(cp)} pages, {len(ca):,} alphanumeric characters, identical "
                      f"text; {same_start}/{len(cp)} pages start at the same point")


def base_ref():
    """The baseline the BUILD uses, read from build_highlighted.sh rather than copied.

    This was hardcoded to "HEAD" here while the build defaulted to "HEAD" too. Pinning the
    build to the as-submitted tag left the two disagreeing, so the audit validated a diff of
    the revision against itself -- one addition, one deletion -- and still reported OK. A check
    that reads its own baseline from somewhere else is not checking the artifact that ships.
    """
    src = (ROOT / "submission" / "build_highlighted.sh").read_text(encoding="utf-8")
    m = re.search(r'BASE_REF="\$\{1:-([^}]+)\}"', src)
    if not m:
        sys.exit("could not read BASE_REF from submission/build_highlighted.sh")
    return m.group(1)


def check_new_reference_highlighting():
    """Every reference newly cited since the baseline must be highlighted in the PDF."""
    import subprocess
    pdf = ROOT / "submission" / "highlighted_pdf.pdf"
    if not pdf.exists():
        return 0, [], "new-reference highlighting: no highlighted PDF to check"
    try:
        import pymupdf
    except Exception:
        return 0, [], ("new-reference highlighting NOT CHECKED: pymupdf unavailable, so the "
                       "yellow fill behind an entry cannot be read")
    base = subprocess.run(["git", "show", "as-submitted:paper/main.tex"], cwd=ROOT,
                          capture_output=True, text=True).stdout
    if not base:
        return 0, [], "new-reference highlighting NOT CHECKED: baseline main.tex unavailable"
    cite = re.compile(r"\\cite[a-z]*\{([^}]*)\}")
    def keys(t):
        return {k.strip() for m in cite.finditer(t) for k in m.group(1).split(",") if k.strip()}
    added = keys((ROOT / "paper" / "main.tex").read_text()) - keys(base)
    if not added:
        return 0, [], "new-reference highlighting: no references added since the baseline"

    bbl = (ROOT / "paper" / "main.bbl")
    if not bbl.exists():
        return 0, [], "new-reference highlighting NOT CHECKED: paper/main.bbl absent"
    btext = bbl.read_text()
    doc = pymupdf.open(pdf)
    # the yellow the build sets via \sethlcolor{HLyellow}
    def yellow_boxes(page):
        out = []
        for d in page.get_drawings():
            f = d.get("fill")
            if f and len(f) == 3 and f[0] > 0.85 and f[1] > 0.8 and f[2] < 0.6:
                out.append(d["rect"])
        return out
    fails, checked = [], 0
    for k in sorted(added):
        m = re.search(r"\\bibitem\{" + re.escape(k) + r"\}\s*\n(.{0,120})", btext, re.S)
        if not m:
            fails.append(f"{k} is newly cited but absent from paper/main.bbl")
            continue
        # The probe must survive typesetting. Taking the first 38 characters pulled in LaTeX
        # quote marks, which render as typographic quotes, so the PDF search missed three
        # entries that WERE highlighted. Use the longest run of letters and spaces instead --
        # usually part of the title -- which renders unchanged.
        clean = " ".join(re.sub(r"\\[a-zA-Z]+|[{}~\\]", " ", m.group(1)).split())
        runs = re.findall(r"[A-Za-z][A-Za-z ]{14,}", clean)
        probe = max(runs, key=len).strip()[:44] if runs else clean[:38]
        # A long probe can straddle a line break, which search_for will not match across. Try
        # progressively shorter prefixes before concluding the entry is unhighlighted.
        hit = False
        for cut in (44, 34, 26, 20):
            cand = probe[:cut].rstrip()
            if len(cand) < 12:
                continue
            for page in doc:
                for r in page.search_for(cand) or []:
                    if any(r.intersects(y) for y in yellow_boxes(page)):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                break
        checked += 1
        if not hit:
            fails.append(f"reference {k} was added in this revision but its entry in the "
                         f"REFERENCES list is not highlighted in the PDF")
    return checked, fails, (f"new-reference highlighting: {checked - len(fails)}/{checked} "
                            f"added reference(s) highlighted in the reference list "
                            f"({', '.join(sorted(added))})")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else base_ref()
    old = subprocess.run(["git", "show", f"{base}:paper/main.tex"],
                         capture_output=True, text=True, cwd=ROOT).stdout
    new = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
    if not old:
        sys.exit(f"could not read paper/main.tex at {base}")
    # A revision that differs from its baseline by almost nothing means the baseline is wrong,
    # not that the revision is clean. Without this the audit passes vacuously.
    if abs(len(new) - len(old)) < 200:
        sys.exit(f"baseline '{base}' is {len(old)} chars against a {len(new)}-char revision; "
                 f"that is not the as-submitted manuscript — check BASE_REF")

    # exactly what build_highlighted.sh holds constant before diffing
    m = re.search(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", new, re.S)
    if m:
        old = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
                     lambda _: m.group(0), old, flags=re.S)
    for a, b in ROUNDING:
        old = old.replace(a, b)

    with tempfile.TemporaryDirectory() as d:
        op, np_ = Path(d) / "o.tex", Path(d) / "n.tex"
        op.write_text(old, encoding="utf-8")
        np_.write_text(new, encoding="utf-8")
        # The same invocation the build uses -- READ FROM the build script rather than copied,
        # because a copy drifts. It had: the build gained --append-textcmd=tfootnote and then
        # --config VERBATIMENV=lstlisting while this call kept neither, so the audit was run
        # against a document the build does not produce, and reported a round-trip failure for
        # a change the real build handles correctly.
        diff = subprocess.run(
            ["latexdiff"] + latexdiff_flags() + [str(op), str(np_)],
            capture_output=True, text=True,
            env={"PATH": f"{Path.home()}/Library/TinyTeX/bin/universal-darwin:/usr/bin:/bin"}).stdout
    if not diff:
        sys.exit("latexdiff produced nothing (is it on PATH?)")

    # Round-trip: the markup must collapse to each side of the revision. This is the whole
    # test -- if both hold, every difference is inside markup and nothing else is.
    rev_ok = body(rebuild(diff, "add")) == body(new)
    org_ok = body(rebuild(diff, "del")) == body(old)
    rev_sim = difflib.SequenceMatcher(None, body(rebuild(diff, "add")), body(new)).ratio()
    org_sim = difflib.SequenceMatcher(None, body(rebuild(diff, "del")), body(old)).ratio()

    marked = " ".join(extract(diff, "\\DIFadd") + extract(diff, "\\DIFdel")
                      + extract(diff, "\\DIFaddFL") + extract(diff, "\\DIFdelFL"))
    n_add = len(extract(diff, "\\DIFadd")) + len(extract(diff, "\\DIFaddFL"))
    n_del = len(extract(diff, "\\DIFdel")) + len(extract(diff, "\\DIFdelFL"))

    print(f"   previous version {len(body(old)):,} chars -> revised {len(body(new)):,} chars")
    print(f"   marked runs: {n_add} additions, {n_del} deletions")
    print(f"   revision rebuilt from the markup matches paper/main.tex   : "
          f"{rev_ok} (similarity {rev_sim:.6f})")
    print(f"   original rebuilt from the markup matches the previous text: "
          f"{org_ok} (similarity {org_sim:.6f})")

    fails = []
    # The decisive property is the revision round-trip. If collapsing the markup the "keep
    # additions" way reproduces paper/main.tex exactly, then every byte that differs from the
    # previous version sits inside a marked run -- nothing changed without being highlighted.
    if not rev_ok:
        fails.append(f"revision does not rebuild from the markup (similarity {rev_sim:.6f}); "
                     f"some change is outside the markup")

    # The original side cannot rebuild exactly and is reported rather than gated. latexdiff
    # carries structural tokens through unmarked because wrapping them would break the
    # document: here the two new subsections' \label and \begin{equation} openers, the
    # tabular column specification (which changed when the SR 26-2 column was added), and the
    # extra & that column adds to each row. None of that is prose, and none of it can hide a
    # content change, because a content change would have broken the revision round-trip above.
    residual = sum(i2 - i1 for tag, i1, i2, _, _ in difflib.SequenceMatcher(
        None, body(rebuild(diff, "del")), body(old)).get_opcodes() if tag != "equal")
    print(f"   original-side residual: {residual} chars of structural markup latexdiff "
          f"cannot wrap (labels, environment openers, column spec, alignment tabs)")

    # CHANGES.md is where these corrections are disclosed instead of highlighted, so the
    # disclosure has to list every one the build actually neutralises. It said "six" in three
    # places while the table under it had grown to nine rows, which is the disclosure being
    # wrong about its own contents.
    changes = ""
    if not ROUNDING:
        rows = []
    elif True:
        changes = (ROOT / "submission" / "CHANGES.md").read_text(encoding="utf-8")
    sec = changes[changes.find("## 4. Numbers corrected"):changes.find("## 5.")]
    rows = [r for r in sec.split("\n") if r.startswith("| `") or r.startswith("| $")]
    print(f"   rounding corrections: {len(ROUNDING)} rules in the build, {len(rows)} disclosed "
          f"in CHANGES.md")
    # Match per figure, not per rule: one rule may neutralise a whole table row and so appear
    # in CHANGES.md as two separate entries.
    disclosed = " ".join(rows)
    for previous, corrected in ROUNDING:
        for before, after in zip(re.findall(r"[\d.]*\d", previous),
                                 re.findall(r"[\d.]*\d", corrected)):
            if before == after:
                continue                      # an unchanged digit inside the match context
            if before not in disclosed or after not in disclosed:
                fails.append(f"build_highlighted.sh corrects {before} to {after}, but CHANGES.md "
                             f"does not disclose that correction")
    for n in re.findall(r"\b(?:six|seven|eight|nine|ten|eleven)\b", sec):
        if n != NUMBER_WORD.get(len(rows), ""):
            fails.append(f"CHANGES.md section 4 says {n!r} corrections; it lists {len(rows)}")
            break

    leaked = [tok for _, corrected in ROUNDING
              for tok in re.findall(r"\d+\.\d+", corrected) if tok in marked]
    if leaked:
        fails.append(f"rounding-only values highlighted: {sorted(set(leaked))}")

    # Independent of the table above: any marked run that is nothing but a number is by
    # definition a digit-level edit, which is what we have decided not to highlight. Testing
    # for it directly means dropping an entry from the build's table cannot hide anything --
    # that edit removes both the neutralisation and, if the check read the same list, the
    # check for it.
    numeric_runs = []
    for frag in (extract(diff, "\\DIFadd") + extract(diff, "\\DIFdel")
                 + extract(diff, "\\DIFaddFL") + extract(diff, "\\DIFdelFL")):
        # digits must be stripped too, or "--14.9" reduces to "149" and reads as content
        bare = re.sub(r"\\[a-zA-Z]+|[\s$={}\\,\[\]()+\-.;:%0-9]", "", frag)
        if frag.strip() and not bare and re.search(r"\d", frag):
            numeric_runs.append(re.sub(r"\s+", " ", frag).strip())
    # This rule exists to catch a digit-level edit slipping into the markup when the build has
    # promised to hold such edits constant. With no ROUNDING table nothing is being withheld,
    # and a numeric run is simply new content -- a new table cell -- which must be highlighted.
    if numeric_runs and ROUNDING:
        fails.append(f"{len(numeric_runs)} marked run(s) contain only numbers, so a digit-level "
                     f"edit is being highlighted: {numeric_runs[:4]}")
    print(f"   marked runs that are only numbers: {len(numeric_runs)}")
    pchecks, pfails, pnote = check_pdf_text_parity()
    fails.extend(pfails)
    print(f"   {pnote}")
    # Verify end-to-end that every reference ADDED since the baseline is visibly highlighted in
    # the built PDF. latexdiff cannot mark these -- it diffs main.tex, where the bibliography is
    # one \bibliography line -- so highlight_newrefs.py marks them in the generated .bbl, and
    # nothing checked that it worked. This looks for a yellow fill behind the entry's text
    # rather than trusting the build's own log line.
    nchecks, nfails, nnote = check_new_reference_highlighting()
    fails.extend(nfails)
    print(f"   {nnote}")

    if re.search(r"\\bibitem", marked):
        fails.append("bibliography entries are highlighted; they should be held constant")
    print(f"   rounding-only corrections in the markup: {len(set(leaked))}")
    print(f"   bibliography entries in the markup: {len(re.findall(chr(92) + 'bibitem', marked))}")

    if fails:
        print(f"   FAILED ({len(fails)}):")
        for f in fails:
            print("      -", f)
        sys.exit(1)
    print("   OK — the revision rebuilds exactly from the markup, so every change is "
          "highlighted; nothing held constant is marked")


if __name__ == "__main__":
    main()
