# The Price of De-correlation

Computational artifact for the IEEE Access article:

**The Price of De-correlation: Quantifying the Agreement–Cost Trade-off in Heterogeneous Large Language Model Ensembles**

### Paper summary

Ensembles of LLM agents are often assumed to benefit from diversity, yet the amount of genuine de-correlation bought by cross-provider heterogeneity—and its inference cost—is rarely measured under a statistically powered, pre-registered design. This article runs **54,000 independent LLM calls** across three five-agent configurations (heterogeneity levels {0, 1, 3}) on a directional financial-analysis task (100 equities × 12 dates). Agreement is measured by Fleiss’ κ with ticker-clustered bootstrap confidence intervals.

**Main findings:**

- Heterogeneity de-correlates ensembles monotonically: κ falls from **0.552** (homogeneous) to **0.302** (one heterogeneous agent) to **0.215** (three), with primary effect **Δκ(HOM−HET) = 0.336** (95% CI [0.304, 0.369]) — *Confirmed*.
- The de-correlation costs a **~4.4×** inference premium per ensemble decision (explicit agreement–cost frontier).
- A capability-matched control recovers **~94%** of the effect (**Δκ = 0.315**), indicating the result is provider-driven rather than a capability-tier artifact.
- A shared-seed measurement artifact can inflate the effect by ~**4×**; the article contributes an independent-draw protocol that removes it.
- Average directional accuracy shows no reliable gain at this scale; exploratory analysis finds homogeneous ensembles produce confident, unanimous, wrong calls at ~**1.8×** the heterogeneous rate.

This repository is the frozen dataset and analysis pipeline that regenerates those numerical results and figures.

---

## 1. Artifact Identification

| Field | Value |
|-------|--------|
| **Article title** | The Price of De-correlation: Quantifying the Agreement–Cost Trade-off in Heterogeneous Large Language Model Ensembles |
| **Authors** | Samir Chincholikar, Robin Chawla |
| **Affiliations** | Independent researchers |
| **Code repository** | https://github.com/samirrc2/price-of-decorrelation |
| **Persistent DOI** | Code Ocean capsule submitted for review (public DOI pending; insert here when minted). Until then, use this GitHub repository. |
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

A [Code Ocean](https://codeocean.com/) compute capsule for this artifact has been **submitted for review** and will be **publicly available soon**, with a persistent DOI assigned after Code Ocean’s reproducibility verification.

| Status | Detail |
|--------|--------|
| Capsule | Prepared (keys-free Reproducible Run via `/code/run`) |
| Review | Submitted; awaiting Code Ocean verification |
| Public link / DOI | Not yet issued — will be added to this README and the manuscript when available |
| Until then | Reproduce from this GitHub repository (`bash reproduce.sh`) |

The capsule layout matches this repository: `/code` (including `run`, `src/`, `scripts/`), `/data` (frozen confirmatory CSV and configs), `/results` (analysis outputs), and `environment/Dockerfile`. The default Reproducible Run regenerates Phase-3 metrics and figures from the frozen dataset with **no API keys** and **no inference cost**.

After publication on Code Ocean, replace the placeholder in Section 1 (**Persistent DOI**) with the minted DOI.

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
| `data/control/runs.csv` | Capability-matched control dataset | included |
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

Faster single-pass regeneration (no hash compare):

```bash
bash reproduce.sh --analyze-only
```

Additional offline analyses on frozen data:

```bash
python code/src/reviewer_analysis.py    # Fig. 5 + reviewer_metrics.md → results/latest/
python code/src/control_kappa.py        # Section 5.8 → results/latest/control_result.md
python code/src/temp_analyze.py         # Section 5.9 → results/latest/temp_sweep_*.{md,tex}
```

### Execution time

See Section 3. The default `bash reproduce.sh` path is the recommended verification workflow. Re-running the full 54,000-call API collection is outside the default artifact exercise.

### Expected results

After `bash reproduce.sh`, `results/latest/metrics_summary.md` must report:

| Quantity | Expected value |
|----------|----------------|
| Verdict | CONFIRMED |
| Primary endpoint Δκ(HOM−HET) | 0.3363 |
| 95% CI (cluster bootstrap, 2,000 draws, seed 42) | [0.3035, 0.3689] |
| κ_HOM | 0.5517 |
| κ_HET-LITE | 0.3023 |
| κ_HET | 0.2154 |
| Inference-cost ratio (HOM → HET) | approximately 4.4× |

Generated figures under `results/latest/figures/` correspond to Article Figures 1, 3, and 4 as mapped above. Generated tables under `results/latest/tables/` correspond to the primary Δκ and frontier tables in the article.

After `bash reproduce.sh`, the console and `results/latest/replication_check.md` must report:

```text
✔ Deterministic: YES (13/13 identical)
```

These outputs are the same quantities reported in the article’s results section for the confirmatory study.

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
├── archive_manifest.md
├── docs/
├── archive/
├── paper/                       # reconstructed manuscript (optional)
│
├── environment/                 # Code Ocean compute environment
│   ├── Dockerfile               # pinned pip pkgs (matches working capsule)
│   └── README.md
│
├── metadata/
│   └── metadata.yml             # capsule title, description, authors
│
├── code/                        # capsule "code" (/code)
│   ├── run                      # Code Ocean Reproducible Run entry point
│   ├── src/                     # analyze.py, replication_check.py, …
│   ├── scripts/
│   │   └── reproduce.sh         # keys-free replication / analyze / scratch-run
│   ├── tests/
│   ├── requirements.txt
│   └── pytest.ini
│
├── data/                        # capsule "data" (/data)
│   ├── confirmatory/<YYYYMMDD>/runs.csv (+ latest →)
│   ├── control/
│   ├── temperature_robustness_small/<YYYYMMDD>/
│   ├── minipilot/
│   ├── raw/                     # gitignored
│   ├── configs/
│   ├── inputs/
│   ├── datacache/
│   └── appendix/
│
└── results/                     # capsule "results" (/results); gitignored
    ├── data-<dataDate>_run-<YYYYMMDD_HHMMSS>/
    └── latest -> <that folder>
```

**Code Ocean flow:** `/code/run` calls `reproduce.sh` on the frozen confirmatory CSV → writes under `/results/data-…_run-…/` (one folder per Reproducible Run; the replication check runs analyze twice *into that same folder* and hash-compares).

**Generated at run time** (safe to overwrite): everything under `results/`.  
**Default review dataset:** `data/confirmatory/latest` (currently `20260704`). New collections write a new dated folder.

### Reviewer quick start

```bash
git clone https://github.com/samirrc2/price-of-decorrelation.git
cd price-of-decorrelation
source code/scripts/activate_env.sh    # required once per shell: create/activate .venv + deps
bash reproduce.sh
```

Confirm that `results/latest/replication_check.md` reports Deterministic: YES, that `results/latest/metrics_summary.md` matches the expected values in Section 4, and that `results/latest/figures/` matches the corresponding article figures.
