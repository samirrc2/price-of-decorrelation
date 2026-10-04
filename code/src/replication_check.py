"""Phase 3 replication check — analyze.py must be byte-identical on re-execution.

Runs analyze.py twice into one timestamped results/ folder, SHA-256s every
generated output, and diffs the two passes. Writes replication_check.md there.
Exit 0 iff all outputs are byte-identical.
"""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import io_paths

_HERE = io_paths.repo_root()
TARGETS = ["metrics_summary.md", "headline_check.md", "protocol_exhibit.md",
           "threats_to_validity.md", "appendix/data_availability.md"]
TARGET_DIRS = ["figures", "tables"]
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


def snapshot(out: Path) -> dict[str, str]:
    result = {}
    for t in TARGETS:
        p = out / t
        if p.exists():
            result[t] = sha(p)
    for d in TARGET_DIRS:
        for p in sorted((out / d).glob("*")):
            result[f"{d}/{p.name}"] = sha(p)
    return result


def run_analyze(pass_label: str, out: Path) -> subprocess.CompletedProcess:
    print(f"  -> launching analyze.py ({pass_label}); bootstrap may take several minutes...",
          flush=True)
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["POD_OUT_DIR"] = str(out)
    env["PYTHONPATH"] = f"{io_paths.code_root() / 'src'}:{env.get('PYTHONPATH', '')}"
    proc = subprocess.run([sys.executable, "src/analyze.py"], cwd=str(io_paths.code_root()),
                          capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        print(f"  !! analyze.py failed in {elapsed:.1f}s (exit {proc.returncode})",
              flush=True)
        if proc.stdout:
            print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
        if proc.stderr:
            print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n")
        raise RuntimeError(f"analyze.py failed (exit {proc.returncode})")
    for line in (proc.stdout or "").splitlines():
        if line.startswith(("VERDICT:", "Input hashes:", "Analysis started",
                            "Wrote ", "Output dir:")):
            print(f"     {line}", flush=True)
    print(f"  -> analyze.py finished in {elapsed:.1f}s", flush=True)
    return proc


def main():
    runs = io_paths.resolve_runs_csv()
    # Prefer config path if set and exists
    import yaml
    cfg = yaml.safe_load(io_paths.default_config_path().read_text())
    runs = io_paths.resolve_runs_csv(cfg["paths"]["runs_csv"])
    if not runs.exists():
        print(f"No {runs} — place confirmatory dataset under data/confirmatory/.")
        return 1

    out = io_paths.new_timestamped_results_dir(runs_csv=runs)
    os.environ["POD_OUT_DIR"] = str(out)
    print(f"Replication check: two analyze passes into {out}",
          flush=True)
    t_all = time.perf_counter()

    print("[1/4] Running analyze.py (pass 1) — regenerating figures/tables...",
          flush=True)
    try:
        run_analyze("pass 1", out)
    except RuntimeError:
        return 1

    print("[2/4] Snapshotting outputs after pass 1...", flush=True)
    t0 = time.perf_counter()
    first = snapshot(out)
    print(f"  -> hashed {len(first)} outputs in {time.perf_counter() - t0:.2f}s",
          flush=True)

    print("[3/4] Running analyze.py (pass 2) — regenerating again...", flush=True)
    try:
        run_analyze("pass 2", out)
    except RuntimeError:
        return 1

    print("[4/4] Snapshotting pass 2 and comparing hashes...", flush=True)
    t0 = time.perf_counter()
    second = snapshot(out)
    keys = sorted(set(first) | set(second))
    diffs = [k for k in keys if first.get(k) != second.get(k)]
    print(f"  -> compared {len(keys)} outputs in {time.perf_counter() - t0:.2f}s",
          flush=True)

    ok = not diffs
    mark = "✔" if ok else "✖"
    status = "YES" if ok else "NO"

    def _rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(io_paths.repo_root().resolve()))
        except Exception:
            return str(p)

    L = ["# Replication check\n",
         f"- output dir: `{_rel(out)}`",
         f"- data: `{_rel(runs)}`",
         f"- data date: `{io_paths.infer_data_date(runs) or 'unknown'}`",
         f"- outputs compared: {len(keys)}",
         f"- byte-identical: {len(keys) - len(diffs)}/{len(keys)}",
         f"- deterministic: {mark} {status}\n"]
    if diffs:
        L.append("## Non-identical outputs (fix nondeterminism)\n")
        for k in diffs:
            L.append(f"- `{k}`: {first.get(k)} vs {second.get(k)}")
            print(f"  {mark} DIFF: {k}", flush=True)
    else:
        L.append("All Phase-3 outputs reproduce byte-for-byte from "
                 "(dated data/*/runs.csv, config.yaml).")
        L.append("\n_Note: `metrics_summary.md` stamps input SHA-256 hashes; any legacy "
                 "wall-clock `Analyzed <timestamp>` line is excluded from the hash._")
    (out / "replication_check.md").write_text("\n".join(L) + "\n")
    io_paths.point_latest_symlink(out)

    total = time.perf_counter() - t_all
    line = (f"{mark} Deterministic: {status} "
            f"({len(keys)-len(diffs)}/{len(keys)} identical). "
            f"Wrote {_rel(out)}/replication_check.md")
    print("", flush=True)
    if sys.stdout.isatty():
        color = "\033[1;32m" if ok else "\033[1;31m"
        print(f"{color}{line}\033[0m", flush=True)
    else:
        print(line, flush=True)
    print(f"Total elapsed: {total:.1f}s", flush=True)
    print(f"Latest -> {_rel(out)}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
