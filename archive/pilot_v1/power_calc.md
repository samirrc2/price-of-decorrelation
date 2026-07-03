# Power calculation

## Method

Fleiss' κ is a scalar per config, so power is sized on the **per-cell paired agreement difference** that underlies Δκ: for each (ticker,date) cell we take the mean-over-runs pairwise agreement P for HOM and for HET, and their difference d = P_HOM − P_HET. Under a paired design the standardized effect is d̄/sd(d); cells for target power at two-sided α follow n = ((z_{1−α/2} + z_{power}) / (d̄/sd))².

## Assumptions & caveats

- Cells treated as i.i.d. paired units (ignores ticker/date clustering — the bootstrap CI in metrics_summary is the clustering-aware check).
- Normal approximation; small-n pilots make d̄/sd itself noisy, so treat cells-needed as an order-of-magnitude estimate.
- Per-cell pairwise agreement is a proxy for κ at the cell level; it moves monotonically with κ but is not identical.

## Observed inputs

- cells observed: 16
- mean paired diff d̄: 0.0438
- sd(d): 0.2331
- standardized effect d̄/sd: 0.1877
- z_(1−α/2)=1.960, z_power=0.842

## Result

- **Cells needed for 80% power at α=0.05 (two-sided): 223**

## Projected full-study cost

- cost per ensemble-decision: HOM 0.002722, HET 0.006818 USD
- runs per cell: 3  →  cost per cell (both configs): 0.028621 USD
- **projected full-study API cost = cells_needed × cost/cell = $6.38**
