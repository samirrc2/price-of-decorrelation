"""Highlight bibliography entries added since the baseline, in the diff build's .bbl.

latexdiff diffs main.tex, where the bibliography is a single \\bibliography{references} line.
The entries themselves do not exist until bibtex expands them at build time, so a reference
added in the revision could never be marked: the in-text citation came out highlighted while
its entry in the REFERENCES list did not.

This marks the entries whose keys are cited in the revision but not in the baseline. An entry
that merely MOVED is deliberately left alone -- adding one reference renumbers every later
entry, and marking those would flood the list with churn that reflects numbering rather than
content. That is why check_highlighting.py fails when an existing \\bibitem is marked, and this
script is written to keep that rule true: it marks new keys only, and names them.

  python3 submission/highlight_newrefs.py <bbl> <baseline.tex> <new.tex>
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CITE = re.compile(r"\\cite[a-z]*\{([^}]*)\}")


def keys(tex: str) -> set[str]:
    out = set()
    for m in CITE.finditer(tex):
        out |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    return out


def box(text: str) -> str:
    """soul cannot cross \\emph, \\url or math, so each is boxed into an opaque atom."""
    text = re.sub(r"(?<!\\)\$([^$]+)\$", lambda m: r"\mbox{$" + m.group(1) + r"$}", text)
    for cmd in ("emph", "url", "texttt", "textbf", "textit"):
        text = re.sub(r"\\" + cmd + r"(\{[^{}]*\})",
                      lambda m, c=cmd: r"\mbox{\\" + c + m.group(1) + "}", text)
    return text.replace(r"\\mbox", r"\mbox").replace(r"\mbox{\\", r"\mbox{" + "\\")


def main() -> int:
    bbl, base, new = (Path(a) for a in sys.argv[1:4])
    if not bbl.exists():
        print("   [newrefs] no .bbl yet; nothing to mark")
        return 0
    added = keys(new.read_text()) - keys(base.read_text())
    if not added:
        print("   [newrefs] no references added since the baseline")
        return 0

    s = bbl.read_text()
    marked = []
    for k in sorted(added):
        m = re.search(r"(\\bibitem\{" + re.escape(k) + r"\}\s*\n)(.*?)(?=\n\s*\\bibitem|\n\s*\\end\{thebibliography\})",
                      s, flags=re.S)
        if not m:
            print(f"   [newrefs] {k} is newly cited but has no .bbl entry")
            continue
        body = m.group(2).strip()
        if "\\texthl" in body:
            continue
        s = s[:m.start(2)] + "\\texthl{" + box(body) + "}" + s[m.end(2):]
        marked.append(k)
    bbl.write_text(s)
    print(f"   [newrefs] {len(marked)} new reference entr{'y' if len(marked)==1 else 'ies'} "
          f"highlighted: {', '.join(marked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
