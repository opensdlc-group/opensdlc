---
kind: plan
status: implemented
spec: spec.md@74d6e3d4e425
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Plan: Remove todos I no longer need

## Files that change
changes/2026-10-remove-todos-i-no-longer-need/plan.md this plan
src/todo_cli/__main__.py command dispatch gains `delete`: parse the id before the store is read, print `{"deleted": <id>}`, map an unknown id to exit 3
src/todo_cli/store.py gains `delete(store, todo_id)`: find the todo by its integer id, remove it, leave `next_id` alone, raise `UnknownId` when none matches
src/todo_cli/ids.py `parse` takes the command name so the "takes exactly one id" message names `delete` or `done`
tests/test_delete.py new: end-to-end tests through the `./todo` command line, one per acceptance criterion

No other file changes. `knowledge/architecture/interface.md` and `GLOSSARY.md` are owned by others; updating the contract document is already a Carried-forward Question in the spec and is not touched here. `Makefile`, `todo`, `tests/test_smoke.py`, `tests/test_add_list.py` and `tests/test_done.py` stay as they are (criterion 16 is proved by them still passing unedited).

## Slices
Tests come first at the one seam the spec names: `./todo` run as a subprocess with `TODO_FILE` in a temporary directory. `tests/test_delete.py` copies the helper style of `tests/test_done.py` (`run_todo`, `assert_refused`, `assert_refused_unchanged`) rather than importing it, so the test files stay independent. Each slice leaves `make build`, `make test` and `make lint` green.

1. **`delete <id>` on a valid, existing id.** Blocked by: none.
   Prefactoring first: `ids.parse(args)` hard-codes "done takes exactly one id". Change it to `parse(command, args)` and update the one `done` call in `__main__.py`; `done` behavior and message are unchanged (`tests/test_done.py` stays green unedited). Then add `store.delete`: match on `type(todo.get("id")) is int and == todo_id` (never by list position, ADR 0001; a bool is not an id), remove that one todo from `store["todos"]` without touching any other, leave `next_id` as it is, and return the removed id. In `main`, the `delete` branch parses the id before `TODO_FILE` or the store is read, calls `store.delete`, saves with the existing atomic write, and prints `json.dumps({"deleted": id})` (compact, single line, integer value). The existing `changed` flag is true for `delete`, so it saves.
   The unknown-id path raises `store.UnknownId` (already mapped to exit 3 in `main`), so slice 1 already refuses unknown ids before any save; slice 2 proves and completes the refusals.
   Acceptance criteria: 1, 2, 4, 5, 6, 7, 8, 12, 16.

2. **Refusals: unknown id, bad argument, bad environment.** Blocked by: 1.
   Tests and any small fixes for the refusals. `ids.parse` already rejects missing, several and non-digit arguments with exit 2 (shared with `done`), and `delete` uses it with its own name in the message. `UnknownId` produces exit 3 with `todo: no todo with id N` on stderr, empty stdout, and never reaches `save`, so a missing store file is not created and an existing one is not rewritten. Id 0, ids above `next_id` and already-deleted ids are simply unknown. `TODO_FILE` unset is exit 2 and an unreadable store is exit 1, through the code that already handles them for the other commands.
   Acceptance criteria: 3, 9, 10, 11, 13, 14, 15.

## Risks
- **Riskiest: ids must stay permanent (ADR 0001).** Any delete that recomputed `next_id` from the remaining todos would reissue the highest id. `store.delete` never writes `next_id`; criteria 4 to 6 prove it through `add` and `list`, including deleting the highest id and deleting everything.
- **Touching `ids.parse` changes shipped `done` code.** The change is only a new `command` parameter used in one message. `tests/test_done.py` must pass unedited. It asserts one-line stderr, not the text, so the message wording is not pinned by existing tests.
- **Refused commands must not touch the store.** Argument parsing runs before any load, and the unknown-id path returns before `save`. Tests compare the store's bytes, or its absence, before and after every refusal.
- **Matching the wrong todo.** Matching by position would let an id shift after earlier deletes. Tests delete id 1 and then act on 3 and 1 (criterion 8) to prove ids are by value. Tests seed through `add` only.
- **Removing while iterating.** Find the index first, then `del`/`pop` once and return; no mutation inside a loop that continues.
- **Leading zeros.** `02` is accepted as id 2, as the spec builds it and as `done` does. A stricter rule would be a later, contract-visible tightening noted in the spec; only `ids.py` and tests would change.
- **Public contract.** An addition only: one command with a second output shape. No auth, PII, payments, migration or infra, and the store layout is unchanged. Hence `low`. Deleting is destructive for the named todo, as requested, and there is no undo (out of scope).
- **Plan departures.** If the build departs from this file list or slice order, update this plan in the same commit.

## Alternatives considered
- **Recompute `next_id` as max id + 1 after delete.** Reissues the highest id; violates ADR 0001. Rejected.
- **Mark todos as deleted instead of removing them (tombstones).** Changes the store layout and `list`; nothing needs it, since `next_id` already guarantees permanence. Rejected.
- **A separate `ids.parse_delete`, or leave the `done` wording in the message.** Duplicates a rule the spec says is shared; the spec asks the message to name `delete`. A `command` parameter is the smaller change.
- **Print the removed todo instead of `{"deleted": id}`.** The spec and ticket fix the shape.
- **Return a not-found flag rather than raise `UnknownId`.** `done` already uses the exception and `main` already maps it; one pattern is simpler.
- **Unit tests per module.** The spec chooses the command line as the only seam; module tests would pin internals.
- **Tickets per slice.** The team works from this change folder; none created.

## Proof
Run from the repository root:

- `make build` prints nothing.
- `make lint` prints nothing.
- `make test` ends with `OK`. `tests/test_delete.py` has at least one test per acceptance criterion, named after it, each setting up todos by running `add` and asserting on parsed JSON:
  - 1: with "Buy milk", "Walk dog", "Call mum" added, `delete 2` prints `{"deleted": 2}`, exit 0.
  - 2: `list` afterwards has exactly ids 1 and 3 in that order, titles and `done` unchanged.
  - 3: a second `delete 2` exits 3, one-line stderr, empty stdout, store bytes unchanged.
  - 4: after `delete 2`, `add "Feed cat"` issues id 4.
  - 5: after `delete 3`, `add "Feed cat"` issues id 4; ids 1 and 2 keep their titles.
  - 6: after deleting 1, 2 and 3, `list` prints `[]` and `add` issues id 4.
  - 7: `done 1` then `delete 1` prints `{"deleted": 1}`, exit 0, and `list` no longer shows it.
  - 8: after `delete 1`, `list` has ids 2 and 3 with their titles; `done 3` ticks "Call mum" and `done 1` exits 3.
  - 9, 10: `delete 7` and `delete 0` exit 3, one-line stderr, empty stdout, store bytes unchanged.
  - 11: `delete 1` with no store file exits 3 and the file is still absent.
  - 12: `delete 02` removes id 2, prints `{"deleted": 2}`, exit 0.
  - 13: `delete`, `delete 1 2`, `delete abc`, `delete -1`, `delete 1.0`, `delete ""`, `delete " 1"` each exit 2 with the refusal checks above.
  - 14: `TODO_FILE` unset makes `delete 1` exit 2 with a message.
  - 15: a store holding invalid JSON makes `delete 1` exit 1 with a message, file unchanged.
  - 16: `tests/test_add_list.py`, `tests/test_done.py` and `tests/test_smoke.py` pass unedited.
- By hand, with `TODO_FILE="$TMPDIR/todo.json" ./todo add "Buy milk"`, then `./todo delete 1`, then `./todo list` (prints `[]`), then `./todo add "Walk dog"` (issues id 2), as in AGENTS.md.
