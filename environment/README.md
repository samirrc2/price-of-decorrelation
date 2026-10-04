# Environment (Code Ocean–compatible)

## Code Ocean

`Dockerfile` in this folder matches the capsule environment that successfully
ran the keys-free replication check (Python 3.12.8 base from Code Ocean’s
registry + pinned pip packages, including `numpy==2.2.6` and `pandas==2.2.3`).

Capsule mounts:

| Mount | Contents |
|-------|----------|
| `/code` | `src/`, `scripts/`, `tests/`, `requirements.txt`, `run` |
| `/data` | call CSVs, `configs/`, `inputs/`, `datacache/`, `appendix/` |
| `/results` | analysis outputs |

Default Reproducible Run: `/code/run` → `bash code/scripts/reproduce.sh --data data/confirmatory/20260704`.

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

`reproduce.sh` / `code/run` set `PYTHONPATH` to `code/src`; they do not activate the venv.
