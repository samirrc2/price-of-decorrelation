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

    out, i, hl, plain = [], 0, 0, 0
    macro = r"\DIFadd{"
    # \DIFaddFL is what latexdiff emits inside a float. It used to render plain, so the
    # eleven additions in Table 5 -- the whole SR 26-2 column and the rewritten caption --
    # were invisible while the build still reported success. They are counted separately
    # now: a number that is never reported is a number nobody checks.
    n_float = s.count("\\DIFaddFL{")
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
        if any(tok in body for tok in UNSAFE_IN_RUN) or len(body) > 1200:
            out.append(r"\DIFplain{" + body + "}")     # keep the text, skip the highlight
            plain += 1
        else:
            out.append(macro + box_for_soul(body) + "}")
            hl += 1
        i = e + 1
    result = "".join(out)
    assert r"\sethlcolor{HLyellow}" in result, "colour setup missing"
    open(p, "w", encoding="utf-8").write(result)
    print(f"   {hl} runs highlighted inline, {plain} left plain (display math or long runs), "
          f"{n_float} inside floats (tables and captions)")


if __name__ == "__main__":
    main()
