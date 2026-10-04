#!/usr/bin/env python3
"""Gate: each freeze receipt must be internally truthful, and the pre-registration must not move.

A freeze receipt asserts the SHA-256 of a set of artifacts at a moment in time. Two different
things can be checked, and conflating them produces nonsense:

  1. Is the receipt TRUE of the commit it names? Every artifact it lists must hash as stated in
     that commit's tree. This is the integrity of the receipt itself and can only be checked
     where git history is available.
  2. Does the artifact still hash that way TODAY? True only for artifacts that must never change.
     The pre-registration is one: the entire pre-registration argument rests on it. The analysis
     code is not -- the revision added four arms -- and config.yaml is not, because the repo moved
     to the dated Code Ocean layout and gained commented documentation of the control arm.

An earlier version of this check asserted (2) for everything the receipt names and would have
reported the artifact broken for three files that legitimately evolved. A version before that
parsed the receipt with a pattern that matched no rows at all and printed "0/0 artifacts ...
as the receipt says", which reads as a pass and verifies nothing. Both failure modes are guarded
here: the row pattern is proven against the real file, and zero rows is a failure.

Exit 0 passed, 1 failed, 2 could not be checked here (no git history, or no receipt).
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALL = "*"

# (receipt, the commit it froze or None, artifacts that must still hash the same TODAY)
#
# The confirmatory receipt names a git commit, so its hashes are checked against that commit's
# tree. Only the pre-registration must ALSO still match today: the analysis code gained four
# arms in the revision and config.yaml moved to the dated Code Ocean layout and picked up
# commented documentation of the control arm, both after the freeze and both recorded as
# amendments.
#
# The replication receipt names no commit -- it was written before any API call for that arm, so
# there was nothing to commit yet. Every artifact it lists is therefore required to match TODAY:
# a pre-collection freeze whose inputs, prompt, ground truth or generator had since changed
# would be worthless as evidence.
RECEIPTS = [
    (ROOT / "docs" / "freeze_receipt.md",
     re.compile(r"git commit:\s*`([0-9a-f]{7,40})`"),
     {"preregistration.md"}),
    (ROOT / "docs" / "freeze_receipt_mmlu.md", None, ALL),
]
# The two receipts put the columns in OPPOSITE orders -- "| file | sha256 |" and
# "| SHA-256 | file |" -- so both shapes are accepted and the hash is identified by its form,
# not by its position. Assuming one order is what made the first version of this check parse
# zero rows out of the replication receipt.
ROW_NAME_FIRST = re.compile(r"\|\s*`([^`]+)`\s*\|\s*`?([0-9a-f]{64})`?\s*\|")
ROW_HASH_FIRST = re.compile(r"\|\s*`?([0-9a-f]{64})`?\s*\|\s*`([^`]+)`\s*\|")
# a receipt may also attest a whole directory by digest over each file's name and bytes
DIR_DIGEST = re.compile(r"directory digest \(`([^`]+)`\): `([0-9a-f]{64})`")


def rows_of(text: str) -> list[tuple[str, str]]:
    rows = ROW_NAME_FIRST.findall(text)
    rows += [(name, h) for h, name in ROW_HASH_FIRST.findall(text)]
    return rows


def dir_digest(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()
# where an artifact named flat in a July receipt lives in today's tree
SEARCH = ["", "docs/", "data/", "data/configs/", "code/src/", "code/", "paper/"]


def git(*args: str) -> str | None:
    try:
        r = subprocess.run(("git", "-C", str(ROOT)) + args, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def resolve(name: str) -> Path | None:
    for pre in SEARCH:
        p = ROOT / (pre + name)
        if p.is_file():
            return p
    return None


def main() -> int:
    top = git("rev-parse", "--show-toplevel")
    if top is None or Path(top.strip()).resolve() != ROOT.resolve():
        print("[freeze-receipt] INCOMPLETE: no git history for this tree, so a receipt cannot be "
              "checked against the commit it names", file=sys.stderr)
        return 2

    fails: list[str] = []
    total_rows = at_commit = today = 0

    for path, commit_pat, must_hold_today in RECEIPTS:
        if not path.exists():
            print(f"[freeze-receipt] INCOMPLETE: {path.name} is absent", file=sys.stderr)
            return 2
        text = path.read_text(errors="replace")
        rows = rows_of(text)
        if not rows:
            fails.append(f"{path.name}: its artifact table parsed to ZERO rows, so this gate "
                         f"would verify nothing -- the pattern or the file has changed shape")
            continue
        total_rows += len(rows)

        commit = None
        if commit_pat is not None:
            m = commit_pat.search(text)
            if not m:
                fails.append(f"{path.name}: names no git commit, so nothing anchors its hashes")
                continue
            commit = m.group(1)
            if git("cat-file", "-e", f"{commit}^{{commit}}") is None:
                fails.append(f"{path.name}: names commit {commit[:12]}, which is not in this "
                             f"history")
                continue

        # 1. the receipt must be true of the commit it froze, where it names one
        for name, want in (rows if commit else []):
            blob = None
            for pre in SEARCH:
                try:
                    r = subprocess.run(("git", "-C", str(ROOT), "show", f"{commit}:{pre}{name}"),
                                       capture_output=True)
                except OSError:
                    r = None
                if r is not None and r.returncode == 0:
                    blob = r.stdout
                    break
            if blob is None:
                fails.append(f"{path.name}: {name} is named by the receipt but is not in commit "
                             f"{commit[:12]}")
                continue
            got = hashlib.sha256(blob).hexdigest()
            at_commit += 1
            if got != want:
                fails.append(f"{path.name}: {name} hashes {got[:16]} in commit {commit[:12]} but "
                             f"the receipt says {want[:16]}")

        # 2. artifacts that must never change must still match today
        want_by_name = dict(rows)
        names_today = sorted(want_by_name) if must_hold_today == ALL else sorted(must_hold_today)
        for name in names_today:
            if name not in want_by_name:
                fails.append(f"{path.name}: expected to attest {name} and does not")
                continue
            p = resolve(name)
            if p is None:
                fails.append(f"{name} is attested by {path.name} but is missing from the tree")
                continue
            got = hashlib.sha256(p.read_bytes()).hexdigest()
            today += 1
            if got != want_by_name[name]:
                fails.append(f"{name} must never change after the freeze, but it now hashes "
                             f"{got[:16]} against the receipt's {want_by_name[name][:16]}")

        # 3. and a directory attested by digest must still produce it
        for rel, want in DIR_DIGEST.findall(text):
            d = ROOT / rel
            if not d.is_dir():
                fails.append(f"{path.name} attests the directory {rel}, which is not present")
                continue
            got = dir_digest(d)
            today += 1
            if got != want:
                fails.append(f"{rel} digests {got[:16]} but {path.name} says {want[:16]}")

    if fails:
        for f in fails:
            print("  " + f, file=sys.stderr)
        print(f"[freeze-receipt] FAILED: {len(fails)} problem(s)", file=sys.stderr)
        return 1
    print(f"[freeze-receipt] {at_commit}/{total_rows} artifacts named across "
          f"{len(RECEIPTS)} receipts hash exactly as the receipt says in the commit it froze; "
          f"{today} artifact(s) that must never change still match today")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
