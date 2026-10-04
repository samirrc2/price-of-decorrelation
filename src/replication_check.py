"""Phase 3 replication check — analyze.py must be byte-identical on re-execution.

Runs analyze.py twice from the frozen runs.csv, SHA-256s every generated output
(markdown, figures, tables), and diffs the two passes. Writes replication_check.md.
Exit 0 iff all outputs are byte-identical.

Note: analyze.py stamps input SHA-256 hashes (not wall-clock) into
metrics_summary.md. As a safety net, any legacy "- Analyzed <timestamp> ..."
line is still stripped before hashing.
"""
from __future__ import annotations
import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
TARGETS = ["metrics_summary.md", "headline_check.md", "protocol_exhibit.md",
           "threats_to_validity.md", "appendix/data_availability.md"]
TARGET_DIRS = ["figures", "tables"]
# Provenance log only — changes every run via datetime.now(); ignore for equality.
_ANALYZED_LINE = re.compile(r"^- Analyzed .+\n?", re.MULTILINE)


def _bytes_for_hash(p: Path) -> bytes:
    data = p.read_bytes()
    if p.name == "metrics_summary.md":
        text = data.decode("utf-8")
        text = _ANALYZED_LINE.sub("", text)
        return text.encode("utf-8")
    return data


def sha(p: Path) -> str:
    return hashlib.sha256(_bytes_for_hash(p)).hexdigest()


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


def run_analyze(pass_label: str) -> subprocess.CompletedProcess:
    print(f"  -> launching analyze.py ({pass_label}); bootstrap may take several minutes...",
          flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, "src/analyze.py"], cwd=_HERE,
                          capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        print(f"  !! analyze.py failed in {elapsed:.1f}s (exit {proc.returncode})",
              flush=True)
        if proc.stdout:
            print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
        if proc.stderr:
            print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n")
        raise RuntimeError(f"analyze.py failed (exit {proc.returncode})")
    # Surface analyze console summary (verdict / hashes) without flooding.
    for line in (proc.stdout or "").splitlines():
        if line.startswith(("VERDICT:", "Input hashes:", "Analysis started", "Wrote ")):
            print(f"     {line}", flush=True)
    print(f"  -> analyze.py finished in {elapsed:.1f}s", flush=True)
    return proc


def main():
    if not (_HERE / "runs.csv").exists():
        print("No runs.csv — run Phase 2 first.")
        return 1

    print("Replication check: two analyze passes + hash compare (console only).",
          flush=True)
    t_all = time.perf_counter()

    print("[1/4] Running analyze.py (pass 1) — regenerating figures/tables...",
          flush=True)
    try:
        run_analyze("pass 1")
    except RuntimeError:
        return 1

    print("[2/4] Snapshotting outputs after pass 1...", flush=True)
    t0 = time.perf_counter()
    first = snapshot()
    print(f"  -> hashed {len(first)} outputs in {time.perf_counter() - t0:.2f}s",
          flush=True)

    print("[3/4] Running analyze.py (pass 2) — regenerating again...", flush=True)
    try:
        run_analyze("pass 2")
    except RuntimeError:
        return 1

    print("[4/4] Snapshotting pass 2 and comparing hashes...", flush=True)
    t0 = time.perf_counter()
    second = snapshot()
    keys = sorted(set(first) | set(second))
    diffs = [k for k in keys if first.get(k) != second.get(k)]
    print(f"  -> compared {len(keys)} outputs in {time.perf_counter() - t0:.2f}s",
          flush=True)

    ok = not diffs
    mark = "✔" if ok else "✖"
    status = "YES" if ok else "NO"

    L = ["# Replication check\n",
         f"- outputs compared: {len(keys)}",
         f"- byte-identical: {len(keys) - len(diffs)}/{len(keys)}",
         f"- deterministic: {mark} {status}\n"]
    if diffs:
        L.append("## Non-identical outputs (fix nondeterminism)\n")
        for k in diffs:
            L.append(f"- `{k}`: {first.get(k)} vs {second.get(k)}")
            print(f"  {mark} DIFF: {k}", flush=True)
    else:
        L.append("All Phase-3 outputs reproduce byte-for-byte from (runs.csv, config.yaml).")
        L.append("\n_Note: `metrics_summary.md` stamps input SHA-256 hashes; any legacy "
                 "wall-clock `Analyzed <timestamp>` line is excluded from the hash._")
    (_HERE / "replication_check.md").write_text("\n".join(L) + "\n")

    total = time.perf_counter() - t_all
    line = (f"{mark} Deterministic: {status} "
            f"({len(keys)-len(diffs)}/{len(keys)} identical). Wrote replication_check.md")
    print("", flush=True)
    if sys.stdout.isatty():
        # Bold green on pass, bold red on fail (ANSI); plain text if redirected.
        color = "\033[1;32m" if ok else "\033[1;31m"
        print(f"{color}{line}\033[0m", flush=True)
    else:
        print(line, flush=True)
    print(f"Total elapsed: {total:.1f}s", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
