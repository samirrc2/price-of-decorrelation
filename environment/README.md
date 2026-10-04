# Environment (Code Ocean–compatible)

## Code Ocean

`Dockerfile` in this folder matches the capsule environment that ran the keys-free
replication check (Python 3.12.8 base from Code Ocean's registry + pinned pip packages,
including `numpy==2.2.6` and `pandas==2.2.3`, which must stay paired — see the comment in
`code/requirements.txt`).

Capsule mounts:

| Mount | Contents |
|-------|----------|
| `/code` | `src/`, `scripts/`, `tests/`, `requirements.txt`, `run` |
| `/data` | call CSVs, `configs/`, `inputs/`, `inputs_mmlu/`, `MANIFEST.sha256`, ground truth |
| `/results` | analysis outputs, written by the run |

Default Reproducible Run: `/code/run` → `bash code/scripts/reproduce.sh --data data/confirmatory/20260704`.

## What runs, and what a capsule cannot check

The capsule mounts `/code` and `/data` only, so `paper/` and `submission/` are not present.
The gate that compares the manuscript's numbers against the frozen analysis reports that it
is **not checkable here** and is skipped; everything that regenerates and verifies the
numbers themselves runs in full:

| Gate | Runs in a capsule? | What it asserts |
|------|---|---|
| Determinism (two analysis passes, hash-compared) | yes | every output byte-identical across re-runs |
| Input integrity (`make_manifest.py --verify`) | yes | all 1,747 frozen inputs match their pinned SHA-256 |
| Revision arms (`reviewer_revision.py`, `analyze_mmlu.py`) | yes | the reviewer analyses and the cross-domain replication regenerate |
| Claims extraction (`make_claims.py`) | yes | the named numbers come out of the regenerated outputs |
| Manuscript agreement (`check_claims.py`) | **no** — needs `paper/main.tex` | no reported number has drifted from the analysis |
| Unit tests | yes | metric and bootstrap primitives |

A capsule run therefore exits **0** on success. The exit codes are a contract:

| Code | Meaning |
|------|---------|
| 0 | Every gate that applies to this copy passed |
| 1 | A gate failed: an input is corrupt, or a reported number disagrees with the frozen analysis |
| 2 | The analysis reproduced, but a gate that *should* apply here could not run — e.g. a full checkout whose `paper/` is present but whose dependencies are missing. Never treat this as a pass. |

## Local development

**Activate first, then reproduce** (Python ≥ 3.10):

```bash
source code/scripts/activate_env.sh    # creates/reuses .venv, installs deps, activates
bash reproduce.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
bash reproduce.sh
```

`reproduce.sh` and `code/run` set `PYTHONPATH` to `code/src`; they do not activate the venv.
They select an interpreter by **import capability**, not by name: an explicit `PY`, then
`./.venv/bin/python`, then `python3`, then `python` — the first that can import `yaml`,
`numpy` and `matplotlib` wins. Point them anywhere with:

```bash
PY=/path/to/python bash reproduce.sh
```

## Verifying the inputs on their own

```bash
python code/src/make_manifest.py --verify     # 0 = all pinned inputs intact, 1 = corrupt/missing
```

`DATA_MANIFEST.md` lists every pinned file with its size and SHA-256.
