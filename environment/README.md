# Environment (Code Ocean–compatible)

Local development installs deps into a repo-root `.venv` via:

```bash
source code/scripts/activate_env.sh
```

That installs from `code/requirements.txt` (Python ≥ 3.10).

## Code Ocean

In the capsule Environment UI, select **Python 3.11 or 3.12** and add pip packages
from `code/requirements.txt` (or the subset needed for Phase-3 offline reproduce:
`pyyaml`, `numpy`, `matplotlib`). Leave the Post-Install Script empty if it cannot
access `/code`.

Capsule layout expected by this repo:

| Mount | Contents |
|-------|----------|
| `/code` | `src/`, `scripts/`, `tests/`, `requirements.txt` |
| `/data` | call CSVs, `configs/`, `inputs/`, `datacache/`, `appendix/` |
| `/results` | analysis outputs |

Default run: `bash /code/scripts/reproduce.sh` (or root `reproduce.sh` if present).
