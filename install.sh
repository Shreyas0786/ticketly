#!/usr/bin/env bash
#
# Developer convenience for working ON Ticketly from a repo checkout.
#
# Normal users do NOT need this — they install the published package:
#
#     pipx install ticketly        # (or: pip install ticketly)
#     ticketly install all         # wire up Claude Code and/or Codex
#
# This script just does the editable-install equivalent for contributors:
# installs the engine from this checkout, then runs the same `ticketly install`
# wiring. Re-running is safe (idempotent). With no argument it prints the choices.
#
#   ./install.sh claude   editable install + wire Claude Code
#   ./install.sh codex    editable install + wire Codex
#   ./install.sh all      editable install + wire both
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Ticketly dev install (from a repo checkout):

  ./install.sh claude   editable install + wire Claude Code (the /ticketly skill)
  ./install.sh codex    editable install + wire Codex ("use Ticketly")
  ./install.sh all      editable install + wire both

Normal users instead run:  pipx install ticketly && ticketly install all
EOF
}

MODE="${1:-}"
case "$MODE" in
  claude|codex|all)
    echo "[engine] Editable install from $REPO_DIR ..."
    python3 -m pip install -e "$REPO_DIR" --quiet
    echo "[wire]   ticketly install $MODE"
    ticketly install "$MODE"
    ;;
  ""|-h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown option: $MODE" >&2; echo >&2
    usage >&2
    exit 1
    ;;
esac
