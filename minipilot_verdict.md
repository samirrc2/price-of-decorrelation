# Mini-pilot verdict (Phase 1.5) — PROCEED

- Primary **Δκ(HOM−HET) = 0.5104**  95% CI [0.2634, 0.7487] (κ_HOM=0.6764, κ_HET=0.1660)
- Per-cell effect d̄/sd = 1.2158 (d̄=0.3000, sd=0.2468, cells=16)
- **Cells for 80% power = 6** (gate ≤ 1200)
- **Projected full-study cost (at 1200 cells) = $18.07** (gate ≤ $75)

## PROCEED

Both gate conditions met on the new model set. Proceed to Phase 1 freeze (if not already frozen) and Phase 2 single execution.

---
Run `python verify_independence.py` on minipilot/runs.csv (point PATH there) to confirm same-model agents produced distinct raw completions before trusting κ_HOM.
