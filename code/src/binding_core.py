#!/usr/bin/env python3
"""Shared machinery for the binding gates.

check_binding.py binds every number in paper/main.tex to one claim; the same
discipline has to apply to submission/response_to_reviewers.txt, which quotes
most of those numbers back to the reviewers and until now was only set-checked.
Rather than fork the logic, both gates call check() here with their own rule
table, so a fix to the rounding or context rules cannot drift between them.

A rule is (context_regex, literal, target, decimals[, scale]):
  target "claim_key"  the literal must equal that claim, rounded half-up
  target "!reason"    a declared non-result, bound to its context not its string
  scale               multiplies the claim before rounding, for a mantissa
                      printed as 6.48 x 10^{-4}
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

LIT = re.compile(r"(?<![\w.])(\d+\.\d+|\d{3,})(?![\w])")

# Digits running straight into letters are an unsubstituted placeholder: main.tex once shipped
# "[0.393LO,\,0.393HI]" for months because the older pattern required a non-word character
# after the digits. TeX dimensions are the one legitimate form, so they are excluded.
# A lone trailing "x" is a multiplier, not a placeholder: the reviewer's own comment quoted in
# the response letter says "The 1.84x pile-on ratio", which the first version of this gate
# reported as unsubstituted text.
PLACEHOLDER = re.compile(r"(?<![\w.])\d+\.\d+"
                         r"(?!(?:in|cm|mm|pt|ex|em|bp|pc|dd|sp|px|true|x)\b)[A-Za-z]+")

# ISO-8601 freeze timestamps are machine identifiers. Their seconds field otherwise extracts as
# a decimal literal (51.396959) and would have to be declared as a non-result, which binding by
# bare string is exactly what this design avoids. check_freeze_timestamps.py gates them instead.
ISO_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)


def words_before(t: str, start: int, n: int = 6) -> str:
    pre = t[max(0, start - 200):start]
    pre = re.sub(r"\\[a-zA-Z@]+\*?", " ", pre)
    pre = re.sub(r"[^0-9A-Za-z.\-]+", " ", pre)
    return " ".join(pre.split()[-n:]).lower()


def rounds_to(value: float, lit: str, nd: int, scale: float) -> bool:
    v = abs(value) * scale
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    if f"{q}" == lit:
        return True
    return nd == 0 and f"{q}".rstrip("0").rstrip(".") == lit


def check(rules, text, claims, doc, *, placeholders=True):
    """Bind every literal in `text`. Returns (fails, bound, total, n_result, n_declared)."""
    fails: list[str] = []
    if placeholders:
        for m in PLACEHOLDER.finditer(text):
            fails.append(f"unsubstituted placeholder {m.group(0)!r} in {doc} "
                         f"...{' '.join(text[max(0, m.start()-70):m.end()].split())[-70:]}")

    occ = [(m.start(), m.group(1), words_before(text, m.start())) for m in LIT.finditer(text)]
    used: Counter[int] = Counter()
    bound = 0
    for _pos, lit, ctx in occ:
        hits = [i for i, r in enumerate(rules) if r[1] == lit and re.search(r[0], ctx)]
        if not hits:
            fails.append(f"UNBOUND {lit}  after \"{ctx}\"  -- no rule says which claim this "
                         f"number is")
            continue
        if len(hits) > 1:
            fails.append(f"AMBIGUOUS {lit} after \"{ctx}\" matches {len(hits)} rules: "
                         f"{[rules[i][0] for i in hits]}")
            continue
        i = hits[0]
        used[i] += 1
        rule = rules[i]
        target, nd = rule[2], rule[3]
        scale = rule[4] if len(rule) > 4 else 1.0
        bound += 1
        if target.startswith("!"):
            continue
        if target not in claims:
            fails.append(f"{lit} after \"{ctx}\" is bound to {target}, which is not in "
                         f"claims.json")
            continue
        v = claims[target]
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            fails.append(f"{lit} bound to {target}, which is not numeric ({v!r})")
            continue
        if not rounds_to(float(v), lit, nd, scale):
            shown = f"{abs(float(v)) * scale:.6f}".rstrip("0")
            fails.append(f"MISMATCH {doc} says {lit} after \"{ctx}\" but {target} = {v} "
                         f"(= {shown} at the printed scale, {nd}dp)")

    for i, r in enumerate(rules):
        if not used[i]:
            fails.append(f"UNUSED RULE {r[0]!r} matched nothing -- the sentence it binds has "
                         f"been edited or removed, so its number is no longer gated")

    n_result = sum(1 for i, r in enumerate(rules) if used[i] and not r[2].startswith("!"))
    n_declared = sum(1 for i, r in enumerate(rules) if used[i] and r[2].startswith("!"))
    return fails, bound, len(occ), n_result, n_declared
