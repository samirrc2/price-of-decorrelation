"""Phase 3 replication check — analyze.py must be byte-identical on re-execution.

Runs analyze.py twice from the frozen runs.csv, SHA-256s every generated output
(markdown, figures, tables), and diffs the two passes. Writes replication_check.md.
Exit 0 iff all outputs are byte-identical.
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
TARGETS = ["metrics_summary.md", "headline_check.md", "protocol_exhibit.md",
           "threats_to_validity.md", "appendix/data_availability.md"]
TARGET_DIRS = ["figures", "tables"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot() -> dict[str, str]:
    out = {}
    for t in TARGETS:
        p = _HERE / t
        if p.exists():
            out[t] = sha(p)
    for d in TARGET_DIRS:
        for p in sorted((_HERE / d).glob("*")):
            out[f"{d}/{p.name}"] = sha(p)
    return out


def run_analyze():
    return subprocess.run([sys.executable, "analyze.py"], cwd=_HERE,
                          capture_output=True, text=True)


def main():
    if not (_HERE / "runs.csv").exists():
        print("No runs.csv — run Phase 2 first."); return 1
    run_analyze(); first = snapshot()
    run_analyze(); second = snapshot()

    keys = sorted(set(first) | set(second))
    diffs = [k for k in keys if first.get(k) != second.get(k)]
    L = ["# Replication check\n",
         f"- outputs compared: {len(keys)}",
         f"- byte-identical: {len(keys) - len(diffs)}/{len(keys)}",
         f"- deterministic: {'YES' if not diffs else 'NO'}\n"]
    if diffs:
        L.append("## Non-identical outputs (fix nondeterminism)\n")
        for k in diffs:
            L.append(f"- `{k}`: {first.get(k)} vs {second.get(k)}")
    else:
        L.append("All Phase-3 outputs reproduce byte-for-byte from (runs.csv, config.yaml).")
    (_HERE / "replication_check.md").write_text("\n".join(L) + "\n")
    print(f"Deterministic: {'YES' if not diffs else 'NO'} "
          f"({len(keys)-len(diffs)}/{len(keys)} identical). Wrote replication_check.md")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
