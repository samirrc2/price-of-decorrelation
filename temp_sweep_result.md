# Temperature-robustness check (small subgrid; not a full temp study)

Subgrid: 8 tickers x 2 dates x 3 configs x 3 runs per temperature (same estimator and seeds as the main study; separate files).

| T | kappa_HOM | kappa_HET-LITE | kappa_HET | Delta-kappa(HOM-HET) | 95% CI | Delta-kappa(HOM-HET-LITE) |
|---|---|---|---|---|---|---|
| 0.0 | 0.332 | 0.172 | 0.033 | 0.299 | [0.160, 0.443] | 0.161 |
| 0.7 | 0.670 | 0.384 | 0.161 | 0.509 | [0.214, 0.777] | 0.286 |
| 1.0 | 0.533 | 0.275 | 0.148 | 0.385 | [0.194, 0.537] | 0.258 |

_Primary contrast robustness: Delta-kappa(HOM-HET) is positive with a 95% CI excluding zero at EVERY measured temperature: YES._
_Ordering HOM >= HET-LITE >= HET holds at every measured temperature: YES._
_Absolute kappa levels vary non-monotonically with T (kappa_HOM ranges 0.332-0.670); it is the de-correlation CONTRAST, not the absolute agreement, that is temperature-stable._
