# Pre-registration — The Price of Diversity (cross-provider confirmatory study, v2)

Frozen at Phase 1. Hashes of the frozen artifacts are in `freeze_receipt.md`.
Raw data is collected exactly once (Phase 2); `analyze.py` is a pure, seeded
function of `(runs.csv, config.yaml)` and must produce byte-identical outputs on
every re-execution.

## Background

A Claude-family pilot (independent-draw, `archive/pilot_v1/`, Δκ = 0.113, 95% CI
[−0.27, 0.55]) established the measurement protocol and showed the effect is
directionally positive but not resolvable at 16 cells; the power projection called
for ~223 cells. This study runs a powered design (400 cells) on a **different,
cross-provider model set** (OpenAI / Google / xAI) with a third intermediate
configuration so the paper reports a κ-vs-heterogeneity **frontier**, not a
two-point comparison. The model-set change between pilot and study is deliberate
and is stated explicitly wherever results are reported.

## Configurations (5 agents each, temperature 0.7)

Heterogeneity level = number of non-OpenAI agents.

- **HOM** (level 0): 5 × `gpt-5.4-nano`
- **HET-LITE** (level 1): 4 × `gpt-5.4-nano` + 1 × `gemini-3.5-flash`
- **HET** (level 3): 2 × `gpt-5.4-nano` + 2 × `gemini-3.5-flash` + 1 × `grok-4.3`

Exact model strings, pricing, and knowledge cutoffs are frozen in
`model_manifest.md` (Phase 0, probe-verified).

## Primary endpoint

**Δκ = κ_HOM − κ_HET** on independent-draw agreement. Fleiss' κ is computed per
`(ticker, date)` cell across the 5 agents, pooled across the 3 runs, then averaged.
Uncertainty: **cluster bootstrap resampling TICKERS, 2,000 draws, fixed RNG seed = 42**
(`bootstrap_seed` in `config.yaml`). The finding stands on the primary point
estimate and its 95% CI. **No post-hoc subgroup inference.**

## Pre-registered secondary endpoints

- Δκ(HOM − HET-LITE) and Δκ(HET-LITE − HET), same method and bootstrap.
- Frontier presentation of κ and cost per ensemble-decision vs heterogeneity
  level {0, 1, 3}.

All other outputs are **descriptive only**: cost per ensemble-decision (incl. per
provider), per-sector κ, per-provider-pair agreement matrix, and the accuracy
proxy (secondary axis, underpowered by design).

## Decision rule

Report **CONFIRMED / WEAKENED / CONTRADICTED** against the pre-registered
expectation Δκ(HOM−HET) > 0, judged by the primary point estimate and whether its
95% CI excludes 0. Secondary contrasts are supporting, not gating.

## Seed protocol

Unique derived seed per agent per call: `seed = SHA256(master, run_seed, config,
ticker, date, agent_idx) mod 2^31` (`seed_mode: per_agent`). No shared sampling
context; the response cache is bypassed for unseeded draws and keyed on the
per-agent seed otherwise. **After the first cell, `verify_independence.py` confirms
same-model agents within a cell produce DIFFERING raw completions; abort and report
if identical** (guards against provider caching / sampling determinism, the artifact
that inflated the broken pilot from Δκ = 0.113 to 0.485).

## Grid

- **50 tickers**, stratified 4–5 per GICS sector across all 11 sectors
  (`config.yaml: sectors`; enumerated with sectors in `appendix/grid.csv`).
- **8 analysis dates**, each (a) strictly AFTER the latest knowledge cutoff in
  `model_manifest.md` and (b) ON/BEFORE 2026-06-01 so every 20-trading-day
  forward-return window has closed. Dates are spread across distinct 2026 market
  regimes (AI-capex expansion vs energy supply-shock), one-line justification per
  date in `config.yaml: date_regimes` and `appendix/grid.csv`.
- 400 cells × 3 configs × 3 runs × 5 agents = **18,000 calls**.
- Context snippets come solely from `/inputs`, containing only pre-date
  information (as-of date strictly before the analysis date); provenance is logged
  per call.

## Task

Each agent receives the same context snippet and returns STRICT JSON
`{"direction":"BUY|HOLD|SELL","conviction":1-5,"rationale":"<=30 words"}`. The exact
prompt text is frozen in `prompt_template.txt`.

## Replicability clause

Raw API data is collected once; `runs.csv` is the immutable dataset (set read-only
and SHA-256-hashed in `archive_manifest.md` at end of Phase 2). `analyze.py` reads
only `runs.csv` + `config.yaml`, with all randomness seeded, and must yield
byte-identical outputs on every re-execution (checked in `replication_check.md`).

## Analysis plan (Phase 3, $0 API)

Verdict line first; primary Δκ + CI; secondary contrasts; frontier (κ, cost) at
levels {0,1,3}; within-run vs cross-run κ gap for all three configs (must be ≈0);
cost table incl. per provider; descriptive per-sector, per-date, and
per-provider-pair tables; accuracy proxy with 95% binomial CIs. Publication assets
(figures 1–3, CSV+LaTeX tables) are generated deterministically inside `analyze.py`.
