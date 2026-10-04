#!/usr/bin/env python3
"""Gate: every section, table and figure the response letter points a reviewer at
must exist in the manuscript, under the title the letter gives it.

The letter makes roughly fifty such pointers ("Section V-I, 'Selective
Prediction,' is now a standalone subsection"). Each is a factual claim about the
submitted manuscript, and until now nothing checked any of them. The two defects
this would have caught in this revision were both found by the author reading the
PDF: a bullet still citing Section V-J for selective prediction after it moved to
V-I, and bullets naming a heading that had since been retitled.

Numbering is derived from the manuscript source the way LaTeX derives it:
\\section in order gives I, II, III...; \\subsection within a section gives A, B,
C... Starred sections and the appendix are skipped. The letter's titles are
compared case-insensitively on letters and digits only, because IEEEtran prints
headings in title case while the source writes sentence case.

Exit 0 passed, 1 failed, 2 could not be checked here.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "paper" / "main.tex"
LETTER = ROOT / "submission" / "response_to_reviewers.txt"

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def sq(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def strip_tex(s: str) -> str:
    s = re.sub(r"\\(?:emph|textit|textbf|texttt|text)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("$", "").replace("{", "").replace("}", "")
    s = s.replace("~", " ").replace("--", "-").replace("\\&", "&")
    return s.strip()


def manuscript_headings() -> dict[str, str]:
    """{'V-I': 'Selective prediction', 'VII': 'Threats to validity', ...}"""
    body = TEX.read_text(errors="replace")
    body = re.sub(r"(?<!\\)%.*", "", body)
    out: dict[str, str] = {}
    sec_i = -1
    sub_i = -1
    for m in re.finditer(r"\\(section|subsection)\*?\{((?:[^{}]|\{[^{}]*\})*)\}", body):
        kind, title = m.group(1), strip_tex(m.group(2))
        if m.group(0).startswith("\\section*") or m.group(0).startswith("\\subsection*"):
            continue
        if kind == "section":
            sec_i += 1
            sub_i = -1
            if sec_i < len(ROMAN):
                out[ROMAN[sec_i]] = title
        else:
            sub_i += 1
            if 0 <= sec_i < len(ROMAN) and sub_i < len(LETTERS):
                out[f"{ROMAN[sec_i]}-{LETTERS[sub_i]}"] = title
    return out


def counts() -> tuple[int, int]:
    body = TEX.read_text(errors="replace")
    body = re.sub(r"(?<!\\)%.*", "", body)
    return (len(re.findall(r"\\begin\{table", body)),
            len(re.findall(r"\\begin\{figure", body)))


def main() -> int:
    if not TEX.exists() or not LETTER.exists():
        print("[letter-sections] INCOMPLETE: manuscript or letter missing", file=sys.stderr)
        return 2
    heads = manuscript_headings()
    n_tab, n_fig = counts()
    text = LETTER.read_text(errors="replace")
    fail, checked_sec, checked_title = [], 0, 0

    for m in re.finditer(r'Section ([IVX]+(?:-[A-Z])?)(?:,\s*[“"\'`]+([^”"\']+)[”"\',]*)?', text):
        num, title = m.group(1), m.group(2)
        checked_sec += 1
        if num not in heads:
            fail.append(f'letter cites Section {num}, which the manuscript does not have '
                        f'(it has {", ".join(sorted(heads, key=len))})')
            continue
        if title:
            checked_title += 1
            if sq(title) != sq(heads[num]):
                fail.append(f'Section {num} is titled "{heads[num]}" in the manuscript but the '
                            f'letter calls it "{title}"')

    for m in re.finditer(r"\bTable (\d+)", text):
        n = int(m.group(1))
        if not 1 <= n <= n_tab:
            fail.append(f"letter cites Table {n}; the manuscript has {n_tab} tables")
    for m in re.finditer(r"\bFigure (\d+)", text):
        n = int(m.group(1))
        if not 1 <= n <= n_fig:
            fail.append(f"letter cites Figure {n}; the manuscript has {n_fig} figures")

    if fail:
        for f in sorted(set(fail)):
            print("  " + f, file=sys.stderr)
        print(f"[letter-sections] FAILED: {len(set(fail))} problem(s)", file=sys.stderr)
        return 1
    print(f"[letter-sections] {checked_sec} section pointer(s) in the response letter resolve to "
          f"the manuscript, {checked_title} of them with a title that matches the heading "
          f"exactly; every Table and Figure cited is within the manuscript's {n_tab} tables and "
          f"{n_fig} figures ({len(heads)} headings derived from source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
