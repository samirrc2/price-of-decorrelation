"""Phase 1 — cryptographic pre-registration freeze.

SHA-256 hashes the frozen artifacts, writes freeze_receipt.md, and makes a LOCAL
git commit (message: prereg-freeze-price-of-diversity-v2). Does NOT push to any
remote (compliance clearance pending). Records commit hash + timestamp.
"""
from __future__ import annotations
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent

FROZEN = ["config.yaml", "agent.py", "analyze.py", "prompt_template.txt",
          "preregistration.md", "appendix/grid.csv", "model_manifest.md"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=_HERE, capture_output=True, text=True)


def main():
    hashes = {}
    missing = []
    for rel in FROZEN:
        p = _HERE / rel
        if p.exists():
            hashes[rel] = sha256(p)
        else:
            missing.append(rel)
    if missing:
        print("Cannot freeze — missing artifacts:", missing)
        print("Run build_grid.py (and probe_models.py) first.")
        return 2

    # local git commit (init if needed); never touch a remote
    if not (_HERE / ".git").exists():
        git("init")
        git("config", "user.email", "prereg@local")
        git("config", "user.name", "prereg")
    git("add", "-A")
    commit = git("commit", "-m", "prereg-freeze-price-of-diversity-v2")
    show = git("rev-parse", "HEAD")
    commit_hash = show.stdout.strip() or "(commit failed — see message below)"
    ts = datetime.now(timezone.utc).isoformat()

    lines = ["# Freeze receipt — prereg-freeze-price-of-diversity-v2\n",
             f"- timestamp (UTC): {ts}",
             f"- git commit: `{commit_hash}`",
             "- remote push: NONE (compliance clearance pending; local commit only)\n",
             "## SHA-256 of frozen artifacts\n",
             "| file | sha256 |", "|---|---|"]
    for rel, h in hashes.items():
        lines.append(f"| `{rel}` | `{h}` |")
    lines.append("\n## git commit output\n```")
    lines.append((commit.stdout + commit.stderr).strip())
    lines.append("```")
    (_HERE / "freeze_receipt.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote freeze_receipt.md. commit={commit_hash}")
    print("Frozen:", ", ".join(hashes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
