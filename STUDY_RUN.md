# Run sequence — The Price of Diversity (confirmatory study)

STRICT ORDER. Live phases run on your Mac (my sandbox can't reach the provider
APIs). Do not skip the gate.

```bash
cd "/Users/samirchincholikar/Desktop/NIW/Paper 1"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # openai, google-genai, matplotlib, numpy, pyyaml
python secrets.py                        # confirm openai / google / xai keys FOUND

# ---- PHASE 0: model inventory (~$0.10) -------------------------------------
python probe_models.py                   # verifies model strings, fingerprints, cutoffs
                                         # -> updates model_manifest.md (Verified block)
# If any model string is invalid, fix config.yaml models: before continuing.

# ---- PHASE 1: freeze -------------------------------------------------------
python build_grid.py                     # writes appendix/grid.csv, validates date floor
python build_data.py                     # builds inputs/ snippets + forward returns
                                         # (mini-pilot cells are already cached)
python freeze.py                         # SHA-256 + local git commit -> freeze_receipt.md

# ---- PHASE 1.5: mini-pilot GATE (~$3, hard cap $8) -------------------------
python orchestrator.py --phase minipilot # 8x2x3runs x3configs on the NEW models
python verify_independence.py            # (edit path to minipilot/runs.csv) draws must differ
python minipilot_gate.py                 # -> minipilot_verdict.md : PROCEED or STOP
# PROCEED only if cells-for-power <= 400 AND projected full-study cost <= $75.
# If STOP: do not continue; send me minipilot_verdict.md.

# ---- (after PROCEED) full-grid data -----------------------------------------
# The 400-cell news+price cache is fetched via the financial connector (my side,
# staged in batches) before Phase 2. Ping me to run it; it populates datacache/
# and inputs/ for all 50x8 cells, then `python build_data.py` finalizes them.

# ---- PHASE 2: single execution (hard cap $90) -------------------------------
python orchestrator.py --phase full      # 18,000 calls; 50% mid-run report; <=3 logged retries
python phase2_finalize.py                # chmod 444 runs.csv + SHA-256 -> archive_manifest.md

# ---- PHASE 3: deterministic analysis ($0 API) -------------------------------
python analyze.py                        # metrics_summary.md (verdict first), figures/, tables/, docs
python replication_check.py              # analyze x2, byte-identical -> replication_check.md
```

## Deliverables produced
model_manifest.md, preregistration.md, freeze_receipt.md, appendix/grid.csv,
minipilot_verdict.md, runs.csv (+ archive_manifest.md), metrics_summary.md,
replication_check.md, protocol_exhibit.md, headline_check.md,
threats_to_validity.md, figures/ (fig1–3, png+svg), tables/ (csv+tex),
appendix/data_availability.md.

## Notes
- `config.yaml` is the frozen single source of truth; `analyze.py` reads only it +
  `runs.csv` and is byte-deterministic (seeded bootstrap = 42).
- Pilot archives: `archive/pilot_v1/` (clean, Δκ=0.113) and
  `archive/pilot_v1_broken_perRunSeed/` (seed-shared, Δκ=0.485) — used by fig. 2.
- Everything was validated end-to-end in offline mock mode (`PILOT_MOCK=1`); clear
  `cache/ results/ runs.csv minipilot/` of any mock output before a real run.
