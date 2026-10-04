#!/usr/bin/env bash
# Activate the project virtualenv (.venv at repo root).
#
# Creates .venv and installs requirements.txt on first use.
# Reuses the existing .venv on later runs; installs deps if missing.
# Requires Python >= 3.10 (for numpy==2.2.6). Picks the newest available among
# python3.13 / 3.12 / 3.11 / 3.10, else plain `python3` if it is >= 3.10.
# After activation, `python` is always the venv interpreter (not a hardcoded path).
#
# Usage (from the repo root or anywhere):
#   source scripts/activate_env.sh
#
# Do NOT run as ./scripts/activate_env.sh — activation must happen in your shell.

if ! (return 0 2>/dev/null); then
  echo "Source this script so it activates in your current shell:"
  echo "  source scripts/activate_env.sh"
  exit 1
fi

# Resolve repo root (works when sourced from bash or zsh)
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -n "${(%):-%x}" ]]; then
  _SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
else
  _SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
_REPO_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
_VENV="$_REPO_ROOT/.venv"
_REQ="$_REPO_ROOT/requirements.txt"

_pick_python() {
  local cand
  # Prefer an explicit 3.x binary when present; do not require 3.12 specifically.
  for cand in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cand" >/dev/null 2>&1; then
      echo "$cand"
      return 0
    fi
  done
  # Fall back to python3 only if it is >= 3.10 (macOS system python3 is often 3.9).
  if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "python3"
      return 0
    fi
  fi
  return 1
}

_install_deps() {
  echo "Installing dependencies from requirements.txt ..."
  "$_VENV/bin/pip" install -q --upgrade pip
  "$_VENV/bin/pip" install -q -r "$_REQ" || {
    echo "pip install failed."
    return 1
  }
  echo "Dependencies installed."
}

_venv_python_ok() {
  # Existing venv must be Python >= 3.10 and able to import yaml after install
  "$_VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

_PYTHON="$(_pick_python)" || {
  echo "Need Python >= 3.10 (numpy==2.2.6 requires it)."
  echo "Install examples:"
  echo "  macOS:   brew install python@3.12"
  echo "  Ubuntu:  sudo apt install python3.12 python3.12-venv"
  echo "  Or use any python3.10+ already on PATH."
  return 1 2>/dev/null || exit 1
}

if [[ -d "$_VENV" ]] && ! _venv_python_ok; then
  echo "Existing .venv uses Python < 3.10 — recreating with $_PYTHON ..."
  rm -rf "$_VENV"
fi

if [[ ! -d "$_VENV" ]]; then
  echo "Creating virtualenv at $_VENV with $_PYTHON ..."
  "$_PYTHON" -m venv "$_VENV" || {
    echo "Failed to create virtualenv."
    return 1 2>/dev/null || exit 1
  }
  _install_deps || return 1 2>/dev/null || exit 1
  echo "Virtualenv ready."
else
  echo "Using existing virtualenv at $_VENV"
  if ! "$_VENV/bin/python" -c "import yaml" 2>/dev/null; then
    echo "Dependencies incomplete — finishing install ..."
    _install_deps || return 1 2>/dev/null || exit 1
  fi
fi

# shellcheck disable=SC1091
source "$_VENV/bin/activate"

export PYTHONPATH="$_REPO_ROOT/src:${PYTHONPATH:-}"
cd "$_REPO_ROOT" || return 1 2>/dev/null || exit 1

echo "Activated: $(python --version) at $(which python)"
