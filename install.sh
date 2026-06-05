#!/usr/bin/env bash
#
# Install Ticketly once, so `/ticketly` works inside Claude Code from ANY folder.
#
# It does two things, both pointing back at this repo so future updates are a plain `git pull`:
#   1. Installs the `ticketly` Python engine (editable) so `python3 -m ticketly...`
#      runs from any working directory.
#   2. Symlinks the `/ticketly` skill into your personal Claude Code skills dir, so the
#      command is available in every project AND tracks this repo automatically.
#
# After this, updating is just `git pull` in this repo — no reinstall needed.
# Re-running it is safe (idempotent). Usage:  ./install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/ticketly"

echo "Ticketly install"
echo "  engine : $REPO_DIR"
echo "  skill  : $SKILLS_DIR"
echo

# 1. Install the Python engine (editable, so it always points back at this repo).
echo "[1/2] Installing the ticketly engine ..."
python3 -m pip install -e "$REPO_DIR" --quiet
echo "      done."

# 2. Symlink the skill at the user level, so it tracks this repo on every git pull.
echo "[2/2] Linking the /ticketly skill ..."
mkdir -p "$SKILLS_DIR"
ln -sf "$REPO_DIR/.claude/skills/ticketly/SKILL.md" "$SKILLS_DIR/SKILL.md"
echo "      done."

echo
echo "Ticketly is installed. From now on, in ANY folder:"
echo "  1. open it in Claude Code"
echo "  2. type /ticketly"
echo "  3. describe your project — tickets land in that folder."
echo
echo "To update later: 'git pull' in this repo. No reinstall needed."
