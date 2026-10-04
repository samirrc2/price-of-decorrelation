#!/usr/bin/env python3
"""Rewrite latexdiff output into the yellow-highlighted form IEEE Access asks for.

The checklist wants the revised manuscript with changes highlighted, and an Associate Editor
needs it to correspond to the clean manuscript page for page. That rules out block-level
highlighting: wrapping a paragraph in \\colorbox{\\parbox{...}} makes it an unbreakable box, so
columns break in the wrong places and the article gains a page. Highlighting is therefore
inline, with soul's \\texthl, which leaves line breaking untouched.

soul is fragile in two specific ways, both handled here rather than worked around:

  * it cannot cross math, so every $...$ inside a highlighted run is wrapped in \\mbox
  * it breaks on commands that take arguments, so \\ref, \\cite, \\texttt and the rest are
    wrapped in \\mbox too, which soul treats as an opaque atom

A run that still cannot be highlighted safely -- one containing a display equation, an
environment, or a tabular row -- is emitted unhighlighted rather than risking a broken build or
a shifted layout. Those are reported in the build output and catalogued in
submission/CHANGES.md, so nothing goes unreported.

latexdiff's own preamble is discarded: its markup strikes deletions through, and it requires
settobox.sty, which is neither installed here nor in the package repository.

Usage: python3 highlight_markup.py <diff.tex>
"""
import re
import sys

FRAGILE = ("ref", "cite", "citep", "citet", "texttt", "emph", "textbf", "textit", "url",
           "textsuperscript", "footnote", "mathrm", "text")

# markers whose presence means the run is not safe for an inline highlight
UNSAFE_IN_RUN = (r"\begin{", r"\end{", r"\[", r"$$", r"\\", "&", r"\item",
                 r"\section", r"\subsection", r"\caption", r"\label")

PREAMBLE = "\n".join([
    r"\usepackage{soul}",
    r"\usepackage{xcolor}",
    r"\definecolor{HLyellow}{rgb}{1,0.94,0.35}",
    r"\sethlcolor{HLyellow}",
    r"\newcommand{\DIFadd}[1]{\texthl{#1}}",
    r"\newcommand{\DIFplain}[1]{#1}",
    r"\newcommand{\DIFdel}[1]{}",
    r"\newcommand{\DIFaddbegin}{}",
    r"\newcommand{\DIFaddend}{}",
    r"\newcommand{\DIFdelbegin}{}",
    r"\newcommand{\DIFdelend}{}",
    r"\newcommand{\DIFaddFL}[1]{\texthl{#1}}",
    r"\newcommand{\DIFdelFL}[1]{}",
    r"\newcommand{\DIFaddbeginFL}{}",
    r"\newcommand{\DIFaddendFL}{}",
    r"\newcommand{\DIFdelbeginFL}{}",
    r"\newcommand{\DIFdelendFL}{}",
    "",
])


def box_for_soul(text):
    """Make one run safe for \\texthl by boxing math and argument-taking commands."""
    text = re.sub(r"(?<!\\)\$([^$]+)\$", lambda m: r"\mbox{$" + m.group(1) + r"$}", text)
    for cmd in FRAGILE:
        text = re.sub(r"(?<!mbox\{)\\" + cmd + r"(\{[^{}]*\})",
                      lambda m, c=cmd: r"\mbox{\\" + c + m.group(1) + "}", text)
    return text.replace(r"\\mbox", r"\mbox").replace(r"\mbox{\\", r"\mbox{\\"[:-1])


def arg_span(s, start):
    """End index of the brace group opening at s[start] == '{'."""
    depth, i = 0, start
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def main():
    p = sys.argv[1]
    s = open(p, encoding="utf-8").read()
    s = re.sub(r"%DIF PREAMBLE EXTENSION ADDED BY LATEXDIFF.*?"
               r"%DIF END PREAMBLE EXTENSION ADDED BY LATEXDIFF", "", s, flags=re.S)
    before = s
    s = s.replace(r"\begin{document}", PREAMBLE + r"\begin{document}", 1)
    assert s != before, "could not inject the preamble"

    # Both macros map to \texthl in the preamble, so BOTH need their bodies made soul-safe.
    # Only \DIFadd{ was rewritten: \DIFaddFL{ runs were counted and left untouched, so a
    # \ref, \cite or $...$ added inside a float went to soul unprotected. soul does not fail
    # on these, it silently drops them -- a \ref{tab:nondet} added to a figure caption rendered
    # as "Table " with the number missing, and the PDF text-parity check caught it as a
    # one-character difference against the manuscript. Counting a run is not the same as
    # processing it.
    s, n_listing = mark_changed_listings(s)
    n_float = s.count("\\DIFaddFL{")
    hl, plain = 0, 0
    for macro in (r"\DIFadd{", r"\DIFaddFL{"):
        s, a, b = _rewrite_runs(s, macro)
        hl += a
        plain += b
    result = s
    assert r"\sethlcolor{HLyellow}" in result, "colour setup missing"
    open(p, "w", encoding="utf-8").write(result)
    print(f"   {hl} runs highlighted inline, {plain} left plain (display math or long runs), "
          f"{n_float} inside floats (tables and captions), "
          f"{n_listing} changed code listing(s) given a highlighted background")


def mark_changed_listings(s):
    """Give a listing that latexdiff replaced a highlighted background.

    soul cannot highlight verbatim, so a changed code listing would otherwise render in plain
    black while every word around it is marked -- the reader sees an unmarked block and assumes
    it did not change. latexdiff wraps a replaced listing in \\DIFaddbeginFL ... \\DIFaddendFL,
    which is the signal used here. Listings it did not touch, such as the unchanged JSON schema,
    keep their default background.
    """
    out, n = [], 0
    i = 0
    while True:
        j = s.find("\\DIFaddbeginFL", i)
        if j < 0:
            out.append(s[i:]); break
        k = s.find("\\DIFaddendFL", j)
        if k < 0:
            out.append(s[i:]); break
        block = s[j:k]
        if "\\begin{lstlisting}" in block:
            block = block.replace("\\begin{lstlisting}",
                                  "\\begin{lstlisting}[backgroundcolor=\\color{HLyellow}]", 1)
            n += 1
        out.append(s[i:j]); out.append(block)
        i = k
    return "".join(out), n


def _rewrite_runs(s, macro):
    out, i, hl, plain = [], 0, 0, 0
    # \DIFaddFL is what latexdiff emits inside a float. It used to render plain, so the
    # eleven additions in Table 5 -- the whole SR 26-2 column and the rewritten caption --
    # were invisible while the build still reported success. They are counted separately
    # now: a number that is never reported is a number nobody checks.
    while True:
        j = s.find(macro, i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        e = arg_span(s, j + len(macro) - 1)
        if e < 0:
            out.append(s[j:])
            break
        body = s[j + len(macro):e]
        # Strip trailing whitespace inside the run. latexdiff ends most runs with the source
        # line break, so the body finishes with a newline, which TeX reads as a space -- and
        # soul highlights that space like any other character. When the run's last line is
        # already full to the margin, the highlighted trailing space does not fit and is set on
        # a line of its own: a blank highlighted line, 11.9pt of white, between the run and
        # whatever follows. In the five-concepts list of Section V-C it opened a visible gap
        # between items 4 and 5 that the clean manuscript does not have. Stripping it closes
        # the gap and changes nothing else, since the space was never part of the text.
        body = body.rstrip()
        if any(tok in body for tok in UNSAFE_IN_RUN) or len(body) > 1200:
            out.append(r"\DIFplain{" + body + "}")     # keep the text, skip the highlight
            plain += 1
        else:
            out.append(macro + box_for_soul(body) + "}")
            hl += 1
        i = e + 1
    return "".join(out), hl, plain


if __name__ == "__main__":
    main()
