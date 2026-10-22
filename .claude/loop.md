Maintenance pass for the current branch. Report only; never push, rebase, merge, or open/close MRs.

1. `git fetch origin`, then `git log --oneline origin/feature/example_taskboard..HEAD`.
   - If it lists commits, continue.
   - If it is empty and `origin/<current branch>` exists, the branch was merged: say so, suggest deleting the local branch, and stop.
   - If it is empty and the branch was never pushed, it is a new branch with nothing to merge yet: say so in one line and stop.
2. Dry-run a merge with `git merge-tree --write-tree HEAD origin/feature/example_taskboard`. If it conflicts, list the conflicting files.
3. Run `make test`. If anything fails, show the failing test names and the likely cause, and propose a minimal fix without committing it.
4. If everything is green and nothing changed since the last pass, reply with one line.

We have no GitLab CLI here, so MR comments and pipeline status are not visible. Don't guess about them.
