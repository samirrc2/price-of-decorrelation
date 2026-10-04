# Threats to validity

**Ticker clustering.** The 50 tickers are stratified across 11 GICS sectors, but names within a sector co-move; our CIs use a cluster bootstrap resampling tickers to respect this, yet residual cross-sector correlation could still narrow intervals.

**Date-regime coverage.** Eight 2026 dates span AI-capex and energy supply-shock regimes, but eight points cannot represent all market states; agreement may be regime-dependent in ways this grid under-samples.

**Model-version pinning.** Providers silently update model strings; we pin exact strings in model_manifest.md and treat the hashed runs.csv as the dataset, so results are reproducible from data even after the live models move.

**Single-run data collection.** Raw data is collected once; there is no re-collection to average over provider-side drift within the window.

**Accuracy axis underpowered.** The study is powered for κ, not for directional accuracy; the forward-return hit-rate is descriptive with wide binomial CIs and must not be read as an alpha claim.

**Generalization.** Findings pertain to these three specific ensemble recipes and this task/prompt; other tasks, sizes, or provider mixes may differ.
