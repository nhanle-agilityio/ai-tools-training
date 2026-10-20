## **TB-101 — Last page of the task list cannot be opened**

**Analysis**

1. **Asks:** Pagination must let clients reach every task for any `per_page`, with `pages` and `has_next` reflecting the real number of pages.
2. **Ambiguous:** The ticket doesn't define what happens outside the valid range: a page past the last one (keep `400` or return `200` with empty `items`?).
3. **First step:** Reproduce with seed data for several `per_page` values (5, 7, 10, 23, 50) and record `total`, `pages`, `has_next` for each to see exactly which combinations break.

**Questions for the reporter**

1. When the app requests a page past the last one, should the API keep returning `400`, or return `200` with an empty `items` list?
2. Did you see this only on "Mobile App", or also with filters (`status`, `q`) applied?

---

## **TB-102 — Task search returns nothing when typing in lowercase**

**Analysis**

1. **Asks:** Searching with `q` must match tasks regardless of letter case, in both title and description.
2. **Ambiguous:** The scope of "case-insensitive" is open: ASCII only, or also accented characters? And the ticket doesn't say whether search is substring or whole-word, whether multi-word queries are a phrase or separate terms.
3. **First step:** Reproduce `q=login` vs `q=Login` on seed data, then also try a word that only appears in a description and a two-word query, to understand current behaviour before changing it.

**Questions for the reporter**

1. Is ASCII-only case-insensitivity acceptable for this release, or must accented characters (e.g. `É` vs `é`) also match?
2. Should a multi-word query like `login crash` match the exact phrase, or tasks containing all the words in any order?

---

## **TB-103 — Tasks due today are reported as overdue**

**Analysis**

1. **Asks:** A task becomes overdue only after its due date has passed: tasks due today are not overdue, tasks due yesterday (and not done) are.
2. **Ambiguous:** "Today" is undefined: the server's timezone, UTC, or the user's?
3. **First step:** Reproduce with `GET /tasks/overdue` on seed data, check whether `is_overdue` on `GET /tasks/<id>` shows the same problem, and confirm with the reporter which timezone defines "today".

**Questions for the reporter**

1. Which timezone defines "today": the server's, UTC, or each user's? (If the user's, where does the API get it from?)
2. Is a task due today overdue only after midnight, or after the end of the business day?

---

## **TB-104 — Project stats show wrong completion % / HTTP 500**

**Analysis**

1. **Asks:** `completion_rate` must be the percentage of done tasks rounded to one decimal, and a project without tasks must return `200` with `total: 0, completion_rate: 0` instead of a 500.
2. **Ambiguous:** which rounding rule for halves, and whether `0` for an empty project means "0% done" or should be `null` ("no data").
3. **First step:** Reproduce both symptoms (`/projects/1/stats` and `/projects/3/stats`), capture the server stack trace for the 500.

**Questions for the reporter**

1. For an empty project, should the dashboard show `0%`, or a distinct "no tasks yet" state (`null`)?
2. Which rounding rule for halves: round half up (`16.65 → 16.7`) or banker's rounding?

---

## **TB-105 — Changing a task's status wipes all its tags**

**Analysis**

1. **Asks:** `PATCH /tasks/<id>` must change only the fields present in the body, while an explicit `"tags": []` still clears all tags.
2. **Ambiguous:**
3. **First step:** Reproduce on task 1, then PATCH each other field on its own (`title`, `priority`, `due_date`) to check whether any other field is also reset.

**Questions for the reporter**

1. Tags already lost for real users: do we need to restore them (from backups or logs), or is the fix forward-only?
