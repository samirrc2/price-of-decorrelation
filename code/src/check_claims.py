"""Gate: every number the manuscript asserts must match results/latest/claims.json.

Paper 2 fails its build when main.tex and the frozen analysis disagree. Paper 1 had no such
gate -- the numbers lived only in prose, so a figure edited by hand, or left behind when an
arm was re-run, reproduced "cleanly" because nothing compared the two.

What it checks:
  1. the PRIMARY endpoint and its interval appear in the manuscript, at the computed values;
  2. no number formatted like one of our claims appears at a DIFFERENT value (drift);
  3. the verdict word matches;
  4. the capture counts match.

Exit 0 = agrees. 1 = a real disagreement. 2 = the manuscript or claims file is not present
in this copy (a /code + /data capsule), which is "could not check here", not a pass.

  python code/src/check_claims.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "results" / "latest" / "claims.json"
TEX = ROOT / "paper" / "main.tex"

# claim -> how it is written in the manuscript. A claim absent from this map is exported for
# reference but not gated; the gate reports its own coverage so that stays visible.
GATED = {
    "primary_delta_kappa": 4,
    "primary_ci_low": 4,
    "primary_ci_high": 4,
    "kappa_hom": 4,
    "kappa_het": 4,
    "frontier_het_lite_kappa": 4,
    "calls_usable": 0,
    "mmlu_overall_n_items": 0,
}


def tex_numbers(t: str) -> set[str]:
    """Every decimal and integer literal in the body, with LaTeX noise stripped."""
    t = re.sub(r"%.*", "", t)                      # comments
    t = re.sub(r"\\(?:label|ref|cite[a-z]*|includegraphics|input|url)\{[^}]*\}", " ", t)
    # LaTeX thousands separators: the manuscript writes 54{,}000 and 94{,}566, so a literal
    # match on "54000" failed against a paper that was perfectly correct. Normalise them
    # away before extracting, or the gate reports its own formatting assumption as a defect.
    t = re.sub(r"(\d)\{,\}(\d)", r"\1\2", t)
    t = re.sub(r"(\d)[,\\][\s]?(\d{3})\b", r"\1\2", t)
    return set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", t))


# Outputs that are committed or hash-compared must not embed machine-specific paths: the
# capsule and a local checkout produced byte-different mmlu_replication.json for identical
# data purely because the file recorded an absolute input path. A hash comparison that can
# never succeed across machines is not a reproducibility check.
PORTABLE = ["results/mmlu_replication.json", "results/revision_metrics.json",
            "results/latest/claims.json"]
ABSOLUTE = re.compile(r'"(?:/Users/|/home/|/private/|[A-Z]:\\\\)')


def check_portable() -> list[str]:
    bad = []
    for rel in PORTABLE:
        p = ROOT / rel
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if ABSOLUTE.search(line):
                bad.append(f"{rel}:{i} embeds a machine-specific path: {line.strip()[:72]}")
    return bad


def main() -> int:
    if not CLAIMS.exists():
        print(f"[check-claims] {CLAIMS.relative_to(ROOT)} absent -- run make_claims.py")
        return 2
    if not TEX.exists():
        print("[check-claims] paper/main.tex not published in this copy -- "
              "nothing to gate (capsule layout)")
        return 2
    claims = json.loads(CLAIMS.read_text())
    tex = TEX.read_text()
    present = tex_numbers(tex)

    fails, checked = [], 0
    for key, nd in GATED.items():
        if key not in claims:
            fails.append(f"{key}: gated but absent from claims.json"); continue
        v = claims[key]
        want = f"{v:.{nd}f}" if nd else str(int(v))
        checked += 1
        # the manuscript may round: accept the full precision OR any shorter rounding of it
        forms = {want}
        if nd:
            for k in range(2, nd + 1):
                forms.add(f"{v:.{k}f}")
        if not (forms & present):
            fails.append(f"{key} = {v}: no form of it ({', '.join(sorted(forms))}) "
                         f"appears in main.tex")

    # The VERDICT, gated on what the manuscript actually asserts rather than on the word.
    # An earlier version looked for the literal "CONFIRMED", which appears nowhere in
    # main.tex -- so the check passed vacuously, and still passed when the verdict was
    # flipped under fault injection. The manuscript's claim is directional: the interval
    # excludes zero and the effect is a de-correlation (positive delta-kappa).
    if "verdict" in claims:
        checked += 1
        vw = str(claims["verdict"]).lower()
        lo, hi = claims.get("primary_ci_low"), claims.get("primary_ci_high")
        excl = (lo is not None and hi is not None and (lo > 0 or hi < 0))
        asserts_excl = bool(re.search(r"\bexcludes?\s+zero", tex, re.I))
        asserts_incl = bool(re.search(r"\bincludes?\s+zero|\bcontains?\s+zero", tex, re.I))
        if vw == "confirmed":
            if not excl:
                fails.append("claims say CONFIRMED but the primary interval contains zero")
            if not asserts_excl:
                fails.append("CONFIRMED, yet main.tex never states the interval excludes zero")
            if asserts_incl:
                fails.append("main.tex says the primary interval INCLUDES zero; "
                             "claims say CONFIRMED with it excluding zero")
            # a contradicted/weakened reading must not be asserted anywhere
            if re.search(r"(?:does not|fails to|did not)\s+(?:de-?correlate|reduce)", tex, re.I):
                fails.append("main.tex asserts a null/negative result; claims say CONFIRMED")
        else:
            if asserts_excl:
                fails.append(f"claims say {vw.upper()} but main.tex asserts the interval "
                             f"excludes zero")

    # drift: a near-miss of the primary endpoint is worse than an absent one, because it
    # looks right. Flag any 4-dp number within 0.01 of it that is not it.
    p = claims.get("primary_delta_kappa")
    if p is not None:
        near = {n for n in present if re.fullmatch(r"0\.\d{4}", n)
                and abs(float(n) - p) < 0.01 and float(n) != round(p, 4)}
        if near:
            fails.append(f"primary endpoint drift: main.tex contains {sorted(near)} "
                         f"near but not equal to {p:.4f}")

    # portability of the committed outputs
    for b in check_portable():
        fails.append(b)
    checked += len(PORTABLE)

    print(f"[check-claims] {checked} gated claims checked against "
          f"{TEX.relative_to(ROOT)} ({len(present)} numeric literals found)")
    for f in fails:
        print(f"  FAIL {f}")
    if fails:
        print(f"[check-claims] {len(fails)} disagreement(s)")
        return 1
    print(f"[check-claims] manuscript agrees with the frozen analysis "
          f"({len(claims)} claims available, {checked} gated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
