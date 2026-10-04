# Metrics summary

- Calls logged: **480**  |  usable (ok + valid direction): **480**
- Unusable (API error or JSON parse failure): **0**

- Context snippet provenance: {'inputs_file': 480}

## 1. Within-ensemble agreement (Fleiss' κ, within-run, averaged)

| config | κ (avg) | per-run κ |
|---|---|---|
| HOM | 0.6349 | 0.7295, 0.6238, 0.5513 |
| HET | 0.5219 | 0.4758, 0.6299, 0.4599 |

**Δκ = κ_HOM − κ_HET = 0.1130**

> κ_HOM > κ_HET (positive Δκ) is the expected direction: homogeneous ensembles are more internally correlated. The pilot asks whether Δκ is large and stable enough to measure affordably.


### Cluster bootstrap 95% CI on Δκ (resample tickers)

- point Δκ (full sample): **0.1130**
- 95% CI: **[-0.2656, 0.5518]** (from 2000 valid draws of 2000)

## 2. Majority-vote decisions + mean conviction


**HOM**
| ticker | date | majority | mean conv | n votes |
|---|---|---|---|---|
| AAPL | 2026-04-15 | BUY | 4.00 | 15 |
| AAPL | 2026-05-15 | HOLD | 3.73 | 15 |
| CAT | 2026-04-15 | BUY | 3.73 | 15 |
| CAT | 2026-05-15 | BUY | 3.33 | 15 |
| GOOGL | 2026-04-15 | BUY | 3.07 | 15 |
| GOOGL | 2026-05-15 | BUY | 3.00 | 15 |
| JPM | 2026-04-15 | HOLD | 3.27 | 15 |
| JPM | 2026-05-15 | HOLD | 3.07 | 15 |
| MSFT | 2026-04-15 | BUY | 3.47 | 15 |
| MSFT | 2026-05-15 | BUY | 3.53 | 15 |
| PG | 2026-04-15 | HOLD | 3.00 | 15 |
| PG | 2026-05-15 | HOLD | 3.00 | 15 |
| UNH | 2026-04-15 | BUY | 4.00 | 15 |
| UNH | 2026-05-15 | BUY | 4.00 | 15 |
| XOM | 2026-04-15 | BUY | 4.00 | 15 |
| XOM | 2026-05-15 | BUY | 4.00 | 15 |

**HET**
| ticker | date | majority | mean conv | n votes |
|---|---|---|---|---|
| AAPL | 2026-04-15 | BUY | 4.00 | 15 |
| AAPL | 2026-05-15 | HOLD | 3.20 | 15 |
| CAT | 2026-04-15 | BUY | 3.73 | 15 |
| CAT | 2026-05-15 | BUY | 3.53 | 15 |
| GOOGL | 2026-04-15 | BUY | 3.60 | 15 |
| GOOGL | 2026-05-15 | BUY | 3.60 | 15 |
| JPM | 2026-04-15 | HOLD | 3.60 | 15 |
| JPM | 2026-05-15 | BUY | 3.07 | 15 |
| MSFT | 2026-04-15 | BUY | 3.73 | 15 |
| MSFT | 2026-05-15 | BUY | 3.87 | 15 |
| PG | 2026-04-15 | HOLD | 3.20 | 15 |
| PG | 2026-05-15 | HOLD | 3.00 | 15 |
| UNH | 2026-04-15 | BUY | 4.00 | 15 |
| UNH | 2026-05-15 | BUY | 4.13 | 15 |
| XOM | 2026-04-15 | BUY | 3.33 | 15 |
| XOM | 2026-05-15 | BUY | 4.00 | 15 |

## 3. Cost

| config | calls | total $ | mean $/call | mean $/ensemble-decision |
|---|---|---|---|---|
| HOM | 240 | 0.1306 | 0.000544 | 0.002722 |
| HET | 240 | 0.3273 | 0.001364 | 0.006818 |

## 4. Accuracy proxy — ⚠️ NOISY, DO NOT DRAW CONCLUSIONS

20-trading-day forward-return sign vs pooled majority direction (HOLD = abstain). Pilot-scale; recorded only.

- HOM: hit-rate 0.636 over 11 directional cells (5 HOLD-abstained)
- HET: hit-rate 0.667 over 12 directional cells (4 HOLD-abstained)

## 6. Run-to-run variance & sampling-nondeterminism bias

| config | κ within-run avg | κ cross-run pooled | within−cross | run variance |
|---|---|---|---|---|
| HOM | 0.6349 | 0.6168 | 0.0181 | 0.008032 |
| HET | 0.5219 | 0.5552 | -0.0334 | 0.008820 |

**Direction of bias for κ_HOM: UPWARD (κ_HOM inflated by within-run sampling correlation).** within−cross = 0.0181. A positive gap means a single stochastic sampling context makes identical models agree with themselves more than they do across independent draws, inflating the naive within-run κ_HOM.
