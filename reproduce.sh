#!/usr/bin/env bash
# Top-level entry point for IEEE Access / Code Ocean reproduction.
# Delegates to scripts/reproduce.sh (keeps implementation under scripts/).
#
#   bash reproduce.sh                 # default: analyze x2 + hash compare
#   bash reproduce.sh --analyze-only  # analyze once
#   bash reproduce.sh --help
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/scripts/reproduce.sh" "$@"
