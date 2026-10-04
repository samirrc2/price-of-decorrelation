# Pre-registration — cross-domain replication (MMLU medical decisions)

Frozen **before any data collection**. Written in response to reviewer requests for a
replication on a substantially different domain. The prediction below is recorded in
advance; the result is reported as it comes out.

## Why this domain

The confirmatory study measured one financial decision task. Reviewers objected that a
single task whose accuracy is near chance and whose label marginals shift by
configuration cannot establish a general principle. This arm answers that directly:

- **Different domain.** Clinical decision-making, not equity direction.
- **Above chance.** Four options, chance 25%; models score far above it.
- **Balanced labels.** Choice order is shuffled deterministically per item, giving an
  answer key of {'A': 126, 'B': 128, 'C': 145, 'D': 138} across 537 items.
- **Different label structure.** Four categories, not the finance triple — which also
  answers the separate request to vary label structure.
- **Same data family as the correlated-error literature this paper builds on**, which
  analysed MMLU via public leaderboards.

## Design

Identical to the confirmatory study except for the domain. Same five agents, same three
configurations, same per-agent independent-draw seeding, same temperature, same number
of runs, same estimators.

| | Confirmatory (finance) | This arm (medical) |
|---|---|---|
| Items | 100 equities × 12 dates | 537 MMLU items |
| Labels | BUY / HOLD / SELL | A / B / C / D |
| Configurations | HOM, HET-LITE, HET | identical |
| Agents | 5 | identical |
| Runs | 3 | identical |
| Clustering unit | ticker | item |

Source: `cais/mmlu` (MIT licence), subsets `professional_medicine` and
`clinical_knowledge`. No personal data. Items frozen with SHA-256 before collection.

## Primary prediction

**Δκ(HOM − HET) > 0**, with a 95% ticker-analogue cluster-bootstrap CI excluding zero.

**Δφ(HOM − HET) > 0** on the error-correlation statistic, CI excluding zero.

## Predicted magnitude, stated in advance

The effect is expected to be **smaller than the finance estimate of 0.336**. Accuracy is
materially higher here, and agents that are individually more often correct necessarily
agree more, which compresses the achievable spread in κ. A smaller but positive effect
therefore **confirms** the mechanism; it is not a weaker result.

## Secondary prediction

Δκ is expected to be **larger on harder items** than easier ones, split at the median
per-item accuracy. This is the difficulty-modulation hypothesis and is exploratory.

## Decision rule

- Both primary predictions hold, CIs exclude zero → the finance result replicates.
- Point estimates positive but a CI includes zero → reported as directional but
  underpowered; no generality claim.
- Either point estimate ≤ 0 → reported as a failure to replicate, in full.

## Analysis plan

`analyze.py` as used for the confirmatory arm, with the category set switched to
['A', 'B', 'C', 'D']. Fleiss κ per run, averaged; Δκ by cluster bootstrap over items, 2000
draws, seed 42. Error correlation φ and the observed/expected joint-failure lift by the
same bootstrap. No other estimator is introduced.

## Frozen artifact hashes (pre-collection)

- inputs (`data/inputs_mmlu/`, 537 files): `8bc7e76d928bc263d015941a6559154c7cffe85e9cff554c157acf8731b85ed5`
- ground truth (`data/mmlu_ground_truth.json`): `4c2ca4321d139c9785694fcc22fd86ee949ffdc2bcd1d00f1386973766173a03`
- config: `data/configs/config_mmlu.yaml`
- prompt: `data/configs/prompt_mmlu.txt`
