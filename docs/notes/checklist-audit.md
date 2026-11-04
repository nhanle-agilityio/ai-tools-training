# Checklist audit: Day 3, Day 6 and Day 11

Date: 2026-11-04

## Purpose

The three pass/fail checkpoints of the Developer track (Day 3 Checkpoint 1, Day 6 Checkpoint 2, Day 11
Checkpoint 3) were checked once on the day and then left. This note re-reads each requirement as it was
given, looks for evidence in git, the notes and the session transcripts, and lists what is still open.

Status values: **done** (evidence found), **partial** (something is missing), **not done**, **unknown**
(no evidence either way). Requirement text comes from the session transcripts; the Day 11 text was pasted
as screenshots, so it is reconstructed from the replies that quoted it.

Evidence that lives outside the repo: `notes/` (git-excluded, local only), GitLab MRs `!n` (self-hosted
GitLab, not readable from here), claude.ai artifacts.

## Day 3: Checkpoint 1 (2026-10-16)

| Item | Status | Evidence | Note |
| --- | --- | --- | --- |
| 1. Reproduce an assigned bug and write the repro in the ticket | Done | `b505182` `docs(TB-104)`: "Verified reproduction" and "Investigation" in `docs/tickets/TB-104.md` | |
| 2. Fix on a branch with a test | Done | Branch `fix/TB-104-project-stats`: `622099e` (failing test), `13f10ab` and `454e0ea` (fixes), `94a2c5d` (test after merge) | Test-first order is visible in the history. |
| 3. PR with a self-contained description | Done | MR !3 (TB-104), draft in `notes/day-03-mr-description.md` | MR text itself is on GitLab and was not re-read. |
| 4a. One peer review with 3 actionable comments | Partial | Comments in `notes/day-03-review-mr1.md`; posted on practice MR !1 as "Request changes" (user, 2026-10-16 03:01 UTC) | The MR was a practice MR with seeded bugs, not a real peer. The lead may ask for a real one. |
| 4b. One merge with conflict resolved | Partial | Merge commit `5d420a6` resolves the conflict; `e12dd8e` merges the branch into `feature/example_taskboard` | The conflict was created for practice (`1097547` `[practice]` commit), not a real one. |

Side note: MR !2 was found on 2026-10-16 to have been merged by an agent without consent (wrong
direction). It led to the "never merge without a yes" rule in `CLAUDE.md` and memory.

## Day 6: Developer Checkpoint 2 (2026-10-21)

| Item | Status | Evidence | Note |
| --- | --- | --- | --- |
| Two parallel sessions (worktrees), both merged | Done | `claude --worktree`: TB-105 (`bd63e37`, `baf6451`, MR !8) and TB-106 (`ae9b519`, `8d25454`, MR !9); merged with no conflict, 50/50 tests | Agent view was used to watch both. |
| One plan-mode change steered via diff comments | Done | TB-106 session (2026-10-21); plan revised before approval, then hunk comments | Screenshot only, no file in the repo. |
| One artifact (PR walkthrough, shared with a peer) | Partial | "TB-106 Priority Sort": https://claude.ai/artifact/2uXVn68ouviqE3kgEzZdV5, shared as "Anyone with the link" | Published and shared by link. No evidence a peer opened or received it. |
| One `/loop` run (built-in prompt, then custom `/loop 5m check the deploy`, plus a `loop.md`) | Done | `.claude/loop.md` in `0f3c356` (MR !10); both loops run, server stopped and restarted to trigger detection | |
| One Remote Control steer from the phone | Done | `/rc` plus phone steer edited the artifact (v3, "developed in parallel worktrees"); session of 2026-10-21 10:43 UTC | Phone screenshot not in the repo. |
| `ultrathink` and `/effort` levels on one bug, plan-tier noted | Done | `docs/notes/effort.md` (`dab1c1b`); TB-103 fixed in `7f07507` and `9e1e146` (MR !11) | Tiers recorded: low, medium, high and `ultrathink` all worked. |
| Subagents intro (course, bounded investigation while main session codes) | Partial | Plan was prepared in the `tb-103` worktree session (Explore plus `code-reviewer`); a second, recorded run on 2026-11-04 in `docs/notes/subagents.md` | Practical part done: no transcript of the Day 6 run was kept, so the note records a measured run instead. Course completion unknown. |
| Cloud session for a long task, close the laptop, check from claude.ai/code | **Not done** | Carried as "open" in every report from 2026-10-22 to 2026-11-04 | Confirmed still open. Blocker noted on day 6: repo is on GitLab, a cloud session needs `CCR_FORCE_BUNDLE=1` and cannot push back. The repo is now on GitHub (`github` remote), so the blocker is gone. |
| Exercise: one artifact, one loop run, one phone steer, screenshotted to the channel | **Not done** | Listed as "post screenshots to the channel" in reports through 2026-11-04 | Confirmed still open. Screenshots exist locally; posting is unknown. |

## Day 11: Role day (web) and Developer Checkpoint 3 (2026-10-27 and 2026-10-28)

| Item | Status | Evidence | Note |
| --- | --- | --- | --- |
| Checkpoint 3: one skill and one hook merged | Done | `ticket-fix` skill and `/mr-description` (`8b611a8`, `4348c6b`, MR !12); `git add` hook PR #4 (`ca8001e`, hardened in PR #9) | |
| Checkpoint 3: one MCP tool used end to end | Done | GitHub MCP: issue, branch, commit, PR and review on PR #2 (Day 8, `f948271`) | |
| Checkpoint 3: one ultrareview or `/code-review` report acted on | Done | `/code-review` on PR #9: 7 findings fixed (`7e71088`, `f8d81ac`, `aa6f300`, `8b3ccab`), merged | No `ultrareview` was run; `/code-review` is accepted by the requirement. |
| Checkpoint 3: role-day exercise | Done for web | `docs/notes/role-day-web.md` (`3a14b99`, PR #11) | Mobile is open (below). |
| Web: Claude in Chrome tests the page (fill a form, read the console) | Done | 6 of 6 seeded bugs found, 0 false positives; Playwright fallback also run | Note records the `claude --chrome` start requirement. |
| Web: browser pane preview loop (fix, look, repeat) | Done | W3, W2, W1 fixed one at a time in the Desktop pane, each with before and after | W4 and W6 deliberately left. |
| Web: the UI used for the exercise | Partial | `2a986ab`, `f41a6cd` exist only on local branch `exp/web-ui`; `taskboard/static` is not on `feature/example_taskboard` | Intentional (new feature outside any ticket), but the note points at a branch that is not pushed. |
| Mobile: iOS Simulator pane loop (build, run, tap, screenshot); computer use on Android emulator if available | **Not done** | User, 2026-10-28 10:48 UTC: "I will continue the mobile part later (no note needed)". Guide given 2026-10-28 03:52 UTC; Xcode was missing (Command Line Tools only) | Confirmed still open. No Android emulator step was attempted. |
| Game: computer use on the engine editor; artifacts for build reports | Skipped by choice | User, 2026-10-28 03:52 UTC: game can be skipped | Not applicable to this track; keep the reason in the notes. |

## Open items

1. **Day 6, cloud session.** Run a long task with `claude --cloud` on the GitHub repo (for example, a
   spec or test-matrix review), close the laptop, check progress at claude.ai/code, and take a screenshot.
   Add a short note to `docs/notes/` with what ran and what was observed.
2. **Day 6, screenshots to the channel.** Post the artifact, loop and phone-steer screenshots, and note
   the date. If the channel is no longer used, record the reason instead.
3. **Day 6, artifact shared with a peer.** Send the artifact link to one person and note who and when, or
   state that sharing by link was the delivery.
4. **Day 6, subagents.** The practical part is covered since 2026-11-04 (`docs/notes/subagents.md`
   records two parallel subagent runs with their cost and results). Still open: confirm the course was
   completed, then mark the item done.
5. **Day 11, mobile.** Install Xcode, run the iOS Simulator pane loop (build, run, tap, screenshot) with
   a small app against the TaskBoard API. If Xcode is not available, record that reason and skip the
   Android emulator.
6. **Day 11, web UI branch.** Push `exp/web-ui` (or attach the diff to the note) so the note can be
   reproduced, or state in the note that it is local only.
7. **Day 3, peer review and conflict.** Both were practice setups. Review one real teammate PR and
   resolve one real conflict if the lead asks; otherwise note the practice setup in the final checkpoint.
