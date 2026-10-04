# Reviewer-hardening re-analysis (frozen data; post-hoc, exploratory)

## Agreement robustness — three statistics agree on the ordering

| config | Fleiss' kappa | Krippendorff's alpha | Gwet's AC1 |
|---|---|---|---|
| HOM | 0.5517 | 0.5518 | 0.7428 |
| HET-LITE | 0.3023 | 0.3025 | 0.5481 |
| HET | 0.2154 | 0.2155 | 0.3977 |

### BUY/HOLD/SELL marginals per config (prevalence check)

| config | BUY | HOLD | SELL | n calls |
|---|---|---|---|---|
| HOM | 0.212 | 0.709 | 0.079 | 18000 |
| HET-LITE | 0.282 | 0.653 | 0.064 | 18000 |
| HET | 0.358 | 0.556 | 0.085 | 18000 |

## Downstream benefit — manufactured consensus & tail risk

| config | scoreable decisions | unanimous rate | unanimous-&-directional-wrong rate | P(agree with majority \| majority wrong) |
|---|---|---|---|---|
| HOM | 3600 | 0.591 | 0.058 (n=210) | 0.824 |
| HET-LITE | 3600 | 0.315 | 0.030 (n=109) | 0.761 |
| HET | 3600 | 0.267 | 0.032 (n=114) | 0.636 |

_HOM unanimous-wrong rate is 1.84x the HET rate._

## Conviction calibration — per-agent directional hit-rate by conviction

| config | low (1-2) | mid (3) | high (4-5) |
|---|---|---|---|
| HOM | n/a (n=0) | 0.473 (n=912) | 0.446 (n=4323) |
| HET-LITE | 0.440 (n=25) | 0.520 (n=2179) | 0.449 (n=4035) |
| HET | 0.474 (n=232) | 0.507 (n=4806) | 0.435 (n=2948) |
