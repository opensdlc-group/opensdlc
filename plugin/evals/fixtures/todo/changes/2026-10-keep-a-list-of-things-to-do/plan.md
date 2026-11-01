---
kind: plan
status: implemented
spec: spec.md@30699dfc9e12
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: standard
---
# Plan: Keep a list of things to do

## Files that change
changes/2026-10-keep-a-list-of-things-to-do/plan.md this plan
src/todo_cli/__main__.py command dispatch for `add` and `list`, exit statuses and stderr messages (the entry point keeps `main(argv)` and the usage message)
src/todo_cli/store.py new: read the `TODO_FILE` store, atomic write, issue ids from the stored counter, `StoreError` for an unreadable store
src/todo_cli/title.py new: title rules (join arguments, drop whitespace at the ends, empty and 200-character checks)
tests/test_add_list.py new: end-to-end tests through the `./todo` command line, one per acceptance criterion

No other file changes. `knowledge/architecture/interface.md` and `GLOSSARY.md` are owned by others and are proposed for update in the spec's Carried-forward Questions, not touched here. `Makefile`, `todo` and `tests/test_smoke.py` stay as they are.

## Slices
Tests are written first at the one seam the spec names: `./todo` run as a subprocess with `TODO_FILE` in a temporary directory. Each slice leaves `make build`, `make test` and `make lint` green.

1. **Dispatch, store and `list`.** Blocked by: none.
   Prefactoring for the rest: add `store.py` (load returns an empty store when the file is missing; invalid JSON or the wrong shape raises `StoreError`; save writes a temporary file in the same directory then `os.replace`s it) and make `main` dispatch on the first argument. Store layout: `{"next_id": 1, "todos": []}`. `list` loads the store, writes it back (the contract says every command writes the store; this also creates the file), prints `todos` as compact JSON, exits 0.
   Errors: no command keeps the existing usage message and exit 2; an unknown command, extra arguments to `list`, or `TODO_FILE` unset exit 2 with a one-line stderr message and empty stdout; `StoreError` exits 1 with a one-line stderr message and the file untouched. Validation happens before any write.
   Acceptance criteria: 1, 12 (for `list`), 13, 14, 15 (for `list`).

2. **`add` with ids.** Blocked by: 1.
   `add` takes the arguments joined with one space as the title, loads the store, builds `{"id": next_id, "title": ..., "done": false}`, appends it, sets `next_id` to id + 1, saves both in one write, prints the todo as compact JSON. The id comes only from `next_id`, never from the list. Title rules are minimal in this slice (join and strip only); slice 3 adds the refusals.
   Acceptance criteria: 2, 3, 4, 5, 9, 10, 11, 12 (for `add`), 15 (for `add`).
   Test for 10 seeds a store file with `next_id` 5 and highest id 2, the deliberate exception the spec names; it is replaced by add, delete, add when the delete ticket lands.

3. **Title rules.** Blocked by: 2.
   `title.py` holds the rules and returns the title or raises `TitleError("title is empty")` / `TitleError("title is longer than 200 characters")`. `main` turns that into exit 2, stderr message, empty stdout, store untouched. Whitespace of any kind at either end is dropped (`str.strip()`); inner text is kept; length is `len()` of the stripped string (code points). The title check runs before the store is read, so a refused title never creates the file.
   Acceptance criteria: 6, 7, 8 (and 4, 5 again).

## Risks
- **Riskiest: slice 2, the id counter.** If the id were taken from the list (highest + 1) it would pass every test except 10 and break ADR 0001 once delete exists. Test 10 guards it; `next_id` is saved in the same write as the todo.
- **Atomic write.** `os.replace` needs the temporary file on the same filesystem, so it is created in the store's directory. A directory that is not writable surfaces as an OS error. Decision: let `OSError` on read or write exit 1 with a one-line message, like an unreadable store, rather than a traceback. This stays within the spec's "exit 1" and adds no new status.
- **Refused commands must not touch the store.** Title and argument validation run before any load or save; tests compare the file's bytes (or absence) before and after.
- **A lost store restarts ids at 1.** Known and carried forward in the spec; not solved here.
- **Public contract.** Only additions (two commands, exit 1), so risk is `standard`, not `high`. No auth, PII, migration or infra.
- **Plan departures.** If the build departs from this file list or slice order, update this plan in the same commit.

## Alternatives considered
- **Id = highest existing id + 1.** Simpler, no counter, but reissues the id of a deleted newest todo. Rejected by ADR 0001 and the spec.
- **Store as a bare JSON array.** Has nowhere to keep the counter. Rejected.
- **Title rules inside `__main__.py`.** Fewer files, but later tickets (edit title) would need them elsewhere. A small `title.py` costs little.
- **Not writing the store on `list`.** Would contradict the contract line "every command reads it and writes it back". Kept as the spec says.
- **Unit tests per module.** The spec chooses the command line as the only seam; module tests would pin internals.
- **One slice for everything.** Rejected: three slices each verify on their own and fit one context window.
- **Tickets per slice.** The team works from this change folder; none created.

## Proof
Run from the repository root:

- `make build` prints nothing.
- `make lint` prints nothing.
- `make test` ends with `OK`. `tests/test_add_list.py` has at least one test per acceptance criterion, named after it:
  - 1: `list` on a missing file prints `[]`, exit 0.
  - 2, 11: `add "Buy milk"` prints an object with exactly `id` 1, `title` "Buy milk", `done` false, and equals the matching item in `list`.
  - 3, 9: two adds then `list` gives both in order with ids 1 and 2, and the same ids on a later `list`.
  - 4, 5: surrounding spaces dropped; unquoted words joined.
  - 6, 7: 200 characters saved, 201 refused (exit 2, stderr message, empty stdout, store unchanged or absent), 200 plus spaces at both ends saved.
  - 8: `""`, `"   "` and no argument refused the same way.
  - 10: seeded store with `next_id` 5 and highest id 2 issues 5 then 6.
  - 12: invalid JSON store makes `add` and `list` exit 1 with a message and the file unchanged.
  - 13: `frobnicate` and `list extra` exit 2, empty stdout.
  - 14: no command prints usage, exit 2 (the existing smoke test also stays green).
  - 15: `TODO_FILE` unset makes `add` and `list` exit 2 with a message.
- By hand, with `TODO_FILE="$TMPDIR/todo.json" ./todo add "Buy milk"` then `./todo list`, as in AGENTS.md.
