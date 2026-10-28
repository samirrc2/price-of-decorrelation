#!/usr/bin/env python3
"""Build submission/main_manuscript.docx from paper/main.tex so the Word file matches the PDF.

Three things pandoc does not get right on its own, each found by comparing the DOCX
against the PDF rather than by reading the output:

  * Citations. Without an IEEE CSL, citeproc emits Chicago author-date -- "(Kim et al.
    2025)" where the PDF reads "[3]" -- and an alphabetical reference list. paper/ieee.csl
    restores numeric citations in order of first appearance, matching IEEEtran.
  * The reference section has no heading at all unless one is named explicitly.
  * Author photographs. The portrait is the optional argument of \\begin{IEEEbiography}[..],
    and pandoc discards it, so both biographies arrived with their text but no picture --
    which the IEEE Access final-files checklist explicitly requires.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEX  = ROOT / "paper" / "main.tex"
OUT  = ROOT / "submission" / "main_manuscript.docx"


def resolve_refs(src: str) -> str:
    """Substitute \\ref with the numbers IEEEtran assigned, taken from paper/main.aux.

    pandoc renumbers sections as 1, 2, 3 with decimal subsections, so the Word file read
    "Section 5.10" where the PDF reads "Section V-J". Taking the labels from the aux file of
    the PDF build means the two documents cannot disagree about a section or table number.
    """
    aux = TEX.with_suffix(".aux")
    if not aux.exists():
        return src
    labels = dict(re.findall(r"\\newlabel\{([^}]+)\}\{\{(?:\\mbox\s*\{)?([^}]+)\}",
                             aux.read_text(encoding="utf-8")))
    return re.sub(r"\\ref\{([^}]+)\}", lambda m: labels.get(m.group(1), m.group(1)), src)


def preprocess(src: str) -> str:
    src = resolve_refs(src)

    # Figure and table captions. pandoc emits the caption text with no "FIGURE n." label,
    # so the Word file carried five unlabelled captions while the prose referred to "Fig. 3".
    # The numbers come from paper/main.aux, the PDF build's own label table.
    aux = TEX.with_suffix(".aux")
    if aux.exists():
        nums = dict(re.findall(r"\\newlabel\{((?:fig|tab):[^}]+)\}\{\{(\d+)\}",
                               aux.read_text(encoding="utf-8")))
        def label(m):
            env, inner = m.group(1), m.group(2)
            lab = re.search(r"\\label\{((?:fig|tab):[^}]+)\}", inner)
            if not lab or lab.group(1) not in nums:
                return m.group(0)
            word = "FIGURE" if lab.group(1).startswith("fig:") else "TABLE"
            n = nums[lab.group(1)]
            return re.sub(r"\\caption\{", f"\\\\caption{{{word} {n}. ", m.group(0), count=1)
        src = re.sub(r"\\begin\{(figure|table)\*?\}(.*?)\\end\{\1\*?\}",
                     label, src, flags=re.S)

    # IEEE Access front-matter macros. pandoc knows none of them, so it dropped the
    # affiliation, both ORCIDs, the funding statement, the submission date and the
    # corresponding-author line outright: the Word file carried only title and byline,
    # while checklist item 4 asks the authors to confirm exactly that information.
    # booktabs partial rules. pandoc does not implement \cmidrule and emitted its arguments
    # as literal text, so a table header in the Word file read "agreement marginals 2-4(lr)5-7".
    src = re.sub(r"\\cmidrule(\(lr\))?\{[\d-]+\}", "", src)
    src = re.sub(r"\\authorrefmark\{\d+\}", "", src)
    # \PARstart{M}{ulti-agent} is the IEEE drop cap. pandoc does not know it and dropped the
    # whole macro, so the Word file's Introduction began "large language model systems..." --
    # the first word of the paper was simply absent.
    src = re.sub(r"\\PARstart\{(.)\}\{([^}]*)\}", r"\1\2", src)
    src = re.sub(r"\\address\[\d+\]\{(.*?)\}\s*\n", r"\n\\medskip\\noindent \1\n", src, flags=re.S)
    src = re.sub(r"\\corresp\{(.*?)\}\s*\n",       r"\n\\noindent \1\n", src, flags=re.S)
    src = re.sub(r"\\tfootnote\{(.*?)\}\s*\n",     r"\n\\noindent \1\n", src, flags=re.S)
    # Lift the portrait out of the optional argument and emit it as its own paragraph,
    # followed by the name as a heading and then the biography text.
    def bio(m):
        photo = re.search(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", m.group(1))
        img = f"\n\\includegraphics[width=1in]{{{photo.group(1)}}}\n" if photo else ""
        return f"\n\\subsection*{{{m.group(2)}}}\n{img}\n{m.group(3).strip()}\n"

    # The optional argument is itself braced -- [{\includegraphics[..]{..}}] -- so anchor on
    # "[{" ... "}]". Anchoring on "[" ... "]" stops at \includegraphics's own closing bracket.
    return re.sub(r"\\begin\{IEEEbiography\}\[\{(.*?)\}\]\{([^}]*)\}(.*?)\\end\{IEEEbiography\}",
                  bio, src, flags=re.S)


def main() -> int:
    tmp = ROOT / "paper" / "_main_docx_src.tex"
    tmp.write_text(preprocess(TEX.read_text(encoding="utf-8")), encoding="utf-8")
    try:
        subprocess.run(
            ["pandoc", tmp.name, "--citeproc", "--bibliography=references.bib",
             "--csl=ieee.csl", "--metadata", "reference-section-title=REFERENCES",
             "--resource-path=.:figures", "-o", str(OUT)],
            cwd=tmp.parent, check=True)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
