#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-tasks/handoff_packet.md}"
mkdir -p "$(dirname "$OUT")"

{
  echo "# Handoff Packet (for switching Claude ↔ ChatGPT)"
  echo
  echo "## Repo state"
  echo '```'
  git status
  echo '```'
  echo
  echo "## Branch/worktree"
  echo '```'
  git branch --show-current
  git worktree list || true
  echo '```'
  echo
  echo "## Diff (stat)"
  echo '```'
  git diff --stat
  echo '```'
  echo
  echo "## Diff (full)"
  echo '```'
  git diff
  echo '```'
} > "$OUT"

echo "Wrote $OUT"
