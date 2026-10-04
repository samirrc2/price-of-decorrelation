# Metrics summary — VERDICT: CONFIRMED

**Primary endpoint Δκ(HOM−HET) = 0.3363**, 95% CI [0.3035, 0.3689] (cluster bootstrap over tickers, 2000 draws, seed 42). κ_HOM=0.5517, κ_HET=0.2154.

Verdict rule: CONFIRMED if Δκ>0 and CI excludes 0; WEAKENED if Δκ>0 but CI includes 0; CONTRADICTED if Δκ≤0. Model set = OpenAI/Google/xAI (cross-provider; differs from the Claude-family pilot — stated explicitly).

- Calls logged (incl. retries): 94566  |  usable: 54000
- Inputs: `runs.csv` SHA-256=`8a1f5fc78482e87cb7ef5825c6a9425eb377bc80a7a60eb0febf61e70e5c0ee1` ; `configs/config.yaml` SHA-256=`3608d4982d50ffd8b10796e2ab824c4e163d896fc20b02a2893cb4b80126964f` (94566 rows). Grid COMPLETE: 54000/54000 cells present. (Historical deferred/retry rows: 3125, all backfilled.)

## Secondary Δκ contrasts

| contrast | Δκ | 95% CI |
|---|---|---|
| HOM − HET-LITE | 0.2494 | [0.2184, 0.2801] |
| HET-LITE − HET | 0.0870 | [0.0672, 0.1050] |

## Frontier (κ and cost vs heterogeneity level)

| config | level | κ | $/ensemble-decision |
|---|---|---|---|
| HOM | 0 | 0.5517 | 0.000648 |
| HET-LITE | 1 | 0.3023 | 0.001515 |
| HET | 3 | 0.2154 | 0.002835 |

## Within-run vs cross-run κ (nondeterminism check — must be ≈0)

| config | within | cross | within−cross |
|---|---|---|---|
| HOM | 0.5517 | 0.5510 | 0.0006 |
| HET-LITE | 0.3023 | 0.3500 | -0.0477 |
| HET | 0.2154 | 0.2893 | -0.0740 |

## Cost by provider
| provider | calls | total $ |
|---|---|---|
| google | 18820 | 10.7586 |
| openai | 72146 | 5.1313 |
| xai | 3600 | 2.1028 |

## Provider-pair direction agreement (descriptive)

| | google | openai | xai |
|---|---|---|---|
| **google** | 0.922 | 0.455 | 0.426 |
| **openai** | 0.455 | 0.798 | 0.625 |
| **xai** | 0.426 | 0.625 | n/a |

## Accuracy proxy — SECONDARY axis (study powered for κ, not accuracy)

- forward returns unavailable: no cache and yfinance/pandas not installed: cannot import name randbits

_(figures written to figures/). Tables in tables/ (CSV + LaTeX)._
