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
double quotes, `eval`, other interpreters (`python -c`), and long wrapper options
with a separate value (`sudo --user root`). Runs on the system python3 (3.9).
"""

import json
import re
import shlex
import sys

OPERATORS = {";", "&", "&&", "|", "||", "(", ")"}
# Wrapper commands, each with its own short options that take a separate value
# (`sudo -u root`, `nice -n 5`). Per wrapper, because `-s` takes a value for xargs
# but not for sudo.
WRAPPERS = {
    "env": {"-u", "-C", "-S", "-P"},
    "sudo": {"-u", "-g", "-h", "-p", "-U", "-C", "-D", "-r", "-t", "-T"},
    "command": set(),
    "nice": {"-n"},
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"},
    "time": {"-f", "-o"},
}
SHELLS = {"bash", "sh", "zsh"}
SHELL_COMMAND_FLAG = re.compile(r"-[a-zA-Z]*c[a-zA-Z]*")  # -c, -lc, -ec
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


def option_width(flag, takes_value):
    """How many tokens a wrapper option uses, getopt style.

    `-E` is 1. `-u root` is 2. In a group the first flag that takes a value ends it:
    `-Eu root` is 2, while `-uroot` is 1 because the rest of the token is the value.
    """
    if flag.startswith("--"):
        return 1
    for i, char in enumerate(flag[1:], start=1):
        if "-" + char in takes_value:
            return 2 if i == len(flag) - 1 else 1
    return 1


def stages_everything(tokens):
    """True if the tokens are a `git ... add` call that stages the whole tree."""
    while tokens and (tokens[0] in WRAPPERS or ("=" in tokens[0] and not tokens[0].startswith("-"))):
        takes_value = WRAPPERS.get(tokens[0], set())
        tokens = tokens[1:]  # a VAR=value assignment or a wrapper command
        while tokens and tokens[0].startswith("-"):
            tokens = tokens[option_width(tokens[0], takes_value) :]  # the wrapper's own flags
    if tokens and tokens[0] in SHELLS:
        for i, token in enumerate(tokens[1:-1], start=1):
            if SHELL_COMMAND_FLAG.fullmatch(token):
                return any(stages_everything(t) for t in segments(tokens[i + 1]))
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
