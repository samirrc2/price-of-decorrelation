# Model manifest — Phase 0

**Status: DRAFT (proposed strings from provider docs, July 2026). Run
`python probe_models.py` on the machine with live keys to confirm availability,
capture system fingerprints, and verify knowledge cutoffs. probe_models.py
rewrites the "Verified" block below and fails loudly if any string is invalid.**

## Selected models

| role | provider | model string | price in / out ($/1M) | knowledge cutoff | used in configs |
|---|---|---|---|---|---|
| OpenAI flagship  | openai | `gpt-5.5`         | 5.00 / 30.00 | 2025-08 (VERIFY) | inventory only |
| OpenAI efficient | openai | `gpt-5.4-nano`    | 0.20 / 1.25  | 2025-08 (VERIFY) | HOM, HET-LITE, HET |
| Gemini flagship  | google | `gemini-3.1-pro`  | 2.00 / 12.00 | 2025-01 (VERIFY) | inventory only |
| Gemini efficient | google | `gemini-3.5-flash`| 1.50 / 9.00  | 2025-01 (VERIFY) | HET-LITE, HET |
| Grok flagship    | xai    | `grok-4.3`        | 1.25 / 2.50  | 2024-11 (VERIFY) | HET |

Sources: OpenAI, Google AI, and xAI developer docs / pricing pages (July 2026).
Pricing and cutoffs change — the probe is the source of truth, not this draft.

## Latest knowledge cutoff (drives the grid date floor)

The **latest** cutoff among models USED in configs (gpt-5.4-nano, gemini-3.5-flash,
grok-4.3) governs Phase 1's date constraint: every analysis date must be strictly
after it. Draft latest = **2025-08** (gpt-5.4-nano). Grid dates are therefore all in
2026, ≤ 2026-06-01. probe_models.py records the confirmed value; if any used model's
cutoff lands after the earliest grid date, Phase 1 build_grid.py aborts.

## Configs (fixed after inventory; 5 agents each, temperature 0.7)

- **HOM**      : 5 × `gpt-5.4-nano`                                   (non-OpenAI agents = 0)
- **HET-LITE** : 4 × `gpt-5.4-nano` + 1 × `gemini-3.5-flash`          (non-OpenAI agents = 1)
- **HET**      : 2 × `gpt-5.4-nano` + 2 × `gemini-3.5-flash` + 1 × `grok-4.3` (non-OpenAI = 3)

Heterogeneity level = count of non-OpenAI agents ∈ {0, 1, 3}.

## Verified (filled by probe_models.py)

_Probed 2026-07-03T19:39:43.833393+00:00_

| model | ok | latency s | in/out tok | fingerprint | cutoff probe |
|---|---|---|---|---|---|
| `gpt-5.5` | True | 3.71 | 170/152 | (none returned) | The 2024 G7 summit in Italy took place in June 2024. |
| `gpt-5.4-nano` | True | 0.79 | 170/47 | (none returned) | I don’t have reliable knowledge of the most recent major world event beyond my knowledge cutoff (August 2024). |
| `gemini-3.5-flash` | True | 1.55 | 177/51 | (provider exposes no fingerprint) | {
  "event": "The coronation of King Charles III and Queen Camilla took place in London in May 2023."
} |
| `grok-4.3` | True | 3.79 | 293/26 | fp_eb3c003fc66c14ed | The October 2023 Hamas attack on Israel and ensuing Gaza conflict. |

Raw probe log: `model_probe_raw.json`.
