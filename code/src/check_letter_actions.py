#!/usr/bin/env python3
"""Gate: the response letter's claims about what changed must be true of the diff.

Every Author action says a section "was added", "was revised", "now reports" or "was retitled".
Each is a factual claim about the difference between the submitted manuscript and this revision,
and a reviewer checks exactly these. Until now nothing did.

The baseline is the git tag `as-submitted`, which is also what the highlighted PDF diffs against,
so this gate and the yellow highlighting cannot disagree about what is new.

  "was added"     the heading must NOT exist in the submitted manuscript, under that title.
                  When the sentence names an inner subsection as the thing added, that inner
                  heading is what gets checked, not the section containing it.
  "was revised"   asserts a prior version, so the heading must exist in the submitted manuscript
                  under that same title, and its body must differ now. A section retitled in
                  this revision is matched through the letter's own "was retitled" claim.
  "now reports"   asserts only what the current text says, not that an earlier version existed,
                  so it carries no baseline requirement; check_letter_sections.py already binds
                  it to a real heading with that exact title.
  "was retitled"  the number must exist in both and the titles must differ

Exit 0 passed, 1 failed, 2 could not be checked here (no git, or the tag is absent -- a shallow
clone or an exported capsule, where the baseline genuinely is not available).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_letter_sections import ROMAN, LETTERS, sq, strip_tex  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LETTER = ROOT / "submission" / "response_to_reviewers.txt"
BASELINE = "as-submitted"


def headings_and_bodies(body: str) -> dict[str, tuple[str, str]]:
    """{'V-I': (title, body text until the next heading)}"""
    body = re.sub(r"(?<!\\)%.*", "", body)
    marks = []
    sec_i = sub_i = -1
    for m in re.finditer(r"\\(section|subsection)(\*?)\{((?:[^{}]|\{[^{}]*\})*)\}", body):
        kind, star, title = m.group(1), m.group(2), strip_tex(m.group(3))
        if star:
            continue
        if kind == "section":
            sec_i += 1
            sub_i = -1
            key = ROMAN[sec_i] if sec_i < len(ROMAN) else f"?{sec_i}"
        else:
            sub_i += 1
            key = (f"{ROMAN[sec_i]}-{LETTERS[sub_i]}"
                   if 0 <= sec_i < len(ROMAN) and sub_i < len(LETTERS) else f"?{sec_i}-{sub_i}")
        marks.append((m.start(), m.end(), key, title))
    out = {}
    for i, (_s, e, key, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        out[key] = (title, " ".join(body[e:end].split()))
    return out


def git(*args: str) -> str | None:
    try:
        r = subprocess.run(("git", "-C", str(ROOT)) + args, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    if git("rev-parse", "--git-dir") is None:
        print("[letter-actions] INCOMPLETE: not a git checkout, so there is no baseline to "
              "compare the letter's claims against", file=sys.stderr)
        return 2
    old_tex = git("show", f"{BASELINE}:paper/main.tex")
    if old_tex is None:
        print(f"[letter-actions] INCOMPLETE: tag {BASELINE} not present in this copy",
              file=sys.stderr)
        return 2
    new_tex = (ROOT / "paper" / "main.tex").read_text(errors="replace")
    old = headings_and_bodies(old_tex)
    new = headings_and_bodies(new_tex)
    old_titles = {sq(t) for t, _ in old.values()}

    text = " ".join(LETTER.read_text(errors="replace").split())
    fails: list[str] = []
    checked = {"added": 0, "revised": 0, "retitled": 0}

    # group 3 is an inner subsection, which is then the heading the sentence says was added
    pat_add = re.compile(r'Section ([IVX]+(?:-[A-Z])?), [“"]([^”"]+)[”",]*'
                         r'(?: ?,? ?subsection [“"]([^”"]+)[”",]*)? ?,? ?(?:was|is now) added')
    pat_rev = re.compile(r'Section ([IVX]+(?:-[A-Z])?), [“"]([^”"]+)[”",]* ?,? ?was revised')
    pat_ret = re.compile(r'Section ([IVX]+(?:-[A-Z])?) was retitled [“"]([^”"]+)[”",]*')

    retitled_now = {m.group(1) for m in
                    re.finditer(r'Section ([IVX]+(?:-[A-Z])?) was retitled', text)}

    for m in pat_add.finditer(text):
        num, title = m.group(1), m.group(3) or m.group(2)
        checked["added"] += 1
        if sq(title) in old_titles:
            fails.append(f'the letter says Section {num}, "{title}", was added, but a heading '
                         f'with that title is already in the submitted manuscript')
        if num not in new:
            fails.append(f'the letter says Section {num} was added but the revision has no '
                         f'Section {num}')

    for m in pat_rev.finditer(text):
        num, title = m.group(1), m.group(2)
        checked["revised"] += 1
        if num not in new or sq(new[num][0]) != sq(title):
            fails.append(f'the letter says Section {num}, "{title}", was revised, but the '
                         f'revision\'s Section {num} is '
                         f'"{new.get(num, ("absent",""))[0]}"')
            continue
        if sq(title) not in old_titles:
            if num in retitled_now and num in old:
                # the letter itself reports the retitle, so the section is the one that was
                # renumbered or renamed, not a new one
                old_key = num
            else:
                fails.append(f'the letter says Section {num}, "{title}", was revised, but no '
                             f'heading with that title existed in the submitted manuscript -- it '
                             f'is new in this revision, so "revised" overstates its history')
                continue
        else:
            old_key = next(k for k, (t, _) in old.items() if sq(t) == sq(title))
        if old[old_key][1] == new[num][1]:
            fails.append(f'the letter says Section {num}, "{title}", was revised, but its text is '
                         f'byte-identical to the submitted version')

    for m in pat_ret.finditer(text):
        num, title = m.group(1), m.group(2)
        checked["retitled"] += 1
        if num not in new or sq(new[num][0]) != sq(title):
            fails.append(f'the letter says Section {num} was retitled "{title}" but it is now '
                         f'"{new.get(num, ("absent",""))[0]}"')
        elif num in old and sq(old[num][0]) == sq(title):
            fails.append(f'the letter says Section {num} was retitled "{title}" but it already '
                         f'had that title when submitted')

    if fails:
        for f in sorted(set(fails)):
            print("  " + f, file=sys.stderr)
        print(f"[letter-actions] FAILED: {len(set(fails))} claim(s) about the revision do not "
              f"hold against {BASELINE}", file=sys.stderr)
        return 1
    print(f"[letter-actions] {checked['added']} 'was added', {checked['revised']} "
          f"'was revised' and {checked['retitled']} 'was retitled' claim(s) in the "
          f"response letter hold against {BASELINE} "
          f"({len(old)} headings then, {len(new)} now)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
