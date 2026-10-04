"""Phase 2 finalize — freeze the confirmatory dataset.

Sets runs.csv read-only, SHA-256 hashes it, and records the hash + row count +
timestamp in archive_manifest.md. After this, runs.csv is the paper's dataset and
must never be regenerated; any patch requires a NEW versioned file + changelog.
"""
from __future__ import annotations
import csv
import hashlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main():
    cfg = yaml.safe_load((_HERE / "configs" / "config.yaml").read_text())
    runs_csv = _HERE / cfg["paths"]["runs_csv"]
    if not runs_csv.exists():
        print("No runs.csv — run Phase 2 (python orchestrator.py --phase full) first.")
        return 1

    rows = list(csv.DictReader(runs_csv.open()))
    ok = sum(1 for r in rows if r.get("ok") == "True")
    digest = sha256(runs_csv)

    # set read-only (0444)
    os.chmod(runs_csv, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    L = ["# Archive manifest — confirmatory dataset\n",
         f"- file: `runs.csv`",
         f"- SHA-256: `{digest}`",
         f"- rows (incl. retries): {len(rows)}   usable (ok): {ok}",
         f"- frozen read-only (0444): yes",
         f"- timestamp (UTC): {datetime.now(timezone.utc).isoformat()}",
         f"- config.yaml SHA-256: `{sha256(_HERE / 'configs' / 'config.yaml')}`\n",
         "This file is the paper's dataset. Do NOT regenerate it. Any correction "
         "requires a new versioned file (e.g. runs_v2.csv) plus a changelog entry here."]
    (_HERE / "archive_manifest.md").write_text("\n".join(L) + "\n")
    print(f"runs.csv frozen read-only. SHA-256={digest}")
    print(f"rows={len(rows)} usable={ok}. Wrote archive_manifest.md")
    print("Next: python analyze.py   (Phase 3, $0 API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
