"""Shared path helpers for Code Ocean–compatible layout with dated datasets.

Local repo:
  <repo>/code/src/...   <repo>/data/...   <repo>/results/...

Code Ocean mounts:
  /code/...   /data/...   /results/...

Call datasets live under:
  data/<kind>/<YYYYMMDD>/runs.csv
  data/<kind>/latest -> <YYYYMMDD>

Analysis outputs:
  results/data-<YYYYMMDD>_run-<YYYYMMDD_HHMMSS>/
  results/latest -> that folder
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

DEFAULT_KIND = "confirmatory"
_DATE_DIR_RE = re.compile(r"^\d{8}(_\d{6})?$")  # YYYYMMDD or YYYYMMDD_HHMMSS
_DATA_DATE_IN_PATH_RE = re.compile(r"(?:^|/)(\d{8}(?:_\d{6})?)(?:/|$)")


@lru_cache(maxsize=1)
def _roots() -> tuple[Path, Path, Path, Path]:
    """Return (code_root, data_root, results_root, repo_root)."""
    if (Path("/code") / "src").is_dir() and Path("/data").is_dir():
        code = Path("/code")
        data = Path("/data")
        results = Path("/results")
        results.mkdir(parents=True, exist_ok=True)
        return code, data, results, Path("/")

    code = Path(__file__).resolve().parents[1]
    repo = code.parent
    return code, repo / "data", repo / "results", repo


def code_root() -> Path:
    return _roots()[0]


def data_root() -> Path:
    return _roots()[1]


def results_root() -> Path:
    return _roots()[2]


def repo_root() -> Path:
    return _roots()[3]


def resolve_under(root: Path, rel: str | Path) -> Path:
    """Resolve rel against root; strip a leading data/ or code/ segment if present."""
    p = Path(rel)
    if p.is_absolute():
        return p
    parts = p.parts
    if parts and parts[0] in ("data", "code", "results"):
        kind = parts[0]
        rest = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        if kind == "data":
            return data_root() / rest
        if kind == "code":
            return code_root() / rest
        return results_root() / rest
    return root / p


def resolve_data_path(rel: str | Path) -> Path:
    return resolve_under(data_root(), rel)


def resolve_config_path(path: str | Path = "configs/config.yaml") -> Path:
    """Resolve a config YAML path under data/configs/ (or absolute / data/...)."""
    p = Path(path)
    if p.is_absolute():
        return p
    parts = p.parts
    if parts and parts[0] == "data":
        return resolve_data_path(p)
    if parts and parts[0] == "configs":
        return data_root() / p
    return data_root() / "configs" / p.name


def default_config_path() -> Path:
    return data_root() / "configs" / "config.yaml"


def utc_today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def utc_now_run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def kind_root(kind: str = DEFAULT_KIND) -> Path:
    return data_root() / kind


def list_dataset_dates(kind: str = DEFAULT_KIND) -> list[str]:
    root = kind_root(kind)
    if not root.is_dir():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name)),
        reverse=True,
    )


def point_dataset_latest(kind: str, data_date: str) -> Path:
    """Make data/<kind>/latest -> <data_date>."""
    root = kind_root(kind)
    root.mkdir(parents=True, exist_ok=True)
    latest = root / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(data_date)
    return latest


def resolve_dataset_dir(kind: str = DEFAULT_KIND, data_date: str | None = None) -> Path:
    """Resolve data/<kind>/<date>/ — default: latest symlink, else newest dated folder."""
    root = kind_root(kind)
    if data_date:
        return root / data_date
    latest = root / "latest"
    if latest.exists():
        return latest.resolve()
    dates = list_dataset_dates(kind)
    if dates:
        return root / dates[0]
    # Fall back to kind root (legacy flat layout)
    return root


def new_collection_dir(
    kind: str = DEFAULT_KIND,
    data_date: str | None = None,
    *,
    fresh: bool = False,
) -> Path:
    """Create data/<kind>/<stamp>/ for a new collection and point latest at it.

    If fresh=True (scratch runs), always use a unique YYYYMMDD_HHMMSS stamp so the
    run starts from an empty runs.csv — never resumes an older folder.
    """
    if fresh:
        day = data_date or utc_now_run_stamp()
        # If caller passed a bare YYYYMMDD with fresh, make it unique
        if data_date and _DATE_DIR_RE.match(data_date) and "_" not in data_date:
            day = f"{data_date}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    else:
        day = data_date or utc_today_yyyymmdd()
    d = kind_root(kind) / day
    d.mkdir(parents=True, exist_ok=True)
    point_dataset_latest(kind, day)
    return d


def infer_data_date(path: Path | str | None) -> str | None:
    """Extract YYYYMMDD from a dataset path (…/20260704/runs.csv or …/latest/…)."""
    if path is None:
        return None
    p = Path(path).resolve()
    for part in reversed(p.parts):
        if _DATE_DIR_RE.match(part):
            return part
    # Symlink latest → date
    for parent in [p] + list(p.parents):
        if parent.name == "latest" and parent.is_symlink():
            target = os.readlink(parent)
            if _DATE_DIR_RE.match(Path(target).name):
                return Path(target).name
    m = _DATA_DATE_IN_PATH_RE.search(str(p))
    return m.group(1) if m else None


def _expand_runs_csv_path(rel: str | Path) -> Path:
    """Map legacy or shorthand paths onto dated dataset layout."""
    p = Path(rel)
    if p.is_absolute():
        return p
    parts = list(p.parts)
    # Strip leading data/
    if parts and parts[0] == "data":
        parts = parts[1:]
    if not parts:
        return data_root() / DEFAULT_KIND / "latest" / "runs.csv"

    # data/confirmatory/runs.csv → confirmatory/latest/runs.csv
    if len(parts) >= 2 and parts[-1] == "runs.csv" and _DATE_DIR_RE.match(parts[-2]) is None:
        if parts[-2] == "latest":
            return data_root().joinpath(*parts)
        # kind/runs.csv
        kind = parts[-2] if len(parts) == 2 else parts[0]
        if kind in (
            "confirmatory", "control", "minipilot",
            "temperature_robustness_small", "temperature_robustness",
        ):
            return resolve_dataset_dir(kind) / "runs.csv"

    # data/confirmatory → confirmatory/latest/runs.csv
    if len(parts) == 1 and parts[0] in (
        "confirmatory", "control", "minipilot", "temperature_robustness_small",
    ):
        return resolve_dataset_dir(parts[0]) / "runs.csv"

    return data_root().joinpath(*parts)


def resolve_runs_csv(cfg_path: str | None = None) -> Path:
    """CSV path: POD_RUNS_CSV env, else config paths.runs_csv, else confirmatory/latest."""
    env = os.environ.get("POD_RUNS_CSV")
    if env:
        p = Path(env)
        if p.is_absolute():
            # Directory passed → use runs.csv inside
            if p.is_dir():
                return p / "runs.csv"
            return p
        if Path(env).suffix == "" and not str(env).endswith(".csv"):
            # e.g. data/confirmatory or data/confirmatory/20260704
            expanded = resolve_data_path(env)
            if expanded.is_dir() or not expanded.suffix:
                # Prefer dated dir resolution
                parts = Path(env).parts
                if parts and parts[0] == "data":
                    parts = parts[1:]
                if len(parts) >= 1:
                    kind = parts[0]
                    date = parts[1] if len(parts) > 1 and _DATE_DIR_RE.match(parts[1]) else None
                    return resolve_dataset_dir(kind, date) / "runs.csv"
            return expanded if expanded.suffix else expanded / "runs.csv"
        return _expand_runs_csv_path(env)

    if cfg_path:
        return _expand_runs_csv_path(cfg_path)
    return resolve_dataset_dir(DEFAULT_KIND) / "runs.csv"


def resolve_out_dir(create: bool = True) -> Path:
    """Analysis output dir: POD_OUT_DIR env, else results/latest."""
    env = os.environ.get("POD_OUT_DIR")
    if env:
        p = Path(env)
        if p.is_absolute():
            out = p
        elif p.parts and p.parts[0] == "results":
            out = resolve_under(results_root(), env)
        else:
            out = results_root() / p
    else:
        out = results_root() / "latest"
    if create:
        out.mkdir(parents=True, exist_ok=True)
    return out


def new_timestamped_results_dir(data_date: str | None = None, runs_csv: Path | str | None = None) -> Path:
    """Create results/data-<dataDate>_run-<runStamp>/ and return it."""
    dd = data_date or infer_data_date(runs_csv) or "unknown"
    run = utc_now_run_stamp()
    name = f"data-{dd}_run-{run}"
    out = results_root() / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def point_latest_symlink(target: Path) -> None:
    """Make results/latest -> target (relative symlink when possible)."""
    latest = results_root() / "latest"
    results = results_root()
    results.mkdir(parents=True, exist_ok=True)
    try:
        rel = target.resolve().relative_to(results.resolve())
        link_target = str(rel)
    except ValueError:
        link_target = str(target.resolve())
    # Robust to any prior 'latest': symlink, file, OR a real directory (a
    # committed results/latest would otherwise raise IsADirectoryError on unlink).
    if latest.is_symlink() or latest.is_file():
        latest.unlink()
    elif latest.is_dir():
        import shutil
        shutil.rmtree(latest)
    latest.symlink_to(link_target)


def raw_dump_dir() -> Path:
    """Where orchestrator writes per-call JSON: data/raw/YYYYMMDD/."""
    day = utc_today_yyyymmdd()
    d = data_root() / "raw" / day
    d.mkdir(parents=True, exist_ok=True)
    return d
