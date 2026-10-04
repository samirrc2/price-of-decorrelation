# Archive manifest — confirmatory dataset

- file: `data/confirmatory/20260704/runs.csv` (reachable as `data/confirmatory/latest/runs.csv`)
- SHA-256: `8a1f5fc78482e87cb7ef5825c6a9425eb377bc80a7a60eb0febf61e70e5c0ee1`
- rows (incl. retries): 94566   usable (ok): 54000
- frozen read-only (0444): yes
- timestamp (UTC): 2026-07-04T03:00:37.848726+00:00
- `data/configs/config.yaml` SHA-256: `89d9ae44e88d9f22e213f7f0fc74f5998810748692ff3cff3e1fce8e6f30e607`

This file is the paper's dataset. Do NOT regenerate it. Any correction requires a new
versioned file (e.g. `runs_v2.csv`) plus a changelog entry here.

Every input the reported numbers depend on — this capture, the control, cross-domain and
appendix captures, the configs, the serialized model inputs, the ground truth and the
offline price cache — is pinned in `DATA_MANIFEST.md` and `data/MANIFEST.sha256`:

```
python code/src/make_manifest.py --verify
```

## Changelog

- **2026-10-01.** Two facts in this file were stale and are corrected above. It named
  `data/confirmatory/runs.csv`, a path that has not existed since the Code Ocean layout
  reorganisation (commit `88fa8f13a`) moved captures into dated folders. It also cited
  `config.yaml` SHA-256 `dfeccd12…`, which matches neither the current file nor its
  pre-reorganisation version (`3608d4982d…`) and so predates both. The dataset hash was
  and remains correct; only this record had drifted. Verified at the same time that the
  reorganisation changed the config's *path strings* only — `runs_csv` and
  `spend_ledger` keys — leaving every seed, estimand, grid entry and model unchanged, so
  the frozen protocol the numbers were computed under is intact.
