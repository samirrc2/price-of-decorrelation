"""Pin every irreplaceable input with a SHA-256, and verify them later.

Paper 2 ships DATA_MANIFEST.md plus per-capture freeze receipts, so a reviewer can tell
whether the bytes they have are the bytes the paper was computed from. Paper 1 had neither:
the analysis printed input hashes to the log, but nothing recorded what they SHOULD be, so a
silently corrupted or regenerated input would reproduce "cleanly" against itself.

  python code/src/make_manifest.py            # write data/MANIFEST.sha256 + DATA_MANIFEST.md
  python code/src/make_manifest.py --verify   # check every pinned file; exit 1 on mismatch

Irreplaceable = cannot be regenerated without spending API budget, or defines the frozen
protocol: the capture CSVs, the model inputs, the ground truth, and the configs. Derived
outputs under results/ are deliberately NOT pinned -- they are what reproduction rebuilds.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "MANIFEST.sha256"
DOC = ROOT / "DATA_MANIFEST.md"

# (glob, why it is irreplaceable) -- the comment lands in DATA_MANIFEST.md
PATTERNS = [
    ("data/confirmatory/*/runs.csv", "primary capture; 54k live model calls"),
    ("data/control/*/runs.csv", "control-arm capture"),
    ("data/mmlu/*/runs.csv", "cross-domain replication capture"),
    ("data/minipilot/*/runs.csv", "gating pilot capture"),
    ("data/pilot/clean/runs.csv", "archived pilot, independent per-agent seeding; the "
                                 "manuscript's 0.113 and Fig. 2"),
    ("data/pilot/broken/runs.csv", "archived pilot, shared per-run seeding; the "
                                   "manuscript's 0.485 and Fig. 2"),
    ("data/appendix/*/runs.csv", "appendix capture"),
    # The temperature-robustness subgrid backs Table 8 and the T=0.0/0.7/1.0 contrasts in
    # the text. It was tracked in git but absent from this manifest, so those manuscript
    # numbers rested on inputs nothing verified.
    ("data/temperature_robustness_small/*/runs_T*.csv", "temperature-robustness subgrid"),
    ("data/configs/*.yaml", "frozen protocol: grid, models, estimands"),
    ("data/inputs/*.json", "serialized model inputs (finance)"),
    ("data/inputs_mmlu/*.json", "serialized model inputs (MMLU)"),
    ("data/mmlu_ground_truth.json", "answer key for the cross-domain arm"),
    ("data/mmlu_manifest.json", "MMLU item provenance"),
    # The offline price cache is NOT optional. metrics.forward_return_signs() prefers it and
    # falls back to yfinance when it is absent -- i.e. a keys-free, offline capsule silently
    # becomes a network-dependent one, and the reviewer analyses crash with KeyError:'HOM'
    # when the fallback yields no signs. Omitting it from the capsule is how iteration 3
    # failed, and omitting it from THIS list is why the integrity gate did not catch that.
    ("data/datacache/forward_returns.json", "offline forward-return cache; the analyses "
                                            "fall back to a NETWORK call without it"),
    ("data/datacache/prices.json", "offline EOD price cache"),
]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def collect():
    """Resolved (relative path, sha, bytes, reason), sorted and deduplicated."""
    seen, out = set(), []
    for pat, why in PATTERNS:
        for p in sorted(ROOT.glob(pat)):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            # a symlinked "latest" directory would otherwise pin the same bytes twice under
            # two names, and then a legitimate re-point of `latest` reads as a corruption
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            out.append((rel, sha(p), p.stat().st_size, why))
    return out


# Files a /code + /data capsule cannot run without. Checked separately from the hash
# verification because a capsule can be internally consistent and still be missing an input
# the analysis needs -- which is precisely what happened: the hashes all verified while
# data/datacache/forward_returns.json was absent, so the reviewer analyses fell back to a
# network call and then crashed.
CAPSULE_REQUIRED = [
    ("data/confirmatory", "primary capture"),
    ("data/configs/config.yaml", "frozen protocol"),
    ("data/datacache/forward_returns.json", "offline price cache (else a network fallback)"),
    ("data/inputs", "serialized model inputs"),
    ("data/pilot/clean/runs.csv", "pilot arm Fig. 2 and two manuscript numbers derive from"),
    ("data/pilot/broken/runs.csv", "pilot arm Fig. 2 and two manuscript numbers derive from"),
]


def check_capsule(root: Path) -> list[str]:
    missing = []
    for rel, why in CAPSULE_REQUIRED:
        if not (root / rel).exists():
            missing.append(f"{rel} -- {why}")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--capsule", action="store_true",
                    help="assert the inputs a /code + /data capsule must carry")
    a = ap.parse_args()

    if a.capsule:
        missing = check_capsule(ROOT)
        for m in missing:
            print(f"  MISSING {m}")
        print(f"[capsule] {len(CAPSULE_REQUIRED)-len(missing)}/{len(CAPSULE_REQUIRED)} "
              f"required inputs present")
        return 1 if missing else 0

    if a.verify:
        if not MANIFEST.exists():
            print(f"[manifest] {MANIFEST.relative_to(ROOT)} absent -- nothing pinned to verify")
            return 2
        pinned = {}
        for line in MANIFEST.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            h, rel = line.split("  ", 1)
            pinned[rel] = h
        bad, missing, ok = [], [], 0
        for rel, h in sorted(pinned.items()):
            p = ROOT / rel
            if not p.exists():
                missing.append(rel); continue
            actual = sha(p)
            if actual != h:
                bad.append((rel, h, actual))
            else:
                ok += 1
        for rel in missing:
            print(f"  MISSING  {rel}")
        for rel, want, got in bad:
            print(f"  MISMATCH {rel}\n           pinned {want[:16]}  actual {got[:16]}")
        print(f"[manifest] {ok}/{len(pinned)} pinned inputs verified"
              f"{f', {len(missing)} missing' if missing else ''}"
              f"{f', {len(bad)} CORRUPT' if bad else ''}")
        return 1 if (bad or missing) else 0

    rows = collect()
    if not rows:
        print("[manifest] no inputs matched -- refusing to write an empty manifest", file=sys.stderr)
        return 1
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        "# SHA-256 of every irreplaceable input. Verify: "
        "python code/src/make_manifest.py --verify\n"
        + "".join(f"{h}  {rel}\n" for rel, h, _, _ in rows))

    by_reason = {}
    for rel, h, n, why in rows:
        by_reason.setdefault(why, []).append((rel, h, n))
    L = ["# Data manifest",
         "",
         "SHA-256 of every input the reported numbers depend on. These files are frozen: the",
         "analysis reads them and writes only under `results/`. Nothing here is regenerable",
         "without spending API budget, so a mismatch means the bytes changed, not that a",
         "re-run differed.",
         "",
         "```",
         "python code/src/make_manifest.py --verify",
         "```",
         "",
         f"{len(rows)} files, {sum(n for _, _, n, _ in rows) / 1e6:.1f} MB total.",
         ""]
    for why, items in by_reason.items():
        L += [f"## {why}", "", "| File | Bytes | SHA-256 |", "|---|---:|---|"]
        for rel, h, n in items:
            L.append(f"| `{rel}` | {n:,} | `{h}` |")
        L.append("")
    DOC.write_text("\n".join(L))
    print(f"[manifest] pinned {len(rows)} inputs "
          f"({sum(n for _, _, n, _ in rows)/1e6:.1f} MB) -> "
          f"{MANIFEST.relative_to(ROOT)} + {DOC.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
