# Review checklist

Use it for every PR on TaskBoard, whether a person, `/code-review`, the `code-reviewer` agent or the
`devflow/review` bot does the review. Each item exists because a review in this repo missed it or caught
it; the source is in brackets. The issue and its spec are the source of truth, not the current code.

## 1. Scope

- [ ] The PR closes one issue (`Closes #n`) and changes only what that issue asks. Anything else found
      on the way is mentioned, not fixed. [CLAUDE.md; Day 10: 5 real bugs outside the ticket became
      proposed tickets]
- [ ] Every acceptance criterion of the issue is met, and no criterion was edited to make a test pass.
- [ ] Ambiguous requirements are asked about or written down as an assumption in the PR, never decided
      silently. [#73: the soft-deleted-project rule was stated as an assumption, then confirmed]
- [ ] The risk label is right: anything under `taskboard/schema.sql`, `taskboard/db.py`, `.github/**`
      or `.claude/**`, or anything that can lose data, is `risk:high` and merged by a person.

## 2. Tests

- [ ] The first commit is a test that fails on the old code; the fix comes in a later commit.
- [ ] Each `must` row of the spec's test matrix has a test that sets up its Given, does its When and
      asserts its whole Then: status **and** the key body values (`pagination.total`, counts, order).
      [#74: three tag-filter tests checked ids but not `total`; #70: a seed test checked "some project
      exists" instead of every seeded project]
- [ ] A test that changes data re-reads it through the API or the database; checking only the response
      is a fake-green test. [Day 10 seeded bug S5: `/code-review` caught it, ultrareview missed it]
- [ ] Tests go through the HTTP layer with the `client` / `project` / `make_task` fixtures, and do not
      depend on the developer's real `instance/` database or on the shell environment.
- [ ] QA test files are formatted before they are committed, so a later `ruff format` does not count as
      a change to the QA test. [#73 was blocked by a line wrap]

## 3. Correctness

- [ ] Every query that reads tasks also excludes soft-deleted tasks **and** tasks of soft-deleted
      projects. The API cascade hides a missing `projects` join. [#73: `/tasks/overdue` counted tasks of
      a project deleted in the database]
- [ ] Two endpoints that report the same number agree on the same data. [Stats acceptance, AC2.5]
- [ ] Writes are committed, and the response matches what was stored. [Day 10 S4: no `commit()`, the
      response still said `completed: 2`]
- [ ] `updated_at` changes on every update, and only on the rows that changed. [Day 10 S7]
- [ ] Bad input returns 400 and a missing resource 404, never 500: `null` or a list where a string is
      expected, `true` as an id (`bool` is an `int`), integers too large for SQLite. [Day 10 tickets A-C]
- [ ] Error handling covers the step after the main action: a cleanup step that fails must not lose the
      result of the step before it. [#63: the gate's merge marker was lost when deleting the branch failed]

## 4. Data and schema

- [ ] No `DROP`, `DELETE` without `WHERE`, or reset runs on startup or on deploy. Schema creation is
      idempotent (`CREATE ... IF NOT EXISTS`). [Railway spec, #70]
- [ ] A change to the schema says what happens to an existing database (new file, old file, partial
      schema) and has a test for each case.

## 5. Architecture and security

- [ ] Layers are not skipped: `routes.py` (HTTP only) → `services.py` → `repository.py` (all SQL) →
      `db.py`. [Day 10 S3: SQL in a route]
- [ ] User input never reaches SQL through string formatting; values are bound parameters, and column
      names come from an allow-list. [Day 10 S1: SQL injection through `?tag=`]
- [ ] User input is normalised the same way it is stored (tags: lowercase, stripped). [Day 10 S2]
- [ ] No secret, token or real credential is committed or pasted into a PR, issue or chat.

## 6. Process

- [ ] Branch `{type}/<issue>-<slug>` from `feature/example_taskboard`; Conventional Commits with the
      issue number as scope; small commits.
- [ ] Everything committed is in English. No `Co-Authored-By` or AI attribution.
- [ ] CI (`test`) and `devflow/review` are green, and every review thread has a reply: fixed in a
      commit, answered, or declined with a reason.
- [ ] When a tool reports a PR as merged or not merged, check `merged_at` (`pull_request_read`) or
      `git merge-base --is-ancestor`; the GitHub MCP list tools always say `merged: false`.

## Which reviewer for which job

| Reviewer | Use it for | Watch out for |
| --- | --- | --- |
| `/code-review` | Every PR; a focused diff of a few files | It does not run the code: reproduce a finding before acting on it |
| `devflow/review` bot | Every PR, automatically, against the issue's criteria | A warning blocks the gate; reply on the thread |
| `/security-review` | Any change that touches input parsing, SQL or auth | Verify the exploit path it reports |
| Ultrareview | A deep pass over a large or risky area, not a five-file diff | It missed a test-quality bug; check its scope (branch vs `main`) |
| `/devflow:accept` | After merge: does what shipped match the spec | Runs over HTTP only; DB-level rows need a human |
| A test-coverage pass | Must rows against the tests, once per spec | Coverage by test names alone is not enough: read the asserts |
