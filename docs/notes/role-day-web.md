# Day 11 — Role day (web) and Developer Checkpoint 3

## Checkpoint 3

| Requirement | Done | Evidence |
| --- | --- | --- |
| One skill and one hook merged | Yes | `ticket-fix` skill and `/mr-description` command (MR !12, Day 7); `git add` hook (PR #4, hardened in PR #9) |
| One MCP tool used end to end | Yes | GitHub MCP: issue, branch, commit, PR and review on PR #2 (Day 8) |
| One ultrareview or `/code-review` report acted on | Yes | `/code-review` on PR #9: all 7 findings fixed as a test/fix commit pair, CI green, merged (Day 10) |
| Role-day exercise | Yes | This note |

## Setup

TaskBoard is a JSON API with no web page, so there was nothing to fill in or read a console from. We added
a minimal UI, `taskboard/static/index.html` (plain HTML and JS, served by Flask at `/static/index.html`,
no Python change). It has a task list, an add-task form and filters, and six seeded bugs that only show
in a browser:

| ID | Bug |
| --- | --- |
| W1 | Overdue badge never shows (`isOverdue` vs `is_overdue`) |
| W2 | Error alerts say "undefined" (`message` vs `error`) |
| W3 | The "High" option sends `urgent`, so the API rejects it |
| W4 | `TypeError` in the console after every add (wrong element id) |
| W5 | Stored XSS: titles, tags and project names go into `innerHTML` |
| W6 | Only page 1 is shown, with no pager |

All six were confirmed with Playwright before the exercise. The answer key stayed outside the repo. The UI
lives on a local `exp/web-ui` branch and is not merged: it is a new feature outside any ticket.

## QA in the browser

The same prompt each time: test the page like a QA tester, try every priority, read the console after
each action, compare with the API, change no code.

| | Playwright (fallback) | Claude in Chrome |
| --- | --- | --- |
| Seeded bugs | 6 / 6 | 6 / 6 |
| False positives | 0 | 0; it caught and dropped one of its own (a search "bug" caused by lost focus in its typing tool) |
| Real bugs outside the key | Project select resets after each add | No empty state when there are no results |
| XSS | Harmless markup, checked in the DOM; also found project names | `onerror` actually ran (`XSS-fired` in the console); titles only |
| `alert()` | Read through Playwright's dialog handling | Replaced `alert()` in the page with a console logger, because dialogs block the extension; said so |
| Browser | Its own Chromium, no logins | Your real browser and logins |

The first run fell back to Playwright: `/chrome` inside a running session does not load the browser tools.
They load at start, with `claude --chrome` (or `@browser` in VS Code). The second run used them.

- **Equal results on a local app with no login.** Claude in Chrome is worth it when the app needs your
  logged-in session; Playwright is better for repeatable runs and CI.
- **Each run found a different real bug outside the key.** Two QA passes cover more than one.
- **It doesn't look like a person using the page.** Most work is reading the DOM, running JS and setting
  form values directly. Pages change, but there is no moving cursor or typing to watch. The tabs open in a
  tab group, which may be collapsed or in another window.
- **Picking a browser is confusing.** `/chrome` listed "Browser 1/2/3 · macOS" with no browser or profile
  names (Chrome, Brave and probably a second profile). Keep the extension signed in to one browser only.

## Browser pane preview loop (Desktop app)

In the Desktop app's Code tab: open the page in the browser pane, fix W3, W2 and W1 one at a time, and check
each in the pane before moving on. From the session transcript:

| Step | What Claude did |
| --- | --- |
| Open | `preview_start` on the page |
| Before each fix | Reproduced in the pane: real clicks, JS checks of the DOM, and the network request (400 body for W3) |
| Fix | One `Edit` per bug |
| After each fix | `navigate` to reload, 1 to 4 seconds after the edit, then the same check: 201 and a red "high" row; "title is required" in the alert; 2 badges on page 1, the third overdue task being on page 2 |

- **The pane does not hot-reload; Claude reloads it.** The reload came so fast after each edit that it
  looked instant. Static files needed no server restart, and no stale cache showed up.
- About 1m30s for three bugs, each with a before and after.
- The working tree already had the same three fixes from an earlier try. To get a real "before", it backed
  the file up, reset it to the committed version and redid the fixes; the result matched the backup byte
  for byte. It said so.
- It stayed in scope: it reported W4 and W6 without fixing them.

## For the retro

- `/chrome` mid-session doesn't add browser tools; start with `claude --chrome`. Claude fell back to
  Playwright on its own and said why.
- The browser picker shows only numbers. Keep one browser connected.
- JavaScript dialogs block browser automation. Claude worked around it by replacing `alert()`, so the page
  it tested was not exactly the shipped page.
- None of the browser runs touched the code except the pane loop, which was asked to.

## Takeaways

- **Verify the product, not just the code.** All six bugs passed the 57 API tests, because they live in the
  page. Only a browser showed them.
- **Pick the browser tool by what you need.** Playwright for repeatable, logged-out checks and CI. Claude
  in Chrome for apps behind your login, or to watch. The browser pane for a quick edit-and-look loop while
  fixing.
- **Ask for before and after.** The pane loop was convincing because each fix had both, checked the same
  way.
