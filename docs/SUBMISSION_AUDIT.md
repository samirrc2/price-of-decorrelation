# Code Ocean Submission Audit — "The Price of De-correlation"

**Verdict: the 2026-08-07 audit below is SUPERSEDED. Read this section first.**

That audit was accurate for the capsule as originally submitted, and it is retained as a record
of it. It does not describe the revised article. The reviewer revision added four analysis arms
that the audited capsule contains no code for at all — error correlation (phi) under both
treatments of HOLD, the two-way crossed cluster bootstrap, selective prediction with AURC, and
the pre-registered cross-domain replication on 537 MMLU items — along with every verification
gate. Nothing in the audited capsule can produce those numbers.

Current state, audited 2026-10-04 at the commit that carries this file:

- The capsule is assembled by `code/scripts/build_capsule.sh`, from `git archive HEAD` rather
  than from the working tree, and the script runs the capsule's own entry point and diffs the
  claims it produces against the committed `claims.json` key by key. A capsule that is not
  proven to run does not get built.
- `make_manifest.py --capsule` pins the inputs a `/code` + `/data` mount must carry. That list
  was six entries stale after the revision and is now 13, covering the clinical replication, its
  ground truth and serialized inputs, the capability-matched control, the temperature arm, the
  pilot gate and the frozen grid. Each addition was fault-injected: hiding any one of them fails
  the gate.
- Twelve gates guard the article and the response letter: every number in both bound to one
  claim, every section and float pointer resolved, every change claim checked against the
  `as-submitted` tag, the reference numbering, the figures against the analysis output, and the
  freeze timestamps against the receipts.
- The document gates cannot run inside a capsule — there is no manuscript and no git history —
  and they exit 2, "not checkable", never 0.
- `cache/` and `data/raw/` are absent from the capsule by construction: both are gitignored, the
  analysis is a function of the frozen `runs.csv` files, and every one of them is verified
  against `data/MANIFEST.sha256` before anything is computed.

DOI `10.24433/CO.9524962.v1` is the audited August capsule and is superseded. The revision is
published as `10.24433/CO.9524962.v2`, built from the current commit by
`code/scripts/build_capsule.sh`, and that is the DOI `paper/main.tex` and `README.md` now cite.

---

# Original audit, 2026-08-07 (superseded, retained as a record)

**Verdict at that time: SUBMISSION-READY.** The capsule reproduced the paper's confirmatory
results byte-for-byte from frozen data, offline, with no secrets and a fixed deterministic seed
path.

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
