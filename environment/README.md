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

Install deps into a repo-root `.venv` (do not rely on the Code Ocean base image):

```bash
source code/scripts/activate_env.sh
```

That installs from `code/requirements.txt` (Python ≥ 3.10).
