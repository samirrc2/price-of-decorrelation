# Pre-registration amendments — The Price of De-correlation

Post-freeze additions to the pre-registered design. The original pre-registration is
`docs/preregistration.md`, frozen 2026-07-03 at commit `259de7814` with per-file SHA-256 in
`docs/freeze_receipt.md`. Each entry below records what was added, why, when, and whether it
was declared before or after the data for that arm existed — because that distinction is
what a reader needs in order to weight it.

## What the original pre-registration covers

Confirmed by reading `docs/preregistration.md`, not by recollection:

| Status | Endpoint |
|---|---|
| **Primary** | Δκ(HOM − HET), ticker-clustered bootstrap, decision rule stated in advance |
| **Pre-registered secondary** | Δκ(HOM − HET-LITE) and Δκ(HET-LITE − HET) |
| **Pre-registered secondary** | the κ-and-cost frontier over heterogeneity levels {0, 1, 3} |
| **Descriptive only, declared as such** | cost per ensemble-decision, per-sector κ, the provider-pair agreement matrix, and the accuracy proxy (underpowered by design) |

Everything in the amendments below is therefore an addition, not a pre-registered test, with
the single documented exception of AMENDMENT #3.

## AMENDMENT #1 — capability-matched control arm (HET-SameTier)

**Added** 2026-07-23 (commit `88fa8f13a`), **after** the confirmatory data existed.

**What.** A fourth configuration drawing all five agents from one capability tier across
providers, with its own capture under `data/control/`, analysed by `code/src/control_kappa.py`.

**Why.** The confirmatory contrast varies provider AND capability tier together, so a
reviewer can read the 0.3363 effect as a capability artifact rather than a provider
one. This arm holds the tier fixed.

**Result.** Δκ(HOM − HET-SameTier) = 0.3153, 95% CI [0.2883, 0.3414], which is 94% of the primary effect with the interval excluding zero.

**Status.** Post-hoc confirmatory-style arm with a stated decision rule (CI excludes zero).
It is reported as a control, not as a pre-registered endpoint.

## AMENDMENT #2 — temperature-robustness subgrid

**Added** 2026-07-23 (commit `88fa8f13a`), **after** the confirmatory data existed.

**What.** A small subgrid (8 tickers × 2 dates × 3 configurations × 3 runs) re-collected at
T = 0.0, 0.7 and 1.0, under `data/temperature_robustness_small/`, analysed by
`code/src/temp_analyze.py`. The confirmatory study fixes T = 0.7.

**Why.** Agreement could be an artifact of one decoding temperature.

**Result.** Δκ(HOM − HET) = 0.299 at T=0.0, 0.509 at T=0.7 and 0.385 at T=1.0; positive with the CI excluding zero at every measured temperature, and the
HOM ≥ HET-LITE ≥ HET ordering holds throughout.

**Status and limits.** Explicitly **not** a full temperature study: the subgrid is small and
its intervals are correspondingly wide. It establishes that the sign and ordering are not a
T = 0.7 artifact, nothing more. Reported as such.

## AMENDMENT #3 — cross-domain replication (MMLU medical decisions)

**Added** 2026-09-29 (commit `2bb28175b`), and — unlike every other amendment here —
**pre-registered before any data for it was collected**.

**What.** The same three configurations on 537 four-option MMLU items drawn from
`professional_medicine`, `college_medicine`, `medical_genetics`, `anatomy` and
`clinical_knowledge`. Design, prediction, predicted magnitude and decision rule are in
`docs/preregistration_mmlu.md`; the freeze receipt `docs/freeze_receipt_mmlu.md` records
2026-09-29T14:47:54Z, **before the first API call for this arm**, with the item set and
config SHA-256 pinned.

**Why.** Reviewers objected that one financial task — with accuracy near chance and label
marginals that shift by configuration — cannot establish a general principle.

**Result.** Over 537 items, Δκ = 0.0719 and Δφ = 0.3927. The de-correlation replicates on a domain where accuracy is
well above chance and labels are balanced by construction.

**Status.** Pre-registered for this arm, with the prediction recorded in advance and the
result reported as it came out.

## AMENDMENT #4 — reviewer-requested analyses on frozen data

**Added** 2026-09-29 (commit `24a808606`), **after** all data existed. Every item is a
re-analysis of already-frozen captures; no new collection, no API spend.

**What**, each keyed to the comment it answers:

| Analysis | Answers | Where |
|---|---|---|
| Two-way and date-clustered bootstraps | whether the interval depends on the resampling unit | `results/revision_metrics.json` |
| Error-correlation φ (scored and strict) | agreement vs correlated *error* | `results/revision_metrics.json` |
| Unanimous-and-incorrect rate | the downstream cost of manufactured consensus | `results/revision_metrics.json` |
| Independence by pair type | same-model vs different-model agreement | `results/revision_metrics.json` |
| Selective prediction (risk–coverage, AURC) | whether conviction is usable for abstention | `results/revision_metrics.json` |
| Agreement robustness (Krippendorff α, Gwet AC1) | whether the ordering survives a different statistic | `results/latest/reviewer_metrics.md` |
| Capability-matched pair contrast (MMLU) | provider vs capability, holding member accuracy fixed | `results/mmlu_replication.json` |

**Clustering result.** The point estimate is identical across resampling units (0.3363); only the interval widens, from [0.3035, 0.3689] over 100 equity clusters to [0.2786, 0.3877] two-way. Every interval excludes zero. The equity row reproduces the primary endpoint's interval exactly, which it had not previously done: that bootstrap treated a draw as a SET of clusters, so an equity drawn twice counted once and each draw used only the ~63 distinct equities of a 100-draw multiset. That is subsampling rather than a cluster bootstrap and it understated the variance, giving [0.3131, 0.3628] for what the manuscript presented as the same estimand as the primary [0.3035, 0.3689]. Multiplicity is now honoured and the equality is asserted in code.

**Capability-matched result.** Δφ = 0.3471, 95% CI [0.2070, 0.5073]: same-provider φ 0.9537 against cross-provider 0.6066 at member accuracies 0.951 and 0.955.

**Status.** All exploratory and post-hoc, and labelled as such in the article. They are
re-analyses of frozen data, so they cannot be selected on by re-collection — but they were
chosen after seeing the primary result and must be read accordingly.

**Provenance correction (2026-10-01).** The capability-matched contrast was asserted in the
manuscript before any code computed it: the member accuracies, both φ values, their
difference and its CI existed only in the LaTeX source. `code/src/analyze_mmlu.py` now
computes it from the frozen MMLU capture and reproduces every published figure exactly.
Doing so corrected the estimator: a single same/cross *slot* pair gives φ 0.612, whereas the
published contrast pools the two google–xai slot pairs into a provider-level comparison —
the correct unit for a provider-level claim — giving 0.6066. The pooling is now explicit in
the code and the selection rule is recorded in the output.

## Scope note

No amendment modifies the primary endpoint, its estimator, the frozen confirmatory capture,
or the decision rule. The primary result is unchanged throughout: Δκ(HOM − HET) = 0.3363, 95% CI [0.3035, 0.3689], verdict CONFIRMED, over 54,000 usable calls.

Every value in this file is regenerated by `bash reproduce.sh` and gated: `check_claims.py`
and `check_coverage.py` fail the run if a reported number disagrees with the analysis.
