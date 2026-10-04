# Code Ocean Submission Audit — "The Price of De-correlation"

**Verdict: SUBMISSION-READY.** The capsule reproduces the paper's confirmatory results
byte-for-byte from frozen data, offline, with no secrets and a fixed deterministic seed path.
Audited on 2026-08-07.

## 1. Reproducibility (the headline)
- Entry point `code/run` → `code/scripts/reproduce.sh --data data/confirmatory/20260704`
  → `analyze.py` (offline).
- Ran end-to-end twice via the built-in replication check: **13/13 outputs byte-identical**,
  `deterministic: ✔ YES`, **exit code 0**.
- Primary result stable across passes: **Δκ(HOM−HET) = 0.3363, 95% CI [0.3035, 0.3689], VERDICT
  CONFIRMED**.
- Control arm and temperature check regenerate in the same run (CONFIRMED).

## 2. Data integrity
- `data/confirmatory/20260704/runs.csv` SHA-256 **matches** `dataset_manifest.json`
  (`8a1f5fc7…5c0ee1`). Config hash stamped in every `metrics_summary.md` (`89d9ae44…`).
- All datasets needed for the full analysis are present offline: confirmatory (1 CSV), control
  (1 CSV), temperature_robustness_small (3 CSVs).
- Accuracy proxy uses the bundled cache `data/datacache/forward_returns.json`; `yfinance` is
  **only** a fallback if the cache is absent (it is present), so the run needs **no network**.

## 3. No secrets, no live calls in the reproduction path
- `analyze.py` imports only `csv, math, yaml` + local modules — no `requests`/`openai`/`genai`.
- Provider API code lives solely in `agent.py` (collection path), which is not exercised by
  `run`. Keys are read from an external `keys.env` (git-ignored, outside the capsule); a
  `PILOT_MOCK=1` offline stub exists for the collection path.
- Tracked-file secret scan (sk-…, AIza…, xai-…, api_key=…): **none**. No `.env`/`.pem`/key file
  is tracked (`code/src/secrets.py` is the loader module, contains no keys).

## 4. One fix applied during audit
- `code/src/io_paths.py :: point_latest_symlink` called `latest.unlink()`, which raises
  `IsADirectoryError` if `results/latest` already exists as a real directory. Made robust
  (symlink/file → `unlink`; directory → `shutil.rmtree`) so the run exits 0 in every
  environment. On Code Ocean `/results` starts empty, so this never fired there, but the fix
  removes a local-repro footgun. **This is the only code change.**

## 5. Capsule structure (Code Ocean layout)
- `code/run` (executable, `-rwx`) — entry point.
- `environment/Dockerfile` — Code Ocean base image `py-r:python3.12.8-R4.4.2…ubuntu22.04` +
  pinned pip deps (numpy 2.2.6, pandas 2.2.3, matplotlib 3.11.1, pyyaml 6.0.3, …).
- `data/` — frozen CSVs + manifests + cache (81 MB).
- `metadata/metadata.yml` — `metadata_version: 1`, title, description, authors (Samir
  Chincholikar, Robin Chawla). Valid.
- `LICENSE` — MIT. `code/tests/` — `test_metrics.py`, `test_stats.py`.
- `.gitignore` excludes `.venv/`, `results/`, `data/raw/`, `cache/`, secrets, LaTeX build.

## 6. Notes (harmless, no action needed)
- `results/` is git-ignored and regenerated each run into `/results` on Code Ocean; local run
  artifacts under `results/` are not part of the tracked capsule.
- `archive/` (old pilots) ships for provenance; documented in `archive_manifest.md`. Remove
  before upload if a leaner capsule is preferred.
- `metadata.yml` is minimal-but-valid; a corresponding-author line can be added in the Code
  Ocean UI at submission.

## 7. How a reviewer reproduces it
On Code Ocean, click **Reproducible Run** (executes `code/run`). Locally:
```bash
bash code/run
# or: bash code/scripts/reproduce.sh --data data/confirmatory/20260704
```
Outputs land in `results/latest/` (figures/, tables/, metrics_summary.md, replication_check.md).
