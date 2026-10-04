"""Central secrets loader. Any module can `from secrets import get_key`.

Loads keys.env (dotenv-style KEY=VALUE, one per line) from this folder, and
also honours real environment variables (env wins over the file so CI can
override). No third-party dependency required.
"""
from __future__ import annotations
import os
from pathlib import Path

import io_paths

_HERE = io_paths.repo_root()


def _resolve_keys_file() -> Path:
    """Locate keys.env. Search order (first hit wins):
      1. $KEYS_ENV_PATH (explicit override)
      2. sibling "API Keys" folder next to this project folder  <-- default
      3. this folder (fallback)
    """
    override = os.environ.get("KEYS_ENV_PATH")
    if override:
        return Path(override).expanduser()
    api_keys_dir = _HERE.parent / "API Keys"
    candidates = [
        api_keys_dir / "keys.env",       # /.../NIW/API Keys/keys.env
        api_keys_dir / "keys.env.txt",   # double-clickable TextEdit version
        api_keys_dir / "keys.txt",
        _HERE / "keys.env",              # /.../Paper 1/keys.env (fallback)
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # default target even if not yet created


_KEYS_FILE = _resolve_keys_file()

_PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_FILE_CACHE = _parse_env_file(_KEYS_FILE)


def get_raw(var_name: str) -> str | None:
    """Return a specific env var, preferring the real environment."""
    val = os.environ.get(var_name) or _FILE_CACHE.get(var_name)
    return val or None


def get_key(provider: str) -> str:
    """Return the API key for a provider ('anthropic', 'openai', 'google', 'xai').

    Raises a clear error if the key is missing so the orchestrator can halt
    before spending anything.
    """
    provider = provider.lower()
    if provider not in _PROVIDER_ENV:
        raise KeyError(f"Unknown provider {provider!r}. Known: {sorted(set(_PROVIDER_ENV))}")
    var = _PROVIDER_ENV[provider]
    val = get_raw(var)
    if not val:
        raise RuntimeError(
            f"No API key for provider {provider!r}. Expected {var} in keys.env "
            f"(copy keys.env.template -> keys.env) or the environment."
        )
    return val


def get_base_url(provider: str) -> str | None:
    if provider.lower() == "anthropic":
        return get_raw("ANTHROPIC_BASE_URL")
    return None


if __name__ == "__main__":
    # Diagnostic: report which providers have keys present, WITHOUT printing them.
    print(f"keys.env present: {_KEYS_FILE.exists()}  ({_KEYS_FILE})")
    for prov, var in sorted(set(_PROVIDER_ENV.items())):
        present = bool(get_raw(var))
        print(f"  {prov:10s} <- {var:18s} : {'FOUND' if present else 'missing'}")
