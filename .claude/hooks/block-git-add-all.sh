#!/usr/bin/env bash
# PreToolUse hook for Bash: block `git add -A`, `git add --all` and `git add .`.
# CLAUDE.md says to stage changed files by name. Exit 2 blocks the call and
# sends stderr back to Claude so it can retry with explicit paths.

set -f  # no globbing when splitting args
cmd=$(jq -r '.tool_input.command // empty')

# Drop quoted strings first, so a commit message that mentions `git add .` passes.
cmd=$(printf '%s\n' "$cmd" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")

# Each `git [-C dir] add ...` segment, cut at ; & | or a newline.
segments=$(printf '%s\n' "$cmd" | grep -oE 'git([[:space:]]+-C[[:space:]]+[^[:space:];&|]+)?[[:space:]]+add([[:space:]][^;&|]*)?')

while IFS= read -r seg; do
  for arg in $seg; do
    case "$arg" in
      -A | --all | . | ./ | -[a-zA-Z]*A*)
        echo "Blocked: '$seg'. CLAUDE.md: never 'git add -A' / 'git add .'; stage the files you changed by name." >&2
        exit 2
        ;;
    esac
  done
done <<< "$segments"

exit 0
