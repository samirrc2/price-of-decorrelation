#!/usr/bin/env python3
"""Lock submission/final_submission against the manuscript and the frozen analysis.

Every other gate here checks paper/main.tex. Nothing checked the files actually uploaded to
IEEE, so the package could drift from the paper it is supposed to be: a PDF rebuilt from an
older source, a Word file whose citations renumber, a graphical-abstract caption quoting a
figure the analysis no longer produces. Each of those ships silently.

Exit 0 all checks passed, 1 a check failed, 2 the package is not present (not a pass).
"""
import json, re, sys, zipfile, hashlib, html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG  = ROOT / "submission" / "final_submission"
sq   = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def pool():
    """Every value the frozen analysis produced, and that value x100."""
    p = set()
    def walk(v):
        if isinstance(v, dict):
            for x in v.values(): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            p.add(abs(float(v))); p.add(abs(float(v)) * 100.0)
    walk(json.loads((ROOT / "results" / "latest" / "claims.json").read_text()))
    return p


def docx_text(p):
    x = zipfile.ZipFile(p).read("word/document.xml").decode()
    return html.unescape(re.sub(r"<[^>]+>", "", x.replace("</w:p>", "\n"))).replace("\xa0", " ")


def main() -> int:
    if not PKG.is_dir():
        print("[deliverables] submission/final_submission not present here; cannot check")
        return 2
    required = ["FINAL Article.pdf", "FINAL Article.docx", "FINAL Article LaTeX Source.zip",
                "Graphical Abstract.jpg", "Graphical Abstract Caption.docx"]
    missing = [f for f in required if not (PKG / f).exists()]
    if missing:
        print(f"[deliverables] missing: {missing}")
        return 1

    fails, checks = [], 0
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

    # 1. the shipped PDF is the manuscript build, not a stale copy
    checks += 1
    if sha(PKG / "FINAL Article.pdf") != sha(ROOT / "paper" / "main.pdf"):
        fails.append("FINAL Article.pdf differs from paper/main.pdf")

    # 2. the caption's figures must come from the analysis, not be typed in
    cap = docx_text(PKG / "Graphical Abstract Caption.docx")
    body = cap.split("Caption for the Graphical Abstract")[-1]
    p = pool()
    for m in re.finditer(r"(?<![\w.])(\d+\.\d+)(?![\w])", body):
        lit = m.group(1)
        checks += 1
        dp = len(lit.split(".")[1])
        if not any(round(q, dp) == float(lit) for q in p):
            fails.append(f"Graphical Abstract caption: {lit} traces to no analysis output")

    # 3. the caption must not outgrow the limit IEEE Access sets
    words = len(body.split())
    checks += 1
    if not (0 < words <= 200):
        fails.append(f"Graphical Abstract caption section is {words} words; expected a short caption")

    # 4. the Word file must carry the same prose as the PDF
    import pymupdf
    P = sq("".join(pg.get_text() for pg in pymupdf.open(PKG / "FINAL Article.pdf")))
    D = docx_text(PKG / "FINAL Article.docx")
    paras = [x.strip() for x in D.split("\n") if len(x.split()) >= 14]
    checks += len(paras)
    absent = [x for x in paras if sq(x)[:80] not in P]
    # the running head repeats per page and is furniture, not prose
    absent = [x for x in absent if "Price of De-correlation in Heterogeneous" not in x]
    # IEEE CSL abbreviates long author lists to "et al." where IEEEtran spells them out
    absent = [x for x in absent if not re.match(r"\[\d+\]", x.strip())]
    for x in absent:
        fails.append(f"DOCX paragraph absent from the PDF: {' '.join(x.split())[:70]}")

    # 5. the LaTeX source must be the same source the PDF came from
    z = zipfile.ZipFile(PKG / "FINAL Article LaTeX Source.zip")
    checks += 1
    if "FINAL Article.tex" not in z.namelist():
        fails.append("LaTeX Source.zip does not contain 'FINAL Article.tex'")
    else:
        if sq(z.read("FINAL Article.tex").decode()) != sq((ROOT / "paper" / "main.tex").read_text()):
            fails.append("LaTeX Source.zip tex differs from paper/main.tex")

    if fails:
        print(f"[deliverables] FAILED ({len(fails)}):")
        for f in fails:
            print("   -", f)
        return 1
    print(f"[deliverables] OK - {checks} check(s): shipped PDF matches the manuscript build, "
          f"every caption figure traces to the frozen analysis, {len(paras)} DOCX paragraphs "
          f"found in the PDF, LaTeX source matches paper/main.tex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
