#!/usr/bin/env bash
#
# Install Ticketly once, so it works from ANY folder — in Claude Code, in Codex, or both.
#
# Every mode installs the same `ticketly` Python engine (editable) so `python3 -m ticketly...`
# runs from any working directory. The modes differ only in which agent's front door they wire up:
#
#   ./install.sh claude   Claude Code — symlinks the /ticketly skill into ~/.claude/skills/
#   ./install.sh codex     Codex      — adds a pointer to ~/.codex/AGENTS.md ("use Ticketly")
#   ./install.sh all       both of the above
#
# Everything points back at this repo, so updating later is just `git pull` — no reinstall.
# Re-running is safe (idempotent). With no argument, this prints the choices and exits.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/ticketly"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_AGENTS="$CODEX_HOME/AGENTS.md"
MARKER_START="# >>> ticketly (codex) >>>"
MARKER_END="# <<< ticketly (codex) <<<"

usage() {
  cat <<'EOF'
Ticketly install — pick where to wire it up:

  ./install.sh claude   for Claude Code (the /ticketly skill)
  ./install.sh codex    for Codex ("use Ticketly" in any session)
  ./install.sh all      for both

Every mode installs the shared Python engine. Update later with `git pull` — no reinstall.
EOF
}

install_engine() {
  echo "[engine] Installing the ticketly engine (shared) ..."
  python3 -m pip install -e "$REPO_DIR" --quiet
  echo "         done: $REPO_DIR"
}

install_claude_skill() {
  echo "[claude] Linking the /ticketly skill ..."
  mkdir -p "$SKILLS_DIR"
  ln -sf "$REPO_DIR/.claude/skills/ticketly/SKILL.md" "$SKILLS_DIR/SKILL.md"
  echo "         done: $SKILLS_DIR/SKILL.md"
}

install_codex_pointer() {
  echo "[codex]  Adding the Ticketly pointer to $CODEX_AGENTS ..."
  mkdir -p "$CODEX_HOME"
  touch "$CODEX_AGENTS"
  # Idempotent: strip any previous Ticketly block, then append a fresh one. Exact-line
  # matching (not regex) so the user's own AGENTS.md content is never touched.
  awk -v s="$MARKER_START" -v e="$MARKER_END" '
    $0==s {skip=1}
    skip==0 {print}
    $0==e {skip=0}
  ' "$CODEX_AGENTS" > "$CODEX_AGENTS.tmp" && mv "$CODEX_AGENTS.tmp" "$CODEX_AGENTS"
  {
    echo "$MARKER_START"
    cat "$REPO_DIR/codex/agents-pointer.md"
    echo "$MARKER_END"
  } >> "$CODEX_AGENTS"
  echo "         done."
}

MODE="${1:-}"
case "$MODE" in
  claude)
    echo "Ticketly install — Claude Code"; echo
    install_engine; install_claude_skill
    echo; echo "Done. In any folder, open Claude Code and type /ticketly."
    ;;
  codex)
    echo "Ticketly install — Codex"; echo
    install_engine; install_codex_pointer
    echo; echo "Done. In any folder, run 'codex' and say \"use Ticketly\"."
    ;;
  all)
    echo "Ticketly install — Claude Code + Codex"; echo
    install_engine; install_claude_skill; install_codex_pointer
    echo; echo "Done. Use /ticketly in Claude Code, or say \"use Ticketly\" in Codex."
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

echo "To update later: 'git pull' in this repo. No reinstall needed."
