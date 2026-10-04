# Data (Code Ocean `/data` mount)

Call datasets are **dated** so you can keep multiple collections:

```text
data/
  confirmatory/
    20260704/                 # frozen main study (completion day)
      runs.csv
      spend_ledger.json
      dataset_manifest.json
    latest -> 20260704
  control/
    20260704/
    latest -> 20260704
  temperature_robustness_small/   # small T-check (not a full temp study)
    20260704/
      runs_T00.csv …
    latest -> 20260704
  minipilot/
    20260703/
    latest -> 20260703
  configs/ inputs/ datacache/ appendix/
  raw/YYYYMMDD/                 # optional per-call JSON (gitignored)
```

## Reproduce (existing data)

```bash
bash reproduce.sh                              # uses confirmatory/latest
bash reproduce.sh --data data/confirmatory/20260704
bash reproduce.sh --analyze-only
```

Results: `results/data-<dataDate>_run-<runStamp>/` + `results/latest`.

## Collect a new dataset (e.g. ~48k today)

```bash
source code/scripts/activate_env.sh
bash reproduce.sh --scratch-run 48k          # live collect → analyze → results/latest
bash reproduce.sh --scratch-run full
```

(`--dry-run` is not allowed with `--scratch-run`.)
