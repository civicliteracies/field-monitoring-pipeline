#!/usr/bin/env bash
#
# Refuse to end an agent's turn while the quality gate is failing.
#
# "Looks done" is the only signal an agent has without a check it can run, so
# this runs the real gate and blocks the stop when it fails, printing the failure
# for the agent to act on. Exit 2 blocks; anything else lets the turn end.
#
# See ADR-0009 in docs/DECISIONS.md.

set -uo pipefail

input=$(cat)

# Claude Code sets stop_hook_active when a Stop hook has already blocked once in
# this turn. Without this guard a persistently failing gate would loop forever,
# so the second time through we let the turn end and leave the failure visible.
case "$input" in
  *'"stop_hook_active":true'* | *'"stop_hook_active": true'*)
    exit 0
    ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# No gate to run means nothing to block on.
command -v mise >/dev/null 2>&1 || exit 0
[ -f mise.toml ] || exit 0

if output=$(mise run check 2>&1); then
  exit 0
fi

{
  echo "The quality gate is failing, so this turn cannot end yet."
  echo "Fix what is below, then run 'mise run check' until it passes."
  echo
  printf '%s\n' "$output" | tail -40
} >&2

exit 2
