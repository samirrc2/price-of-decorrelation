# The Price of De-correlation
### Quantifying the Agreement–Cost Trade-off in Heterogeneous Large Language Model Ensembles

**Samir Chincholikar and Robin Chawla**  
*IEEE Access* (2026)

[**Journal article**](https://doi.org/10.1109/ACCESS.2026.3749218) · [**Reproducibility capsule**](https://doi.org/10.24433/CO.9524962.v2) · [**Research guide**](https://samirrc2.github.io/price-of-decorrelation/)

## Overview

This study examines whether using models from different providers reduces agreement and shared errors in large language model (LLM) ensembles—and the inference cost of doing so. The preregistered financial experiment comprises **54,000 independent model calls** across three five-agent configurations, 100 equities, and 12 analysis dates. A separately preregistered evaluation on **537 clinical-knowledge items** examines whether the pattern extends beyond finance.

The analysis distinguishes agreement between agents (Fleiss’ κ), correlation between their errors (φ), and predictive accuracy. These quantities measure different properties of ensemble behavior.

### Key findings

- **Agreement decreases with heterogeneity.** Fleiss’ κ declines from **0.552** in the homogeneous ensemble to **0.302** with one alternative-provider agent and **0.215** with three. The preregistered HOM–HET contrast is **0.336** (95% CI: 0.304–0.369).
- **Shared-error dependence also decreases.** Binary-error correlation falls from **0.984** to **0.530**, a difference of **0.454** (95% CI: 0.376–0.534). Lower agreement and lower error correlation are related but distinct findings.
- **Heterogeneity carries a measurable cost.** The fully heterogeneous configuration costs approximately **4.4×** as much per ensemble decision in metered inference charges.
- **The result is not explained by capability tier alone.** An approximately capability-matched comparison retains about **94%** of the primary agreement contrast. Provider identity remains confounded with model-specific characteristics, so a provider-only causal effect is not identified.
- **Independent generation matters.** A shared-seed pilot inflated the measured agreement contrast by roughly **4×** relative to an independent-draw protocol.
- **Better average accuracy is not established.** Directional prediction shows no statistically reliable improvement at the study's power. An exploratory analysis finds approximately **1.8×** as many unanimous incorrect decisions in homogeneous ensembles, but that analysis is post hoc and hypothesis-generating.

## Reproducibility

This repository contains the frozen datasets, study configurations, preregistration records, analysis code, and validation procedures used to reproduce the paper's numerical findings and figures. The default reproduction workflow uses archived model responses: **no LLM API keys or new inference calls are required**.

For an executable archival environment, use the [Code Ocean capsule](https://doi.org/10.24433/CO.9524962.v2). The [research guide](https://samirrc2.github.io/price-of-decorrelation/) provides a topic-organized discussion of the findings and limitations. The published IEEE Access article is the authoritative source for the research.

---

## 1. Artifact Identification

| Field | Value |
|-------|--------|
| **Article** | *The Price of De-correlation: Quantifying the Agreement–Cost Trade-off in Heterogeneous Large Language Model Ensembles* |
| **Authors** | Samir Chincholikar; Robin Chawla |
| **Affiliation** | Independent researchers |
| **Journal** | IEEE Access (2026) |
| **Article DOI** | [10.1109/ACCESS.2026.3749218](https://doi.org/10.1109/ACCESS.2026.3749218) |
| **Manuscript** | ACCESS-2026-50920 |
| **Research repository** | https://github.com/samirrc2/price-of-decorrelation |
| **Code Ocean capsule DOI** | [10.24433/CO.9524962.v2](https://doi.org/10.24433/CO.9524962.v2) |
| **Contact** | Samir Chincholikar: samir.chincholikar@gmail.com; Robin Chawla: robin.chawla.cse14@iitbhu.ac.in |
| **ORCID** | Samir Chincholikar: https://orcid.org/0009-0007-2779-3492; Robin Chawla: https://orcid.org/0009-0007-2807-3948 |

### Abstract and role of the artifact

This artifact accompanies a pre-registered study of **cross-provider model heterogeneity** in five-agent LLM ensembles on a directional equity-analysis task. The confirmatory experiment comprises **54,000 independent LLM calls** (100 equities × 12 dates × 3 ensemble configurations × 3 runs × 5 agents) using models from OpenAI, Google, and xAI.

The artifact enables independent reproduction of the article’s computational results. Specifically, it provides:

1. The frozen confirmatory dataset (`data/confirmatory/latest/runs.csv`) and study configuration (`data/configs/config.yaml`).
2. A deterministic analysis pipeline that regenerates Fleiss’ κ estimates, Δκ contrasts with cluster-bootstrap confidence intervals, the agreement–cost frontier, and publication figures and tables under `results/<timestamp>/`.
3. Pre-registration and freeze records, plus the pilot archives that document the independent-draw measurement protocol.
4. Configurations and analysis scripts for the capability-matched control and temperature-sensitivity robustness studies.

**Default workflow (this README):** regenerate Phase-3 analysis outputs from the frozen dataset. This path requires **no LLM API keys** and incurs **no inference cost**. Re-collecting the 54,000 API calls is optional, incurs cost (~USD 90), and is **not required** to verify the numerical claims in the article.

---

## Code Ocean

A [Code Ocean](https://codeocean.com/) compute capsule for this artifact is available at
[https://doi.org/10.24433/CO.9524962.v2](https://doi.org/10.24433/CO.9524962.v2)
(DOI `10.24433/CO.9524962.v2`).

| Field | Detail |
|--------|--------|
| Reproducible Run entry point | `/code/run` → `bash code/scripts/reproduce.sh --data data/confirmatory/20260704` |
| Environment | `environment/Dockerfile` (Code Ocean `py-r` base, pinned pip packages) |
| API keys | **none required**; the default path is keys-free and costs nothing |
| Runtime | ~5–8 minutes |
| Local equivalent | `bash reproduce.sh` |

### Capsule mounts

| Mount | Contents |
|-------|----------|
| `/code` | `run`, `src/`, `scripts/`, `tests/`, `requirements.txt` |
| `/data` | the frozen captures (confirmatory, clinical, control, temperature, pilot), `configs/`, `inputs/`, `inputs_mmlu/`, `datacache/`, `MANIFEST.sha256`, clinical ground truth |
| `/results` | written by the run: `claims.json`, metrics, tables, figures, the supporting-arm reports |
| `docs/` + root | the two freeze receipts, both frozen pre-registrations, `PREREGISTRATION_AMENDMENTS.md`, `DATA_MANIFEST.md` — the evidence the article points the reader at |

The capsule is assembled and self-verified by `bash code/scripts/build_capsule.sh`, which builds
from `git archive HEAD` rather than the working tree, runs the capsule's own entry point inside
the staged directory, diffs the claims it produces against the committed `claims.json` key by
key, re-checks the freeze receipts against the artifacts they attest to, and fails if any gate
reports an error instead of "not checkable" in a capsule layout.

`/data/datacache/` is **not optional**. The analyses prefer its offline forward-return cache
and fall back to a live `yfinance` call without it — which would turn a keys-free offline
capsule into a network-dependent one. `make_manifest.py --capsule` asserts its presence, and
the run fails if it is missing.

### What a capsule can and cannot verify

A capsule mounts `/code` and `/data` only, so `paper/` is absent. The two gates that read the
manuscript report **not checkable here** and are skipped; everything that regenerates and
verifies the numbers runs in full. A capsule run therefore exits **0** on success.

| Gate | In a capsule |
|------|---|
| Determinism, input integrity, capsule completeness | runs |
| Robustness arms, supporting analyses, claims extraction | runs |
| Manuscript agreement (`check_claims.py`) | skipped — needs `paper/main.tex` |
| Manuscript provenance (`check_coverage.py`) | skipped — needs `paper/main.tex` |
| Unit tests | runs |

The capsule has been verified to produce **all 365 claims identically** to a full checkout,
with 10/10 shared artifacts byte-identical.

---

## 2. Artifact Dependencies and Requirements

### Hardware

| Resource | Requirement |
|----------|-------------|
| CPU | Standard laptop or workstation (analysis is CPU-bound, single process) |
| RAM | ≥ 4 GB (≥ 8 GB recommended) |
| Disk | ≥ 2 GB free (`data/confirmatory/latest/runs.csv` ≈ 53 MB; avoid cloning ignored `cache/` / `data/raw/`) |
| GPU | Not required |

### Operating system

- macOS, Linux, or Windows with WSL2
- `bash` required for the provided shell scripts
- Containerized review environments (e.g., Code Ocean): Linux

### Software

| Component | Requirement |
|-----------|-------------|
| Python | ≥ 3.10 (3.11, 3.12, or 3.13 accepted) |
| Shell | `bash` |
| Network | Not required for the default Phase-3 workflow |

### Software libraries

Dependencies are listed in `code/requirements.txt` (install with `pip install -r code/requirements.txt`). Primary packages:

- `pyyaml>=6.0`
- `numpy==2.2.6`
- `matplotlib>=3.7`
- `pandas==2.2.3`
- `requests>=2.31`
- `openai>=1.40`
- `google-genai>=0.3`
- `yfinance>=0.2.40`

Phase-3 analysis primarily requires PyYAML, NumPy, and Matplotlib. Pandas and yfinance are optional when `data/datacache/forward_returns.json` is present.

### Input data included with the artifact

| Path | Description | Approx. size |
|------|-------------|--------------|
| `data/confirmatory/latest/runs.csv` | Frozen confirmatory call log (54,000 usable rows) | 53 MB |
| `data/configs/config.yaml` | Frozen study configuration | &lt; 1 MB |
| `data/configs/prompt_template.txt` | Frozen prompt template | &lt; 1 MB |
| `data/datacache/prices.json` | EOD price cache | &lt; 1 MB |
| `data/datacache/forward_returns.json` | Forward-return signs for the accuracy proxy | &lt; 1 MB |
| `data/inputs/*.json` | Price-derived context snippets (1,200 cells) | included |
| `data/appendix/grid.csv` | Frozen experimental grid | included |
| `data/control/latest/runs.csv` | Capability-matched control dataset | 20 MB |
| `data/temperature_robustness_small/latest/runs_T*.csv` | Temperature-robustness check (small subgrid) | included |

**Integrity (frozen confirmatory dataset):**

```
data/confirmatory/latest/runs.csv SHA-256 =
8a1f5fc78482e87cb7ef5825c6a9425eb377bc80a7a60eb0febf61e70e5c0ee1
```

Recorded in `archive_manifest.md`.

### Optional dependencies (live re-collection only)

API credentials for OpenAI, Google Gemini, xAI, and Financial Modeling Prep are required **only** for live re-collection (`bash reproduce.sh --scratch-run …` or `code/src/orchestrator.py`). They are **not** required for the default reproduction path. Live runs **cost money** (API inference spend); the frozen confirmatory dataset is enough to verify the article’s numerical claims.

---

## 3. Artifact Installation and Deployment Process

### Time estimates

| Step | Typical duration |
|------|------------------|
| Install Python dependencies / create venv (first time) | 1–5 minutes |
| Activate an existing virtual environment | &lt; 5 seconds |
| Byte-identical replication check (`bash reproduce.sh`, default) | 5–20 minutes |
| Single analyze pass (`bash reproduce.sh --analyze-only`) | 1–5 minutes |
| Code Ocean Reproducible Run (`/code/run`) | ~3–5 minutes (observed) |

### Installation

**Required before any local `reproduce.sh` run:** activate the project environment. `reproduce.sh` does **not** create or activate a venv for you; if packages are missing it will exit with an install hint.

**Recommended (creates/reuses `.venv`, installs deps, activates):**

```bash
git clone https://github.com/samirrc2/price-of-decorrelation.git
cd price-of-decorrelation
source code/scripts/activate_env.sh
bash reproduce.sh
```

Do **not** run `./code/scripts/activate_env.sh` — it must be **sourced** so the venv stays active in your shell. Then run `bash reproduce.sh` (or `--analyze-only`, etc.) in that same shell.

**Equivalent manual setup:**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r code/requirements.txt
bash reproduce.sh
```

`reproduce.sh` and `code/run` set `PYTHONPATH` to `code/src` automatically once the env is active. On Code Ocean, packages come from `environment/Dockerfile` — no `activate_env.sh` step.

On some Linux distributions, install `python3-venv` (or the matching versioned package) if `python3 -m venv` is unavailable.

### Deployment / execution

No compilation step is required. From the repository root, with the env **already activated** (`source code/scripts/activate_env.sh`) and `data/confirmatory/latest/runs.csv` present:

| Goal | Command |
|------|---------|
| Prove byte-identical re-execution (default) | `bash reproduce.sh` |
| Regenerate figures/tables once (no compare) | `bash reproduce.sh --analyze-only` |
| Analyze a specific call dataset | `bash reproduce.sh --data data/confirmatory/latest --analyze-only` |
| Analyze only (environment already activated) | `POD_OUT_DIR=results/latest python code/src/analyze.py` |
| Replication check only | `python code/src/replication_check.py` |
| Code Ocean entry point | `/code/run` → `bash code/scripts/reproduce.sh --data data/confirmatory/20260704` |
| Live re-collection (optional; **not** required to verify the paper) | `bash reproduce.sh --scratch-run 48k` or `--scratch-run full` |

**Scratch / live runs:** `--scratch-run` calls live LLM APIs. You must supply your own API keys (OpenAI, Google Gemini, xAI; see Section 2). This **incurs real inference cost** (on the order of tens of USD for a partial grid; ~USD 90 for a full confirmatory-scale collection) and is **not** part of the default reproducibility check. Prefer the frozen CSV + `bash reproduce.sh` unless you intentionally want a new dataset.

`reproduce.sh` (repository root) delegates to `code/scripts/reproduce.sh`. Outputs land under `results/<timestamp>/` with `results/latest` pointing at the newest run.

---

## 4. Reproducibility of Experiments

### Experiment workflow

The default workflow reproduces **Phase 3** of the study: deterministic re-analysis of the frozen confirmatory dataset.

```text
data/confirmatory/latest/runs.csv + data/configs/config.yaml
        │
        ▼
  bash reproduce.sh
  (→ results/<timestamp>/ via analyze.py x2 + hash compare)
        │
        ├── figures/fig1_frontier.png (.svg)   → Article Fig. 1 (agreement–cost frontier)
        ├── figures/fig2_protocol.png          → Article Fig. 3 (measurement-trap / protocol)
        ├── figures/fig3_provider_heatmap.png  → Article Fig. 4 (provider agreement matrix)
        ├── tables/endpoints.csv /.tex         → Article Table 2 (Δκ contrasts)
        ├── tables/frontier.csv /.tex          → Article Table 4 (κ and cost by config)
        ├── metrics_summary.md                 → Verdict and primary numerical results
        └── replication_check.md               → Deterministic: YES (13/13 identical)
```

Stable path for readers: `results/latest/` (symlink to the newest timestamped folder).

### Gates

`reproduce.sh` does not merely regenerate outputs — it refuses to report success unless every
applicable gate passes. Each prints its own coverage count, so a gate that silently checked
nothing is visible rather than reassuring, and each was **fault-injected**: a defect was
planted and the gate confirmed to fail on it before being trusted to pass.

| Gate | Asserts | Would catch |
|---|---|---|
| Determinism | two analysis passes, 13 outputs hash-compared | order- or seed-dependence |
| `make_manifest.py --verify` | all 1,752 frozen inputs match their pinned SHA-256 | an input that changed, was regenerated, or vanished |
| `make_manifest.py --capsule` | the inputs a `/code`+`/data` mount cannot run without are present | a capsule that passes its hashes while missing the offline price cache — hashing proves what you have is unchanged, not that you have everything |
| `robustness_analysis.py`, `analyze_mmlu.py` | the robustness arms regenerate from frozen captures | a stale robustness or cross-domain number |
| `control_kappa.py`, `temp_analyze.py`, `agreement_analysis.py` | the control arm, temperature sweep and agreement-robustness tables regenerate | a supporting-arm number left behind by an older run |
| `make_claims.py` | 365 named claims extract from the regenerated outputs | an analysis that stopped emitting a number the paper cites |
| `check_claims.py` | `paper/main.tex` agrees with the analysis | a drifted figure, including a plausible near-miss; a machine-specific path in a committed output; a stale hash or path in `archive_manifest.md` |
| `check_coverage.py` | **every** numeric literal in `main.tex` traces to a claim, a documented transform, or a declared non-result | a manuscript number that no analysis produces — this is the gate that found five published figures with no generating code |
| `pytest code/tests` | metric and bootstrap primitives | a regression in κ, φ or the cluster bootstrap |

The last two run in opposite directions, and both are needed. `check_claims.py` asks whether
our claims appear in the manuscript; `check_coverage.py` asks whether every manuscript number
has provenance. Only the second can notice an assertion the artifact never computed.

Exit codes are a contract:

| Code | Meaning |
|------|---------|
| **0** | every gate that applies to this copy passed |
| **1** | a gate failed: an input is corrupt, or a reported number disagrees with the analysis |
| **2** | the analysis reproduced, but a gate that *should* apply here could not run. Never a pass. |

A `/code`+`/data` capsule has no `paper/`, so the two manuscript gates are correctly skipped
and the run still exits 0. A **full checkout** that cannot run them exits 2.

Verify the inputs or the provenance on their own, without a full run:

```bash
python code/src/make_manifest.py --verify     # 0 = all inputs intact, 1 = corrupt or missing
python code/src/make_manifest.py --capsule    # 0 = a capsule has everything it needs
python code/src/check_coverage.py             # 0 = every manuscript number has provenance
```

`DATA_MANIFEST.md` lists every pinned input with its size and SHA-256.
`results/latest/claims.json` is the machine-readable record of every number the paper may
assert. `SUBMISSION_ARTIFACT.md` summarises the locked values.

### Execution time

See Section 3. The default `bash reproduce.sh` path is the recommended verification workflow. Re-running the full 54,000-call API collection is outside the default artifact exercise.

### Expected results

`bash reproduce.sh` exits **0** only if every gate passes, so the run itself is the
verification — there is nothing to compare by eye.

**Primary endpoint** — `results/latest/metrics_summary.md`:

| Quantity | Expected value |
|----------|----------------|
| Verdict | CONFIRMED |
| Primary endpoint Δκ(HOM−HET) | 0.3363 |
| 95% CI (ticker-clustered bootstrap, 2,000 draws, seed 42) | [0.3035, 0.3689] |
| κ_HOM / κ_HET-LITE / κ_HET | 0.5517 / 0.3023 / 0.2154 |
| Secondary Δκ (HOM−HET-LITE) | 0.2494 [0.2184, 0.2801] |
| Secondary Δκ (HET-LITE−HET) | 0.087 [0.0672, 0.105] |
| Inference-cost ratio (HOM → HET) | ≈ 4.4× (4.375 from the frontier costs) |
| Usable calls / grid cells | 54,000 / 54,000 of 54,000 |

**Supporting arms** — regenerated by the same command, under `results/latest/`:

| Arm | File | Expected value |
|---|---|---|
| HET-SameTier capability control | `control_result.md` | Δκ = 0.3153 [0.2883, 0.3414] |
| Temperature robustness (T = 0.0 / 0.7 / 1.0) | `temp_sweep_result.md` | Δκ = 0.299 / 0.509 / 0.385 |
| Agreement robustness, HOM (Fleiss / Krippendorff / Gwet) | `reviewer_metrics.md` | 0.5517 / 0.5518 / 0.7428 |
| Cross-domain replication (MMLU, 537 items) | `../mmlu_replication.json` | Δκ = 0.0719, Δφ = 0.3927 |
| Capability-matched pair contrast | `../mmlu_replication.json` | Δφ = 0.3471 [0.2070, 0.5073] |
| Robustness analyses (clustering, selective prediction, pair types) | `../revision_metrics.json` | over 54,000 calls |
| Request accounting | `claims.json` | 94,566 requests; 40,566 unsuccessful = 40,544 rate-limit/quota + 22 transport/schema |

**Determinism** — the console and `results/latest/replication_check.md` must report:

```text
✔ Deterministic: YES (13/13 identical)
```

Figures under `results/latest/figures/` correspond to Article Figures 1, 3 and 4; tables under
`results/latest/tables/` to the primary Δκ and frontier tables.

Verified across **four consecutive runs of the same commit, plus a `/code` + `/data` capsule
run**: 15/15 result artifacts byte-identical between iterations, and 10/10 byte-identical
between capsule and full checkout.

### Out of scope for the default workflow

- Re-issuing live LLM API calls via `code/src/orchestrator.py`
- Any inference or API spend

---

## 5. Other Notes

- **Pre-registration and freeze records:** `docs/preregistration.md`, `docs/freeze_receipt.md`, `docs/model_manifest.md`
- **Operator run log (historical):** `docs/STUDY_RUN.md`
- **Pilot archives (measurement protocol):** `archive/pilot_v1/` and `archive/pilot_v1_broken_perRunSeed/`
- **Provenance in analysis outputs:** `results/latest/metrics_summary.md` records SHA-256 hashes of the call CSV and `data/configs/config.yaml`. Wall-clock time is printed to the console only and is not part of the hashed scientific content.
- **Repository layout:** `data/` = frozen API call logs; `results/<timestamp>/` = analysis outputs; `results/latest` symlink; top-level `reproduce.sh` entry point
- **Cleanup:** `bash code/scripts/cleanup_transient.sh` removes `data/raw/` and `cache/` (not call CSVs)
- **Manuscript source:** the IEEE Access PDF/LaTeX may be distributed separately; this artifact regenerates the computational figures and tables cited above. Optional: `bash code/scripts/build_paper.sh` builds `paper/main.pdf` from `results/latest` figures.
- **Issues and support:** GitHub Issues, or the author emails listed in Section 1

### Repository structure

```text
price-of-decorrelation/
├── README.md
├── LICENSE
├── reproduce.sh                 # → code/scripts/reproduce.sh
├── DATA_MANIFEST.md             # every pinned input: path, size, SHA-256
├── SUBMISSION_ARTIFACT.md       # the locked values, and what each gate would catch
├── archive_manifest.md          # the confirmatory dataset's pin, with a changelog
├── docs/                        # pre-registration, freeze receipts, model manifest
├── archive/                     # pilot archives (the independent-draw protocol)
├── paper/                       # manuscript source (absent from the capsule)
│
├── environment/                 # Code Ocean compute environment
│   ├── Dockerfile               # pinned pip packages (matches the working capsule)
│   └── README.md                # mounts, gates, exit-code contract
│
├── metadata/metadata.yml        # capsule title, description, authors
│
├── code/                        # capsule /code
│   ├── run                      # Code Ocean Reproducible Run entry point
│   ├── src/
│   │   ├── analyze.py           # primary endpoint, figures, tables
│   │   ├── replication_check.py # two passes + hash compare
│   │   ├── control_kappa.py     # HET-SameTier capability control
│   │   ├── temp_analyze.py      # temperature robustness
│   │   ├── agreement_analysis.py # agreement robustness, unanimity, hit rates
│   │   ├── robustness_analysis.py # clustering, selective prediction, pair types
│   │   ├── analyze_mmlu.py      # cross-domain + capability-matched contrast
│   │   ├── make_manifest.py     # pin and verify inputs; --capsule completeness
│   │   ├── make_claims.py       # extract every claim the paper may assert
│   │   ├── check_claims.py      # manuscript agreement, portability, document hashes
│   │   └── check_coverage.py    # every manuscript number must have provenance
│   ├── scripts/reproduce.sh     # keys-free replication / analyze / scratch-run
│   ├── tests/                   # metric and bootstrap unit tests
│   └── requirements.txt
│
├── data/                        # capsule /data
│   ├── MANIFEST.sha256          # machine-readable pins, verified on every run
│   ├── confirmatory/<YYYYMMDD>/runs.csv (+ latest →)
│   ├── control/                 # capability-matched control capture
│   ├── temperature_robustness_small/<YYYYMMDD>/
│   ├── mmlu/, inputs_mmlu/, mmlu_ground_truth.json
│   ├── minipilot/, appendix/
│   ├── configs/                 # frozen protocol: grid, models, estimands
│   ├── inputs/                  # serialized model inputs
│   ├── datacache/               # OFFLINE price cache — required, see Code Ocean above
│   └── raw/                     # gitignored, not needed to reproduce
│
└── results/                     # capsule /results; gitignored
    ├── data-<dataDate>_run-<YYYYMMDD_HHMMSS>/
    │   ├── claims.json          # every number the paper may assert
    │   ├── metrics_summary.md, replication_check.md, headline_check.md
    │   ├── control_result.md, temp_sweep_result.md, reviewer_metrics.md
    │   ├── figures/, tables/
    ├── revision_metrics.json    # reviewer analyses
    ├── mmlu_replication.json    # cross-domain + capability-matched
    └── latest -> <that folder>
```

**Code Ocean flow:** `/code/run` calls `reproduce.sh` on the frozen confirmatory CSV, writes
under `/results/data-…_run-…/` (one folder per Reproducible Run; the replication check runs
analyze twice *into that same folder* and hash-compares), then runs the gates.

**Generated at run time** (safe to overwrite): everything under `results/`. These files are
gitignored because they are rebuilt, not archived — and a fresh clone has been verified to
regenerate them byte-identically. `SUBMISSION_ARTIFACT.md` carries the same values in prose
for a reader who does not want to run the pipeline.

**Default dataset:** `data/confirmatory/latest` (currently `20260704`). New collections
write a new dated folder and never overwrite an existing one.

### Reproducing from a clean checkout

```bash
git clone https://github.com/samirrc2/price-of-decorrelation.git
cd price-of-decorrelation
source code/scripts/activate_env.sh    # once per shell: create/activate .venv + install deps
bash reproduce.sh
```

The last line of a successful run is:

```text
[reproduce] all gates passed
```

and `echo $?` is **0**. If it prints `INCOMPLETE` and exits 2, a gate that should apply here
could not run — that is not a pass. If any gate fails, the run exits 1 and names the
disagreement.

`reproduce.sh` selects an interpreter by **import capability**, not by name: an explicit `PY`,
then `./.venv/bin/python`, then `python3`, then `python` — the first that can import `yaml`,
`numpy` and `matplotlib`. To point it somewhere specific:

```bash
PY=/path/to/python bash reproduce.sh
```

Then confirm, in `results/latest/`:

- `replication_check.md` reports `Deterministic: YES (13/13 identical)`
- `metrics_summary.md` matches the primary endpoint table in Section 4
- `control_result.md`, `temp_sweep_result.md` and `reviewer_metrics.md` match the supporting-arm table
- `claims.json` holds 378 claims; `check_coverage.py` reported 161/161 literals traced and
  `check_binding.py` 291/291 numbers bound
- `figures/` matches the corresponding article figures
