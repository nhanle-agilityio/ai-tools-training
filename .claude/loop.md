Maintenance pass for the current branch. Report only; never push, rebase, merge, or open/close PRs.

1. `git fetch github`, then `git log --oneline github/feature/example_taskboard..HEAD`.
   - If it lists commits, continue.
   - If it is empty and `github/<current branch>` exists, the branch was merged: say so, suggest deleting the local branch, and stop.
   - If it is empty and the branch was never pushed, it is a new branch with nothing to merge yet: say so in one line and stop.
2. Dry-run a merge with `git merge-tree --write-tree HEAD github/feature/example_taskboard`. If it conflicts, list the conflicting files.
3. Run `make test`. If anything fails, show the failing test names and the likely cause, and propose a minimal fix without committing it.
4. If everything is green and nothing changed since the last pass, reply with one line.

If the branch has an open PR, read its review comments and CI status with the GitHub MCP (`pull_request_read`) and
list unresolved comments and failing checks. Read only: never reply, resolve, or re-run anything.
