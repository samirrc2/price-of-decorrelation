#!/usr/bin/env python3
"""Gate: every freeze timestamp quoted in a document must be one the receipts carry.

Reviewer 3 asked for exact pre-registration timestamp evidence, so the response
letter now prints the freeze times in prose. A timestamp typed into prose is a
claim about a cryptographic receipt, and nothing else in the pipeline reads it:
check_claims masks ISO-8601 shapes precisely so they are not mistaken for
results, which means a wrong digit in a timestamp would otherwise pass every gate.

Source of truth is the receipts themselves, docs/freeze_receipt.md and
docs/freeze_receipt_mmlu.md. A quoted timestamp may be the receipt value in full
or truncated to whole seconds (2026-07-03T20:41:51Z), and nothing else.

Exit 0 passed, 1 failed, 2 could not be checked here (a receipt is missing).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = {
    "confirmatory": (ROOT / "docs" / "freeze_receipt.md",
                     re.compile(r"timestamp \(UTC\):\s*([0-9T:.+-]+)")),
    "replication":  (ROOT / "docs" / "freeze_receipt_mmlu.md",
                     re.compile(r"Frozen \(UTC\):\s*`([0-9T:.+-]+)`")),
}
SCANNED = [
    Path("paper") / "main.tex",
    Path("submission") / "response_to_reviewers.txt",
    Path("PREREGISTRATION_AMENDMENTS.md",),
    Path("README.md"),
]
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")


def accepted(value: str) -> set[str]:
    """The receipt value and its whole-second truncations."""
    base = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", value).group(1)
    return {value, base, base + "Z", base + "+00:00"}


def main() -> int:
    truth, missing = {}, []
    for label, (path, pat) in RECEIPTS.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        m = pat.search(path.read_text(errors="replace"))
        if not m:
            missing.append(f"{path.relative_to(ROOT)} (no timestamp line)")
            continue
        truth[label] = m.group(1)
    if missing:
        print("[freeze-timestamps] INCOMPLETE: cannot read " + ", ".join(missing)
              + "; the receipts are the only source of truth, so this is not a pass",
              file=sys.stderr)
        return 2

    ok = {form for v in truth.values() for form in accepted(v)}
    fail, checked = [], 0
    for rel in SCANNED:
        p = ROOT / rel
        if not p.exists():
            continue
        for m in ISO.finditer(p.read_text(errors="replace")):
            checked += 1
            if m.group(0) not in ok:
                fail.append(f"{rel}: {m.group(0)} is not a freeze-receipt timestamp "
                            f"(receipts carry {', '.join(sorted(truth.values()))})")

    if fail:
        for f in fail:
            print("  " + f, file=sys.stderr)
        print(f"[freeze-timestamps] FAILED: {len(fail)} quoted timestamp(s) do not match the "
              f"receipts", file=sys.stderr)
        return 1
    print(f"[freeze-timestamps] {checked} quoted timestamp(s) across "
          f"{len([p for p in SCANNED if (ROOT / p).exists()])} document(s) match the "
          f"{len(truth)} freeze receipts exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
