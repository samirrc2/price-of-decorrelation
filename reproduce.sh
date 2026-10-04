#!/usr/bin/env bash
# Top-level entry point for IEEE Access / Code Ocean reproduction.
# Delegates to code/scripts/reproduce.sh.
#
#   bash reproduce.sh                 # default: analyze x2 + hash compare
#   bash reproduce.sh --analyze-only  # analyze once
#   bash reproduce.sh --help
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# Local repo: ./code/scripts/... ; Code Ocean may place this at /code/reproduce.sh
if [[ -f "$ROOT/code/scripts/reproduce.sh" ]]; then
  exec bash "$ROOT/code/scripts/reproduce.sh" "$@"
elif [[ -f "$ROOT/scripts/reproduce.sh" ]]; then
  exec bash "$ROOT/scripts/reproduce.sh" "$@"
else
  echo "ERROR: cannot find code/scripts/reproduce.sh" >&2
  exit 1
fi
