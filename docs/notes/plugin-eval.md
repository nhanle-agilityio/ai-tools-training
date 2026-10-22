# Day 7 — Plugin evaluation: pyright-lsp

## What it is

`pyright-lsp@claude-plugins-official` v1.0.0, installed from `/plugin` → Discover, user scope (nothing
written to the repo). The plugin is only configuration: it tells Claude Code to start `pyright-langserver`
for `.py` / `.pyi` files. The language server itself is a separate install (`npm i -g pyright`, 1.1.414).

It gives Claude an `LSP` tool (go to definition, find references, document symbols, hover) and diagnostics
after edits.

## Method

Two prompts, each in a fresh session, before and after installing the plugin:

- **P1, navigation:** list every call site of `is_overdue` and `_serialize_tasks`, and which callers pass
  `now`.
- **P2, diagnostics:** introduce a type error (`.date` instead of `.date()` in `is_overdue`), report any
  problem without running tests, then revert.

A third prompt asked Claude explicitly to use the LSP tool.

## Results

| Run | Before | After | Tools after |
| --- | --- | --- | --- |
| P1 | 13s, 44.6k context | 14s, 44.7k context | Bash (grep), no LSP |
| P2 | 21s, 45.8k context | 16s, 45.9k context | Read, Edit, Bash, no LSP call |
| Forced LSP | — | 10s | `LSP documentSymbol` + `findReferences` |

- **Context cost: none measurable.** System tools stayed at 15.1k; totals moved by 0.1k.
- **Claude did not pick LSP by itself.** In P1 it used grep in both runs. On ~8 Python files, grep is fast
  and complete enough, so the model has no reason to switch.
- **When asked, LSP worked and was more precise.** It found 7 references to the function across 2 files
  (definition, 2 callers, 1 import, 3 test calls) and correctly left out the `"is_overdue"` dict key,
  which a text search would mix in.
- **Diagnostics after edit (P2): no visible effect.** The after-run never mentioned Pyright or a
  diagnostic. Claude found the bug by reading the line, as it did before the plugin, and went further:
  adding `()` would still fail (`str` vs `date`), and `now or datetime.now()` duplicates the line above.
  The model already catches this class of error by reading, so diagnostics added nothing here. I can't
  tell from the transcript whether a diagnostic was delivered and ignored, or never delivered.

## Verdict

**Keep it installed, but don't expect much on this repo.** It costs nothing in context and works, but on a
small codebase Claude prefers grep and gets the same answer.

Where it should pay off:

- Larger codebases, or common names where grep returns noise (`get`, `update`, `status`).
- Renames and "who calls this?" questions where missing one caller is a bug.
- Type errors that need cross-file knowledge (a changed signature used three modules away), which
  reading one line can't reveal. P2 was too local to show this.

Costs and caveats:

- A separate binary to install and keep updated on every machine; the plugin does nothing without it.
- To use it reliably you have to ask for it ("use the LSP tool"), or add a hint to `CLAUDE.md`.
- One run per setting; times are indicative only.
