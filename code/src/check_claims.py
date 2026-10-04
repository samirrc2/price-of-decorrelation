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
from decimal import Decimal, ROUND_HALF_UP
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


# Documents that assert a hash or a path must agree with the filesystem. archive_manifest.md
# named a path that had not existed since the layout reorganisation and a config SHA-256 that
# matched neither the current file nor its pre-reorganisation version -- stale for months,
# with nothing to catch it, in the one document whose entire purpose is to pin the dataset.
def _check_asserting_doc(path: Path, label: str) -> list[str]:
    """Paths named in a document must exist; decimals it asserts must be claims."""
    bad = []
    t = path.read_text()
    # A path may be legitimately absent from a fresh clone -- but only if the sentence naming
    # it says so. This gate used to demand that every quoted path exist, which passed in the
    # source working tree (where ignored files are lying around) and failed in a clone on
    # three paths the README already describes correctly: "avoid cloning ignored cache/ /
    # data/raw/", "cleanup ... removes data/raw/ and cache/", and "build_paper.sh builds
    # paper/main.pdf". Requiring the prose to mark them keeps the check non-vacuous: if the
    # README ever claims one of them SHIPS, the sentence loses the marker and the gate fires.
    OPTIONAL = re.compile(r"\bignored?\b|\bremoves?\b|\bbuilds?\b|\bgenerate[sd]?\b"
                          r"|\boptional\b|\bnot distributed\b|\bseparately\b", re.I)
    excused = []
    for m in re.finditer(r"`((?:code|data|results|docs|paper|environment|metadata|archive)"
                         r"/[A-Za-z0-9_./-]+)`", t):
        rel = m.group(1)
        if (ROOT / rel).exists():
            continue
        line = t[t.rfind("\n", 0, m.start()) + 1:t.find("\n", m.end())]
        if OPTIONAL.search(line):
            excused.append(rel)
            continue
        bad.append(f"{label} names a path that does not exist and is not described as "
                   f"ignored, generated or distributed separately: {rel}")
    if excused:
        print(f"     [{label}] absent by design, and the text says so: "
              f"{', '.join(sorted(set(excused)))}")
    claims = json.loads(CLAIMS.read_text())
    forms = set()
    for v in claims.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            av = abs(v)
            for nd in range(7):
                forms.add(f"{av:.{nd}f}")
                forms.add(f"{av:.{nd}f}".rstrip("0").rstrip("."))
                # authors round half UP, Python rounds half to EVEN: 0.3035 must be
                # allowed to appear as "0.304". Omitting this reported the README's
                # correct rounding as a provenance failure.
                forms.add(str(Decimal(str(av)).quantize(Decimal(1).scaleb(-nd),
                                                        rounding=ROUND_HALF_UP)))
                for mult in (1e3, 1e4, 100.0):
                    forms.add(f"{av*mult:.{nd}f}")
                    # Half-up was applied to the plain value but not to the scaled ones, so a
                    # cost written as 2.84 x 10^-3 failed: 0.002835 x 1000 formats as 2.83
                    # under banker's rounding while the author correctly writes 2.84.
                    forms.add(str(Decimal(repr(av * mult)).quantize(
                        Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)))
    # The cost premium the README quotes is cost_ratio_het_over_hom, a claim. Generating
    # every pairwise quotient of every cost here explained almost any number, as it did in
    # check_coverage.py, so it is gone.
    superseded = []
    body = re.sub(r"```.*?```", "", t, flags=re.S)   # code blocks are commands, not claims
    allow = {"0.24433", "10.24433"}                  # DOI fragments
    for m in re.finditer(r"(?<![\w.])(\d+\.\d+)(?![\w])", body):
        lit = m.group(1)
        if lit in forms or lit in allow:
            continue
        # Version numbers were skipped by SHAPE: any d.dd below 15. That silently exempted every
        # ratio these documents quote -- 1.84, 2.3, 4.4, 1.42, 2.52, 1.13, 3.06 -- so the
        # superseded [1.51, 2.35] sat in the response letter and passed. The exemption now needs
        # the line to actually be about a version.
        if re.match(r"^\d\.\d{1,2}$", lit) and float(lit) < 15:
            line = t[t.rfind("\n", 0, m.start()) + 1:t.find("\n", m.end())]
            before = t[max(0, m.start() - 4):m.start()]
            if re.search(r"(>=|==|~=|<=|>|<)\s*$", before):
                continue        # a dependency pin: requests>=2.31, openai>=1.40
            if re.search(r"\bpython\b|\bnumpy\b|\bmatplotlib\b|\bpytest\b|\byaml\b|"
                         r"\bpandas\b|\bscipy\b|\bversion\b|\bv\d|\bubuntu\b|\bmacos\b|"
                         r"\bdocker\b|\bpip\b|\brequirements\b", line, re.I):
                continue
        # An amendments record documents what CHANGED, so it legitimately quotes values the
        # analysis no longer produces. Allow that only where the sentence says so, and name
        # what was excused -- a superseded number stated as a current one still fails.
        line = t[t.rfind("\n", 0, m.start()) + 1:t.find("\n", m.end())]
        if re.search(r"\bpreviously\b|\bsuperseded\b|\bformerly\b|\bearlier\b|\bhad (?:not |been )|"
                     r"\bunderstated\b|\bincorrect(?:ly)?\b|\bused to\b|\bgiving\b",
                     line, re.I):
            superseded.append(lit)
            continue
        bad.append(f"{label} asserts {lit}, which is not a claim at any rounding")

    if superseded:
        print(f"     [{label}] quoted as superseded, and the text says so: "
              f"{', '.join(sorted(set(superseded)))}")
    return bad


def check_documents() -> list[str]:
    bad = []
    # The README is a document that pins paths and asserts results, so it drifts exactly like
    # archive_manifest.md did. Two things are checked: every repo path it names in backticks
    # must exist (it named data/control/runs.csv, which has not existed since captures became
    # dated), and every decimal it asserts outside a code block must be a claim.
    # README.md and PREREGISTRATION_AMENDMENTS.md both assert results and name paths, so both
    # drift the same way archive_manifest.md did. The amendments file is the higher risk of the
    # two: it is the document a reviewer reads to decide what was pre-registered, and it
    # restates roughly twenty-five computed values.
    # The response letter restates dozens of computed values and is read alongside the paper,
    # yet nothing gated it: when the clustering intervals were corrected, the letter kept the
    # superseded [0.3131, 0.3628] and no check noticed. It is gated here for the same reason the
    # other two are.
    for doc in ("README.md", "PREREGISTRATION_AMENDMENTS.md",
                "submission/response_to_reviewers.txt"):
        rd = ROOT / doc
        if not (rd.exists() and CLAIMS.exists()):
            continue
        bad.extend(_check_asserting_doc(rd, doc))
    am = ROOT / "archive_manifest.md"
    if am.exists():
        t = am.read_text()
        # Only the LIVE assertions are gated. The changelog deliberately quotes the stale
        # path and hash it is recording the correction of, and a gate that cannot tell a
        # historical citation from a current claim would force the record to omit what went
        # wrong -- which is the opposite of an audit trail.
        _cl = t.find("## Changelog")
        if _cl > 0:
            t = t[:_cl]
        # every `path` in backticks that looks like a repo file must exist
        for m in re.finditer(r"`((?:data|code|results|paper)/[^`\s]+)`", t):
            rel = m.group(1)
            if "*" in rel or rel.endswith("/"):
                continue
            if not (ROOT / rel).exists():
                bad.append(f"archive_manifest.md names a path that does not exist: {rel}")
        # every 64-hex SHA-256 asserted next to a named file must match that file
        import hashlib
        for m in re.finditer(r"`((?:data|code)/[^`\s]+)`[^`]{0,80}?`([0-9a-f]{64})`", t, re.S):
            rel, want = m.group(1), m.group(2)
            f = ROOT / rel
            if not f.exists():
                continue
            h = hashlib.sha256()
            with f.open("rb") as fh:
                for b in iter(lambda: fh.read(1 << 20), b""):
                    h.update(b)
            if h.hexdigest() != want:
                bad.append(f"archive_manifest.md asserts {rel} = {want[:16]}... "
                           f"but it hashes to {h.hexdigest()[:16]}...")
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
        # Scope the inclusion test to the PRIMARY contrast. A sentence reporting that the
        # AURC interval contains zero -- a different, secondary endpoint -- is not the
        # manuscript conceding its primary result, and reading it as one made this gate fire
        # on a correct paper the moment R3.4's selective-prediction uncertainty was added.
        asserts_incl = False
        for m in re.finditer(r"\bincludes?\s+zero|\bcontains?\s+zero", tex, re.I):
            w = tex[max(0, m.start() - 320):m.end() + 160]
            if re.search(r"AURC|selective[- ]prediction|risk[- ]coverage", w, re.I):
                continue          # a secondary endpoint's interval, not the primary
            asserts_incl = True
            break
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

    # documents that pin hashes or paths
    for b in check_documents():
        fails.append(b)
    checked += 1

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
