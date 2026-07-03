# Pilot: cost of de-correlating multi-agent LLM financial analysis

Measures the accuracy/cost price of model heterogeneity in a 5-agent financial
ensemble. Compares a **homogeneous** ensemble (5× Haiku) against a **heterogeneous**
one (Opus + 2× Sonnet + 2× Haiku) on within-ensemble agreement (Fleiss' κ), cost,
and a noisy forward-return accuracy proxy — then runs the statistics that decide
whether a full study is worth funding.

**This repo builds and runs the pilot; it does not ship any results.** All result
files are generated from live API calls you make with your own keys.

## What runs where

```
config.yaml        fixed grid: tickers, dates, seeds, HOM/HET, pricing, $20 cap
secrets.py         loads ../API Keys/keys.env (env vars override); used everywhere
build_data.py      cached real news+prices -> inputs/ snippets + forward_returns
agent.py           builds no-lookahead prompt, calls a model, strict-JSON parse
orchestrator.py    INDEPENDENT-mode loop -> runs.csv, live spend cap, response cache
metrics.py         Fleiss κ, majority vote, cost, forward-return accuracy proxy
stats.py           cluster bootstrap CI on Δκ, run-variance/bias, power calc
analyze.py         reads runs.csv -> metrics_summary.md, power_calc.md, verdict.md
verify_independence.py  checks the 5 agents/cell gave DISTINCT raw draws (not seed-shared)

datacache/         COMMITTED real data (source of truth, no network at run time)
  news_cache.json    real dated headlines per (ticker,date) from financial MCP
  prices.json        real EOD closes per ticker
  forward_returns.json  (generated) 20-trading-day forward-return sign per cell
inputs/            (generated) per-cell no-lookahead snippets built from news_cache
cache/responses/   (generated) response cache; re-runs skip API + spend on a hit
results/raw/<provider>/<model>/   (generated) full per-call record, one JSON each
```

## Quickstart

```bash
pip install -r requirements.txt

# Keys live in the sibling "API Keys" folder:
cp "../API Keys/keys.env.template" "../API Keys/keys.env"   # then edit — at least ANTHROPIC_API_KEY
python secrets.py                  # sanity: which providers have keys (no secrets printed)

# 1. VERIFY the two things the spec insists on, in config.yaml:
#    - models.*.knowledge_cutoff   (dates must be strictly AFTER every cutoff)
#    - models.*.price_in/price_out (must match CURRENT published pricing)
#    The placeholders are marked "VERIFY" — the run refuses to start on bad dates
#    but CANNOT know if your pricing is stale, so check it.

python build_data.py               # builds inputs/ snippets + forward_returns from datacache (no network)
python orchestrator.py --dry-run   # validates config + grid + projects worst-case cost, no calls
python orchestrator.py             # runs / resumes; halts hard before the $20 cap
python analyze.py                  # writes the three deliverables + verdict
```

Offline dry test (no keys, no spend): `PILOT_MOCK=1 python orchestrator.py` runs the
full grid with a deterministic offline stand-in so you can exercise caching, storage,
metrics, and stats before spending anything. Clear `cache/` afterward so your real run
doesn't hit mock cache entries: `rm -rf cache results runs.csv`.

### Smart infra

- **Response cache** (`cache/responses/`): keyed by provider+model+prompt+seed+temperature.
  A warm cache re-runs the whole grid at **$0** — only cache misses touch the API or the
  spend cap. Editing a prompt or model invalidates just the affected keys.
- **Per-model result storage** (`results/raw/<provider>/<model>/`): one JSON per call with
  the full record, so you can diff behavior model-by-model, plus the flat `runs.csv`.
- **Cached market data** (`datacache/`): real headlines and prices are committed, so
  `orchestrator.py` and `analyze.py` need no financial API at run time and are fully
  reproducible. Regenerate derived files with `build_data.py`.

## Guardrails baked in

- **Hard spend cap ($20).** `orchestrator.py` projects each call's worst-case cost
  and stops `stop_margin_usd` before the cap. `spend_ledger.json` tracks cumulative.
- **Deterministic & resumable.** Fixed tickers/dates/seeds in config.yaml; completed
  rows in runs.csv are skipped so a killed run resumes exactly.
- **No lookahead.** Every context snippet's `asof` date is asserted strictly before
  the analysis date, or the run aborts.
- **Independence.** One fresh API request per agent — no shared context, no caching.
- **Full provenance.** Each call logs model, seed, timestamp, prompt hash, snippet
  source, tokens, cost, and raw response to runs.csv.

## Deliverables (generated)

1. `runs.csv` — raw per-call log.
2. `metrics_summary.md` — κ table (κ_HOM, κ_HET, Δκ) + bootstrap CI, majority-vote
   table, cost table, noisy accuracy proxy, run-variance & sampling-bias analysis.
3. `power_calc.md` — method, assumptions, cells needed for 80% power, projected
   full-study cost.
4. `verdict.md` — GO / REDESIGN / NO-GO with the two gate numbers stated first.

## Gate criteria (in config.yaml)

- **GO**: cells for 80% power ≤ 400 AND projected cost ≤ $300.
- **REDESIGN**: power reachable only via design changes — cheapest redesign proposed.
- **NO-GO**: bootstrap CI on Δκ too wide for any feasible grid to resolve.

## Notes on scope

- Default HOM/HET are Claude-only per the spec. The provider router (agent.py) also
  supports OpenAI / Gemini / xAI so you can add cross-vendor agents by editing only
  config.yaml + keys.env.
- The accuracy proxy reads `datacache/forward_returns.json` (real cached prices), so it
  needs no network; it falls back to `yfinance` only if that cache is deleted.
- `knowledge_cutoff` and pricing in config.yaml are **placeholders to verify** — they
  cannot be confirmed from inside the code.
