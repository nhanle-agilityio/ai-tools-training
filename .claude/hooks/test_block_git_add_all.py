"""Tests for block_git_add_all.py. Not part of `make test` (testpaths = tests); run with:

.venv/bin/pytest .claude/hooks/test_block_git_add_all.py
"""

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("block_git_add_all.py")


def run_hook(command):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    # System python3, as the hook runs in settings.json.
    return subprocess.run(["python3", str(HOOK)], check=False, input=payload, capture_output=True, text=True)


@pytest.mark.parametrize(
    "command",
    [
        "git add -A",
        "git add .",
        "git add --all",
        "git add ./",
        "git add :/",
        "git add -vA",
        "git status && git add .",
        "cd x; git add . && git commit -m y",
        "git status\ngit add .",
        'git add . && git commit -m "msg"',
        "git -C /x add -A",
        # Bypasses found by the Claude review on PR #4
        "git add -Av",
        "git add -An",
        'git add "."',
        "git add '.'",
        'git -C "my dir" add -A',
        "git -c core.quotepath=off add -A",
        "git --no-pager add .",
        "git --git-dir=.git add -A",
        "GIT_TRACE=1 git add .",
        "git add -- .",
        # Second review: wrappers
        "bash -c 'git add -A'",
        'sh -c "cd x && git add ."',
        "env git add .",
        "env -i git add -A",
        "sudo git add .",
        "command git add .",
        # Third review: wrapper options that take a value, and combined shell flags
        "sudo -u root git add .",
        "sudo -uroot git add .",
        "sudo -Eu root git add .",
        "nice -n 5 git add -A",
        "env -u FOO git add .",
        "xargs -I {} git add .",
        "sudo -u root env -u FOO git add -A",
        "bash -lc 'git add .'",
        "bash -e -c 'git add -A'",
        # Blocked before the fix above; a shared option list broke them (the /goal regression)
        "sudo -s git add .",
        "sudo -P git add .",
        "sudo -E git add .",
        "nice git add -A",
    ],
)
def test_blocks_staging_everything(command):
    result = run_hook(command)
    assert result.returncode == 2
    assert "stage the files you changed by name" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git add .gitignore",
        "git add docs/a.md taskboard/services.py",
        "git add 'my file.md'",
        "git add -p",
        "git add -u",
        "git add src/*.py",
        "git commit -m 'add . files'",
        'git commit -q -m "chore: block git add -A and git add . with a hook"',
        "echo git add -A is forbidden",
        "git status",
        "ls *",
        "",
        "bash -c 'git add docs/a.md'",
        "sudo -u root git add docs/a.md",
        "bash -lc 'git status'",
        # Second review: unbalanced quotes in unrelated commands must not be blocked
        "cat > notes.md <<'EOF'\nit's done\nEOF",
        "echo it's fine",
    ],
)
def test_allows_other_commands(command):
    assert run_hook(command).returncode == 0


def test_unparsable_command_falls_back_to_regex():
    result = run_hook("git add . && echo it's done")
    assert result.returncode == 2
    assert "stage the files you changed by name" in result.stderr
