"""Gate: every numeric literal in the manuscript is either a CLAIM or a declared non-result.

check_claims.py verifies that a hand-picked list of claims appears in main.tex. That is the
wrong direction: it cannot notice a manuscript number that no analysis produces. This gate
runs the other way -- it walks every literal in main.tex and demands each one be either

  * equal to a value in results/latest/claims.json at some rounding, or
  * a documented transform of one (a cost in scientific notation, a ratio, a percentage), or
  * listed in NON_RESULTS below with a reason.

It was written after an audit found that only 13 of 65 claims were gated while 127 of 184
literals were unaccounted for -- and that five figures in the capability-matched passage had
NO generating code anywhere in the repository. They existed only in main.tex.

  python code/src/check_coverage.py
"""
from __future__ import annotations
import json, re, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "results" / "latest" / "claims.json"
TEX = ROOT / "paper" / "main.tex"

# Literals that are NOT results, each with the reason it appears. Anything not here and not
# traceable to a claim fails the gate, so this list is the explicit, reviewable boundary of
# what the artifact does and does not generate.
NON_RESULTS = {
    "5.4": "model name gpt-5.4-nano",
    "3.5": "model name gemini-3.5-flash",
    "4.3": "model name grok-4.3",
    "0.20": "API list price, provider table",
    "1.25": "API list price, provider table",
    "1.50": "API list price, provider table",
    "2.50": "API list price, provider table",
    "9.00": "API list price, provider table",
    "0.85": "\\includegraphics width fraction",
    "10.24433": "Code Ocean DOI prefix",
    "10.1109": "IEEE DOI prefix",
    "0.63": "rounded endpoint of a descriptive agreement RANGE (0.43-0.63)",
    "0.43": "rounded endpoint of a descriptive agreement RANGE (0.43-0.63)",
    "0000": "IEEE template placeholder in \\history{xxxx 00, 0000}",
    "256": "algorithm name SHA-256, not a quantity",
}


def claim_forms(claims: dict) -> dict[str, list[str]]:
    """Every string a claim could legitimately be printed as -> the claims that explain it."""
    forms: dict[str, list[str]] = {}
    def add(sv: str, key: str):
        forms.setdefault(sv, []).append(key)
    for k, v in claims.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        av = abs(v)
        for nd in range(0, 7):
            add(f"{av:.{nd}f}", k)
            add(f"{av:.{nd}f}".rstrip("0").rstrip("."), k)
            # Python rounds half to EVEN, authors round half UP: 0.3035 formats as "0.303"
            # but the manuscript correctly prints "0.304". Emitting only the banker form made
            # three correctly-rounded manuscript numbers look untraced, i.e. the gate
            # reported its own formatting convention as a provenance failure.
            q = Decimal(str(av)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
            add(f"{q}", k)
            add(f"{q}".rstrip("0").rstrip(".") if "." in f"{q}" else f"{q}", k)
        # documented transforms: a cost printed in scientific notation, and a ratio
        for mult, why in ((1e3, "x1e3"), (1e4, "x1e4"), (100.0, "pct")):
            for nd in (1, 2, 3):
                add(f"{av*mult:.{nd}f}", f"{k} {why}")
                add(f"{av*mult:.{nd}f}".rstrip("0").rstrip("."), f"{k} {why}")
                q = Decimal(str(av * mult)).quantize(Decimal(1).scaleb(-nd),
                                                     rounding=ROUND_HALF_UP)
                add(f"{q}", f"{k} {why}")
    # The "4.4x the cost" claims used to be explained here by generating every pairwise
    # quotient of every cost claim -- 365x365 candidate ratios, which can explain almost any
    # number and therefore explained nothing. cost_ratio_het_over_hom and
    # cost_ratio_het_lite_over_hom are now claims, so the quotients are no longer invented.
    return forms


def main() -> int:
    if not CLAIMS.exists():
        print("[coverage] claims.json absent -- run make_claims.py"); return 2
    if not TEX.exists():
        print("[coverage] paper/main.tex not published in this copy (capsule layout)"); return 2
    claims = json.loads(CLAIMS.read_text())
    forms = claim_forms(claims)

    t = re.sub(r"%.*", "", TEX.read_text())
    t = re.sub(r"\\(?:label|ref|cite[a-z]*|includegraphics|input|url|eqref|doi)\{[^}]*\}", " ", t)
    t = re.sub(r"(\d)\{,\}(\d)", r"\1\2", t)
    # integers below 100 are overwhelmingly counts, section numbers and "5-agent"; the
    # substantive assertions are decimals and large counts, which is what this gates.
    lits = sorted({m.group(1) for m in re.finditer(r"(?<![\w.])(\d+\.\d+|\d{3,})(?![\w])", t)})

    unexplained = []
    for l in lits:
        if l in forms or l in NON_RESULTS:
            continue
        if re.fullmatch(r"(19|20)\d\d", l):      # a year
            continue
        unexplained.append(l)

    explained = len(lits) - len(unexplained)
    print(f"[coverage] {explained}/{len(lits)} manuscript literals traced to a claim or a "
          f"declared non-result ({len(claims)} claims available)")
    for l in unexplained:
        m = re.search(rf"(?<![\w.]){re.escape(l)}(?![\w])", t)
        ctx = " ".join(t[max(0, m.start()-60):m.end()+24].split()) if m else ""
        print(f"  UNTRACED {l}   ...{ctx[:90]}")
    if unexplained:
        print(f"[coverage] {len(unexplained)} manuscript number(s) have no provenance. Either "
              f"the analysis must produce them, or they must be declared in NON_RESULTS "
              f"with a reason.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
