#!/usr/bin/env python3
"""Paint the revision's changes onto the manuscript PDF itself.

Why this exists. The previous build compiled a SECOND document in which every changed run was
wrapped in soul's \\texthl. soul cannot hyphenate inside a highlight, so highlighted paragraphs
broke their lines differently -- "we eval-/uate" became "we/evaluate" -- and four of fourteen
pages started one line out from the manuscript. A reviewer holding the two PDFs side by side
could not read across them. Compiling with zero-width \\pdfsavepos markers instead fails the same
way: a whatsit suppresses hyphenation of the word after it, and that build came out a page longer.

So nothing is compiled twice. main_manuscript.pdf is built once, and this script draws the
highlights onto that exact file. Line breaks, page breaks and every coordinate are the
manuscript's own, because it IS the manuscript.

What it highlights. latexdiff still produces the markup, so the definition of "changed" is
unchanged: every \\DIFadd and \\DIFaddFL run, plus any \\bibitem new in this revision.

How it finds them, in two stages. First the whole diff is reduced to the token sequence of the
NEW document, each token carrying a changed/unchanged flag, and that sequence is aligned against
the PDF's own word stream with difflib. One global alignment places about 95% of the changed
tokens and is immune to the problem that defeats per-run searching: a short run such as a single
word "statistically" or a table cell "0.3363" is not unique on its own, but it is unambiguous in
its position. Second, any run that the alignment placed nowhere -- in practice the contents of
floats, whose source order differs from their printed order -- is located by its own head and
tail. A run still unplaced after both stages fails the build.

Where it refuses. A run that cannot be located is a change that would ship unmarked, which is
worse than a reflowed page, so an unlocated run FAILS the build and is named. The one legitimate
exception is declared in UNLOCATABLE with the reason.

Matching notes, each earned:
  * hyphenation -- "capability-" at a line end is joined to "tier" on the next, across block
    boundaries, because pdflatex puts a caption and its paragraph in different blocks;
  * inline math, \\ref, \\cite and \\url become wildcards: the rendered form ("III-D", "0.336")
    is not recoverable from the source, so the matcher accepts one to six words there;
  * 54{,}000 is normalised to 54000 to match the rendered "54,000", and a run boundary that
    falls inside such a number is matched by prefix or suffix on the first and last token.
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

WILD = "\x00"
YELLOW = (1.0, 0.94, 0.30)

# Runs that are genuinely not in the PDF's text layer, with the reason. Anything else that fails
# to match stops the build.
UNLOCATABLE: dict[str, str] = {}


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9%]", "", w.lower())


def run_bodies(tex: str, macro: str) -> list[str]:
    out, i = [], 0
    while True:
        j = tex.find(macro, i)
        if j < 0:
            return out
        k = j + len(macro)
        depth, m = 1, k
        while m < len(tex) and depth:
            if tex[m] == "{":
                depth += 1
            elif tex[m] == "}":
                depth -= 1
            m += 1
        out.append(tex[k:m - 1])
        i = m


def tokens(tex: str) -> list[str]:
    t = re.sub(r"(\d)\{,\}(\d)", r"\1\2", tex)
    t = re.sub(r"\\(?:begin|end)\{[^{}]*\}", " ", t)   # environment names are not printed text
    t = re.sub(r"\\label\{[^{}]*\}", " ", t)
    t = re.sub(r"\\(?:ref|eqref|cite[a-z]*|url|doi)\{[^{}]*\}", f" {WILD} ", t)
    t = re.sub(r"\\mbox\{", "{", t)
    t = re.sub(r"\\(?:emph|textit|textbf|texttt|text|mathrm|mathit)\{", "{", t)
    t = re.sub(r"\$[^$]*\$", f" {WILD} ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
    t = (t.replace("{", " ").replace("}", " ").replace("~", " ")
          .replace(r"\%", "%").replace(r"\&", "&").replace(r"\_", "_"))
    out = []
    for x in t.split():
        if WILD in x:
            out.append(WILD)
            continue
        n = norm(x)
        if n:
            out.append(n)
    # Collapse runs of wildcards but KEEP them. A \DIFadd run that is pure math -- a confidence
    # interval in a table cell -- otherwise contributes no token at all, and the context around
    # its neighbours then has a hole where the printed table has two numbers, so the surrounding
    # cells of that row can never be matched.
    collapsed = []
    for t in out:
        if t == WILD and collapsed and collapsed[-1] == WILD:
            continue
        collapsed.append(t)
    return collapsed


def word_stream(doc):
    """Every word in reading order, hyphenation repaired, with the rects that drew it."""
    stream = []
    for pno, page in enumerate(doc):
        ws = sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7]))
        i = 0
        while i < len(ws):
            w = ws[i]
            txt, rects = w[4], [(pno, w[:4])]
            # a line-final hyphen continues into the next word, which pdflatex may place in
            # another block (a caption and its paragraph are separate blocks)
            if txt.endswith("-") and i + 1 < len(ws) and ws[i + 1][1] > w[1] + 2:
                txt = txt[:-1] + ws[i + 1][4]
                rects.append((pno, ws[i + 1][:4]))
                i += 1
            n = norm(txt)
            if n:
                stream.append((n, rects))
            i += 1
    return stream


def match_at(words, start, seq):
    i, j = start, 0
    while j < len(seq):
        if i >= len(words):
            return None
        tok, last = seq[j], j == len(seq) - 1
        if tok == WILD:
            if last:
                return i + 1
            nxt = seq[j + 1]
            for take in range(1, 7):
                if i + take < len(words) and (words[i + take] == nxt
                                              or words[i + take].startswith(nxt)):
                    i += take
                    j += 1
                    break
            else:
                return None
            continue
        w = words[i]
        if w == tok or (j == 0 and w.endswith(tok)) or (last and w.startswith(tok)):
            i += 1
            j += 1
            continue
        # A source token can span two PDF words. "capability-tier" is one word in main.tex and
        # extracts as "capability-" + "tier" when the line breaks at its hyphen, and the repair
        # in word_stream only fires when the continuation is on the next line -- which it is not
        # when the break falls at a real hyphen mid-column. Accept the concatenation.
        if i + 1 < len(words) and words[i] + words[i + 1] == tok:
            i += 2
            j += 1
            continue
        return None
    return i


def locate(words, seq):
    for s0 in range(len(words)):
        t = seq[0]
        if t != WILD and not (words[s0] == t or words[s0].endswith(t)):
            continue
        e = match_at(words, s0, seq)
        if e:
            return s0, e
    return None


def new_bibitems(bbl: Path, old_tex: str, new_tex: str) -> list[str]:
    """The reference-list text of every \\bibitem cited in the revision but not before."""
    if not bbl.exists():
        return []
    # Split the comma-separated groups BEFORE differencing. Differencing the raw groups treats
    # "\cite{a,b}" as one key, so a group that merely gained a member looked entirely new and an
    # already-cited reference was reported as added.
    def cited(s):
        return {k.strip() for grp in re.findall(r"\\cite[a-z]*\{([^}]*)\}", s)
                for k in grp.split(",") if k.strip()}
    added = cited(new_tex) - cited(old_tex)
    out = []
    entries = re.split(r"\\bibitem", bbl.read_text(errors="replace"))
    for e in entries[1:]:
        m = re.match(r"(?:\[[^\]]*\])?\{([^}]*)\}(.*)", e, re.S)
        if m and m.group(1) in added:
            out.append(m.group(2))
    return out


NEW_DOC_MACROS = (r"\DIFadd{", r"\DIFaddFL{")
DEL_MACROS = (r"\DIFdel{", r"\DIFdelFL{")


def _skip_arg(s: str, k: int) -> int:
    depth = 1
    while k < len(s) and depth:
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
        k += 1
    return k


def flagged_segments(src: str):
    """The NEW document as (text, changed) segments: deletions dropped, additions flagged."""
    segs, i = [], 0
    while i < len(src):
        if any(src.startswith(m, i) for m in DEL_MACROS):
            m = next(m for m in DEL_MACROS if src.startswith(m, i))
            i = _skip_arg(src, i + len(m))
            continue
        if any(src.startswith(m, i) for m in NEW_DOC_MACROS):
            m = next(m for m in NEW_DOC_MACROS if src.startswith(m, i))
            j = _skip_arg(src, i + len(m))
            segs.append((src[i + len(m):j - 1], True))
            i = j
            continue
        j = i
        while j < len(src) and not any(src.startswith(m, j) for m in DEL_MACROS + NEW_DOC_MACROS):
            j += 1
        segs.append((src[i:j], False))
        i = j
    return segs


def paint(doc, stream, indices, pymupdf):
    """One rectangle per (page, line) the given word indices touch."""
    by_line = {}
    for idx in indices:
        for pno, (x0, y0, x1, y1) in stream[idx][1]:
            key = (pno, round(y0, 1))
            b = by_line.get(key)
            by_line[key] = ((min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1))
                            if b else (x0, y0, x1, y1))
    for (pno, _), (x0, y0, x1, y1) in by_line.items():
        doc[pno].draw_rect(pymupdf.Rect(x0 - 0.6, y0 - 0.5, x1 + 0.6, y1 + 0.5),
                           color=None, fill=YELLOW, overlay=False)
    return len(by_line)


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    try:
        import pymupdf
    except ImportError:
        print("highlight_overlay: pymupdf is required", file=sys.stderr)
        return 2
    clean, diff_tex, out_pdf = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    old_tex = Path(sys.argv[4]).read_text(errors="replace") if len(sys.argv) > 4 else ""
    new_tex = Path(sys.argv[5]).read_text(errors="replace") if len(sys.argv) > 5 else ""
    bbl = Path(sys.argv[6]) if len(sys.argv) > 6 else None

    src = diff_tex.read_text(errors="replace")
    doc = pymupdf.open(clean)
    stream = word_stream(doc)
    words = [w for w, _ in stream]

    # ---- stage 1: global alignment of the new document against the PDF
    segs = flagged_segments(src)
    toks = [(t, flag) for body, flag in segs for t in tokens(body)]
    src_words = [t for t, _ in toks]
    changed_src = {i for i, (_, f) in enumerate(toks) if f}
    sm = difflib.SequenceMatcher(a=src_words, b=words, autojunk=False)
    placed = set()
    src_to_pdf = {}
    # Only a matching block of three or more consecutive tokens is evidence. difflib will match
    # a lone "at" or "to" anywhere in the document, and near the end -- at the biographies and
    # the reference list, where the source order and the printed order genuinely diverge -- such
    # an isolated match put a changed word on the author's name. Runs left unplaced by this
    # restriction are picked up by the per-run search below, which needs real context.
    MIN_BLOCK = 3
    for blk in sm.get_matching_blocks():
        if blk.size < MIN_BLOCK:
            continue
        for k in range(blk.size):
            src_to_pdf[blk.a + k] = blk.b + k
    for i in sorted(changed_src):
        if i in src_to_pdf:
            placed.add(src_to_pdf[i])
    stage1 = len(placed)

    # ---- stage 2: per-run fallback for anything the alignment placed nowhere
    # Runs are taken from the SAME segment list the alignment used, so run i and span i are the
    # same object by construction. Collecting them separately -- all \DIFadd then all \DIFaddFL
    # -- put them in a different order from the spans and silently mismatched the two.
    runs, spans, cur = [], [], 0
    for body, flag in segs:
        n = len(tokens(body))
        if flag:
            runs.append(("changed run", body))
            spans.append((cur, cur + n))
        cur += n
    refs = new_bibitems(bbl, old_tex, new_tex) if bbl else []
    runs += [("bibitem", b) for b in refs]
    fails, recovered = [], 0
    for ri, (kind, body) in enumerate(runs):
        seq = tokens(body)
        while seq and seq[0] == WILD:
            seq.pop(0)
        while seq and seq[-1] == WILD:
            seq.pop()
        if not seq or body.strip() in ("#1", "#2", "#3"):
            continue        # a macro parameter in a redefined command, not printed text
        if ri < len(spans):
            a, b = spans[ri]
            if any(i in src_to_pdf for i in range(a, b)):
                # A one-word run is accepted from the alignment only if its surroundings agree.
                # "Two-way" in Table 5 was being placed on the word "two-way" in the prose, so
                # that table cell shipped unmarked while the rest of its row was highlighted.
                if b - a == 1:
                    at = next(src_to_pdf[i] for i in range(a, b) if i in src_to_pdf)
                    before = [t for t in src_words[max(0, a - 2):a] if t != WILD]
                    after = [t for t in src_words[b:b + 2] if t != WILD]
                    ok = all(t in words[max(0, at - 4):at] for t in before) and \
                         all(t in words[at + 1:at + 5] for t in after)
                    if not ok:
                        placed.discard(at)
                    else:
                        continue
                else:
                    continue                   # stage 1 already placed it
        probe = seq[:8] if len(seq) >= 2 else seq
        hit = locate(words, probe) if len(probe) >= 2 else None
        if hit is None and len(seq) >= 2:
            hit = locate(words, seq[:4])
        if hit is None and ri < len(spans):
            # A one-word change -- "statistically", a table cell "same" -- is not unique on its
            # own but is unambiguous in context. Rebuild the probe from the surrounding
            # UNCHANGED tokens of the new document and keep only the run's own words.
            a, b = spans[ri]
            # Symmetric context fails where the run sits at a float boundary: the words after it
            # belong to a caption that the PDF prints elsewhere. One-sided windows are tried too.
            windows = [(p, p) for p in (4, 7, 10, 3, 2)] + [(8, 0), (0, 8), (12, 0), (0, 12)]
            for pad_l, pad_r in windows:
                lo, hi = max(0, a - pad_l), min(len(src_words), b + pad_r)
                ctx = [t for t in src_words[lo:hi]]
                if len(ctx) < 2:
                    continue
                ch = locate(words, ctx)
                if ch:
                    s0c = ch[0] + (a - lo)
                    placed.update(range(s0c, min(len(words), s0c + max(1, b - a))))
                    recovered += 1
                    break
            else:
                ch = None
            if ch:
                continue
        if hit is None:
            fails.append(f"{kind}: could not locate: {' '.join(seq[:12])}")
            continue
        s0 = hit[0]
        end = None
        for probe in (seq[-8:], seq[-5:], seq[-3:]):
            probe = [t for t in probe if t != WILD] or probe
            if len(probe) < 2:
                continue
            for s1 in range(s0, min(len(words), s0 + len(seq) + 40)):
                e1 = match_at(words, s1, probe)
                if e1:
                    end = e1
                    break
            if end:
                break
        end = end if end and end > s0 else min(len(words), s0 + len(seq))
        placed.update(range(s0, end))
        recovered += 1

    if fails:
        for f in fails:
            print("  " + f, file=sys.stderr)
        print(f"highlight_overlay: {len(fails)} change(s) could not be located and would ship "
              f"unmarked", file=sys.stderr)
        return 1

    boxes = paint(doc, stream, sorted(placed), pymupdf)
    doc.save(out_pdf, garbage=3, deflate=True)
    print(f"   {len(placed)} changed word(s) highlighted on the manuscript's own pages in "
          f"{boxes} runs: {stage1} placed by whole-document alignment, {recovered} run(s) "
          f"recovered individually ({len(refs)} new reference(s)); {len(doc)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
