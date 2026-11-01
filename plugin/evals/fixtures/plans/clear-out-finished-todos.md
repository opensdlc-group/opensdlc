---
kind: plan
status: draft
spec: spec.md@956f888418af
context: knowledge/architecture/interface.md@0afec65d1a8a, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Plan: Clear out finished todos

## Files that change
changes/2026-10-clear-out-finished-todos/plan.md this plan
src/todo_cli/__main__.py command dispatch gains `clear`: accepted only with no arguments (checked before `TODO_FILE` or the store is read), prints `{"removed": <count>}`
src/todo_cli/store.py gains `clear_done(store)`: removes every todo whose `done` is `True`, leaves `next_id` alone, returns the count
tests/test_clear.py new: end-to-end tests through the `./todo` command line, one per acceptance criterion

No other file changes. `knowledge/architecture/interface.md` and `GLOSSARY.md` are owned by others; updating the contract document is already a Carried-forward Question in the spec and is not touched here. `Makefile`, `todo`, `src/todo_cli/ids.py`, `src/todo_cli/title.py` and the existing tests stay as they are (criterion 14 is proved by them still passing unedited).

## Slices
Tests come first at the one seam the spec names: `./todo` run as a subprocess with `TODO_FILE` in a temporary directory. `tests/test_clear.py` copies the helper style of `tests/test_delete.py` (`run_todo`, `assert_refused`, `assert_refused_unchanged`, `listed`, `added_id`) rather than importing it, so the test files stay independent. Todos are set up with `add` and `done` only; "id never reissued" is checked through `add` and `list`, never by reading `next_id`. No prefactoring is needed: `delete` already established that `next_id` is kept apart from the todos and that `save` is atomic. Each slice leaves `make build`, `make test` and `make lint` green.

1. **`clear` with done todos present.** Blocked by: none.
   Add `store.clear_done(store)`: build the kept list with a comprehension that keeps every todo for which `todo.get("done") is not True` (so a missing or malformed `done` stays), assign it back to `store["todos"]` once, never write `next_id`, and return `before - after`. Order and every field of the kept todos are untouched. In `main`, the dispatch condition `command == "list" and not args` becomes `command in ("list", "clear") and not args`; `clear` with arguments therefore falls to the existing unknown-command branch, which refuses with exit 2 and a one-line message that includes `clear` and runs before `TODO_FILE` or the store is read. After `store.load`, the `clear` branch sets `output = {"removed": store.clear_done(data)}`. The existing `changed = True` default means the store is saved with the existing atomic write, so a missing file is created holding an empty list and `next_id` 1 (as `list` does), and a clear is all done todos or none. Output is `json.dumps(output)`: compact, single line, integer value. Saving when the count is 0 rewrites the same parsed contents; the spec leaves that to the plan.
   Acceptance criteria: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14.

2. **Refusals.** Blocked by: 1.
   Tests, and small fixes if any fail, for `clear 1`, `clear all`, `clear ""` (exit 2, one-line stderr, empty stdout, store bytes unchanged, done todos still listed), `TODO_FILE` unset (exit 2 with a message) and a store holding invalid JSON (exit 1 with a message, file unchanged). All go through code that already handles them for the other commands; this slice proves it for `clear`.
   Acceptance criteria: 11, 12, 13.

## Risks
- **Riskiest: ids must stay permanent (ADR 0001).** A clear that recomputed `next_id` from the remaining todos would reissue the highest cleared id, or id 1 after clearing everything. `clear_done` never writes `next_id`; criteria 4, 5 and 6 prove it through `add` and `list`, including clearing the highest id and clearing every todo.
- **Clearing the wrong todos.** The spec says a todo goes exactly when `done` is JSON `true`. Using truthiness would remove a hand-edited `"done": 1` or `"yes"`. The test for criterion 2 and 7 cover not-done todos staying; the comprehension uses `is not True`, matching `mark_done`.
- **Refused commands must not touch the store.** Arguments are checked in the dispatch before any load; the tests compare the store's bytes before and after every refusal.
- **Argument handling rides on the unknown-command branch.** Its message is `unknown command or arguments: clear 1`, which names `clear` and is one line, as the spec requires. If a later change reworded that branch, the criterion 11 tests would catch it only through the one-line and exit-2 checks, not the wording.
- **Destructive with no undo.** As requested; it touches only done todos, and the intent's Out of scope excludes undo and confirmation.
- **Public contract.** An addition only: one command with a second output shape. No auth, PII, payments, migration or infra, and the store layout is unchanged. Hence `low`.
- **Plan departures.** If the build departs from this file list or slice order, update this plan in the same commit.

## Alternatives considered
- **Recompute `next_id` as max id + 1 after clear.** Reissues the highest cleared id; violates ADR 0001. Rejected.
- **Save only when something was removed.** A missing store file would then not be created, which differs from `list` and the contract's rule that commands create a missing file (criterion 8 expects `list` afterwards to work either way, but the spec chose creation). Always saving is the smaller change: the existing `changed = True` default.
- **A dedicated argument check with its own message for `clear`.** Reuses nothing and duplicates the unknown-command branch; the existing message already names `clear` and exits 2. Rejected as extra code.
- **Remove by looping `delete` over done ids.** Several writes, so a failure could leave half a clear; the spec requires all or none. Rejected.
- **Truthiness test for `done`.** Rejected; see Risks.
- **Unit tests per module.** The spec chooses the command line as the only seam; module tests would pin internals.
- **Tickets per slice.** The team works from this change folder; none created.

## Proof
Run from the repository root:

- `make build` prints nothing.
- `make lint` prints nothing.
- `make test` ends with `OK`. `tests/test_clear.py` has at least one test per acceptance criterion, named after it, each setting up todos by running `add` and `done` and asserting on parsed JSON. With "Buy milk" (1), "Walk dog" (2), "Call mum" (3), "Feed cat" (4) added and `done 1`, `done 3` run:
  - 1: `clear` prints `{"removed": 2}` (one key, integer value), exit 0, empty stderr.
  - 2: `list` afterwards has exactly ids 2 and 4, in that order, titles and `done` false unchanged.
  - 3: a second `clear` prints `{"removed": 0}`, exit 0, and `list` is unchanged.
  - 4: after the first clear, `add "Water plants"` issues id 5.
  - 5: with todos 1 to 3 and only `done 3`, `clear` prints `{"removed": 1}`; the next `add` issues id 4; ids 1 and 2 keep their titles.
  - 6: with every todo done, `clear` prints the count, `list` prints `[]`, and the next `add` issues the id after the highest ever issued.
  - 7: with none done, `clear` prints `{"removed": 0}`, exit 0, and `list` shows every todo unchanged and in order.
  - 8: after `add` and `delete` of the only todo, `clear` prints `{"removed": 0}`, exit 0; with no store file, it exits 0 and `list` then prints `[]`.
  - 9: after clearing 1 and 3, `done 2` and `done 4` tick "Walk dog" and "Feed cat", and `done 1` exits 3.
  - 10: after `done 1` and a clear, `delete 1` and `done 1` exit 3.
  - 11: `clear 1`, `clear all`, `clear ""` each exit 2, one-line stderr, empty stdout, store bytes unchanged.
  - 12: `TODO_FILE` unset makes `clear` exit 2 with a message.
  - 13: a store holding invalid JSON makes `clear` exit 1 with a message, file unchanged.
  - 14: `tests/test_add_list.py`, `tests/test_done.py`, `tests/test_delete.py` and `tests/test_smoke.py` pass unedited.
- By hand, with `TODO_FILE="$TMPDIR/todo.json" ./todo add "Buy milk"`, `./todo add "Walk dog"`, `./todo done 1`, then `./todo clear` (prints `{"removed": 1}`), `./todo list` (only "Walk dog", id 2), and `./todo add "Feed cat"` (issues id 3), as in AGENTS.md.
