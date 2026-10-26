#!/usr/bin/env python3
"""PreToolUse hook for Bash: block `git add -A`, `git add --all` and `git add .`.

CLAUDE.md says to stage changed files by name. Exit 2 blocks the call and sends
stderr back to Claude so it can retry with explicit paths.

The command is split like a shell would (shlex), so quoted arguments such as
`git add "."` are still caught, while a commit message or an `echo` that only
mentions `git add -A` is not. Wrappers (`env`, `sudo`, `bash -c '...'`) are
looked through. If shlex can't parse the command (an apostrophe in a heredoc),
a regex on the raw text decides instead, so unrelated commands are not blocked.

This guards against habit, not against evasion. Known gaps: `$(...)` inside
double quotes, `eval`, and other interpreters (`python -c`). Runs on the system
python3 (3.9).
"""

import json
import re
import shlex
import sys

OPERATORS = {";", "&", "&&", "|", "||", "(", ")"}
WRAPPERS = {"env", "sudo", "command", "nice", "xargs", "time"}
SHELLS = {"bash", "sh", "zsh"}
# Git options before the subcommand that take a separate value (`git -C dir add`).
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
STAGE_ALL_ARGS = {"-A", "--all", ".", "./", ":/"}
# Fallback for commands shlex can't parse: `git ... add ... <stage-all arg>` on one line.
STAGE_ALL_RE = re.compile(
    r"""\bgit\b[^\n;&|]*?\sadd\b[^\n;&|]*?\s["']?(-A|--all|-\w*A\w*|\./?|:/)["']?(\s|$)"""
)

MESSAGE = "CLAUDE.md: never 'git add -A' / 'git add .'; stage the files you changed by name."


def segments(command):
    """Yield the token list of each simple command, split at shell operators."""
    lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segment = []
    for token in lexer:
        if token in OPERATORS:
            yield segment
            segment = []
        else:
            segment.append(token)
    yield segment


def stages_everything(tokens):
    """True if the tokens are a `git ... add` call that stages the whole tree."""
    while tokens and (tokens[0] in WRAPPERS or ("=" in tokens[0] and not tokens[0].startswith("-"))):
        tokens = tokens[1:]  # leading VAR=value assignments and wrapper commands
        while tokens and tokens[0].startswith("-"):
            tokens = tokens[1:]  # the wrapper's own flags (`env -i`, `sudo -E`)
    if tokens and tokens[0] in SHELLS and "-c" in tokens[1:-1]:
        inner = tokens[tokens.index("-c") + 1]
        return any(stages_everything(t) for t in segments(inner))
    if not tokens or tokens[0] != "git":
        return False

    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in GIT_OPTIONS_WITH_VALUE else 1
    if i >= len(tokens) or tokens[i] != "add":
        return False

    for arg in tokens[i + 1 :]:
        if arg in STAGE_ALL_ARGS:
            return True
        if arg.startswith("-") and not arg.startswith("--") and "A" in arg[1:]:
            return True  # combined short flags: -Av, -vA
    return False


def main():
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    try:
        blocked = [shlex.join(tokens) for tokens in segments(command) if stages_everything(tokens)]
    except ValueError:  # unbalanced quotes, e.g. an apostrophe in a heredoc body
        match = STAGE_ALL_RE.search(command)
        blocked = [match.group(0).strip()] if match else []
    if blocked:
        print(f"Blocked: '{blocked[0]}'. {MESSAGE}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
