---
kind: plan
status: implemented
spec: spec.md@80b8cad3f62f
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Plan: Tick todos off

## Files that change
changes/2026-10-tick-todos-off/plan.md this plan
src/todo_cli/__main__.py command dispatch gains `done`: parse the id before the store is read, skip the write when nothing changed, map an unknown id to exit 3
src/todo_cli/store.py gains `mark_done(store, todo_id)`: find the todo by its integer id, set `done`, return it, raise `UnknownId` when none matches
src/todo_cli/ids.py new: parse the `done` argument into an integer id (ASCII digits only), raise `IdError` otherwise; sits beside `title.py` for the same reason
tests/test_done.py new: end-to-end tests through the `./todo` command line, one per acceptance criterion

No other file changes. `knowledge/architecture/interface.md` and `GLOSSARY.md` are owned by others; updating the contract document is already a Carried-forward Question in the spec and is not touched here. `Makefile`, `todo`, `tests/test_smoke.py` and `tests/test_add_list.py` stay as they are (criterion 13 is proved by them still passing).

## Slices
Tests come first at the one seam the spec names: `./todo` run as a subprocess with `TODO_FILE` in a temporary directory. `tests/test_done.py` reuses the helper style of `tests/test_add_list.py` (`run_todo`, `assert_refused`, `assert_refused_unchanged`), copied rather than imported so the two files stay independent. Each slice leaves `make build`, `make test` and `make lint` green.

1. **`done <id>` on a valid, existing id.** Blocked by: none.
   Prefactoring first: `main` currently builds `output` inline for `list` and `add` and always saves. Restructure it so each command yields its output plus a flag saying whether the store changed, and `save` runs only when it did. `list` and `add` keep their behavior exactly, including `list` writing the store back (the contract says every command writes it, and `list` creates the file). Then add `store.mark_done` and the `done` branch: the argument is read as `int(arg)`, the todo is matched on `type(id) is int` and equality (never by list position, ADR 0001; a bool is not an id), `done` is set to `true`, the store is saved with the existing atomic write, and the todo is printed as compact JSON with `id`, `title`, `done`. Nothing else in the store is touched, so order and `next_id` stay. A todo that is already done is returned without a change and without a save, so the store bytes are untouched and the output is identical to a first tick.
   In this slice the id is parsed minimally (`int(arg)` on a single argument); slice 2 replaces that with the strict rules.
   Acceptance criteria: 1, 2, 3, 4, 8, 12, 13.

2. **Refusals: unknown id, bad argument.** Blocked by: 1.
   `ids.py` accepts a string only if it is non-empty and every character is an ASCII digit (`str.isascii() and str.isdigit()`, which also rules out Unicode digits such as `٣` that `int()` would take), and returns `int(text)`; otherwise raises `IdError("id must be digits only: ...")`. `main` turns `IdError`, a missing id, or more than one argument into exit 2 with a one-line stderr message and empty stdout, before `TODO_FILE` or the store is read (as `add` does for its title). `store.mark_done` raises `UnknownId` and `main` turns that into exit 3 with `todo: no todo with id N` on stderr and empty stdout. The unknown-id path never calls `save`, so a missing store file is not created and an existing one is not rewritten. `TODO_FILE` unset is exit 2 and an unreadable store is exit 1, through the code that already handles them for the other commands. Id 0 and ids above `next_id` are simply unknown.
   Acceptance criteria: 5, 6, 7, 9, 10, 11.

## Risks
- **Riskiest: the `main` restructure in slice 1.** It touches `add` and `list`, which are shipped public behavior. Mitigation: the restructure is the first step of the slice and `tests/test_add_list.py` and `tests/test_smoke.py` must stay green unedited (criterion 13).
- **Refused commands must not touch the store.** Argument parsing runs before any load, and the unknown-id path returns before `save`. Tests compare the store's bytes, or its absence, before and after every refusal.
- **Matching the wrong todo.** Matching by position, or by `==` alone, would let `True` match id 1 in a hand-edited store, and string ids are deliberately never matched (spec: Id argument). Tests seed ids through `add` only, so a hand-seeded store is out of the proof; the id-by-value rule is covered by ticking id 2 after id 1 and checking the right todo changed.
- **Leading zeros.** `02` is accepted as id 2, as the spec builds it. If the product owner later wants it refused, that is a contract-visible tightening, noted in the spec's Carried-forward Questions. Only `ids.py` and one test would change.
- **Public contract.** Only an addition (one command, first use of exit 3). No auth, PII, payments, migration or infra. Hence `low`: small blast radius, covered by existing tests, additions only.
- **Plan departures.** If the build departs from this file list or slice order, update this plan in the same commit.

## Alternatives considered
- **Parse the id in `__main__.py` or `store.py`.** Fewer files, but the strict digits rule is a contract decision that deserves a named home beside `title.py`, and the delete ticket will need the same rule. A small `ids.py` costs little.
- **Parse with bare `int()`.** Accepts `-1`, `+3`, ` 1`, `1_0` and Unicode digits, all of which the spec says exit 2. Rejected.
- **Save the store on an already-done tick.** Would be harmless (same bytes) but writes for no reason and makes criterion 3 depend on serialisation being stable. Skipped.
- **Save on an unknown id, to create the file as the contract says.** Contradicts "change nothing"; the spec resolves it in favour of change nothing.
- **Match string ids too.** The product only issues integers; matching strings would add a rule nothing can exercise.
- **Unit tests per module.** The spec chooses the command line as the only seam; module tests would pin internals.
- **Separate slices for the restructure and the happy path.** The restructure has no behavior of its own to verify apart from the existing tests, so it is the first step of slice 1 rather than a slice.
- **Tickets per slice.** The team works from this change folder; none created.

## Proof
Run from the repository root:

- `make build` prints nothing.
- `make lint` prints nothing.
- `make test` ends with `OK`. `tests/test_done.py` has at least one test per acceptance criterion, named after it, each setting up todos by running `add` and asserting on parsed JSON:
  - 1: with "Buy milk", "Walk dog", "Call mum" added, `done 2` prints `{"id": 2, "title": "Walk dog", "done": true}`, exit 0.
  - 2: `list` afterwards has ids 1, 2, 3 in order, only 2 done, titles and ids unchanged.
  - 3: a second `done 2` prints the same object, exit 0, and the store bytes equal those before the call.
  - 4: the `done` output equals the matching item in `list`.
  - 5, 6: `done 7` and `done 0` exit 3, one-line stderr, empty stdout, store bytes unchanged.
  - 7: `done 1` with no store file exits 3 and the file is still absent.
  - 8: `done 02` marks id 2 done, exit 0.
  - 9: `done`, `done 1 2`, `done abc`, `done -1`, `done 1.0`, `done ""`, `done " 1"` each exit 2 with the refusal checks above (a Unicode digit such as `٣` is added to this list).
  - 10: `TODO_FILE` unset makes `done 1` exit 2 with a message.
  - 11: a store holding invalid JSON makes `done 1` exit 1 with a message, file unchanged.
  - 12: after `done 2`, `add "Feed cat"` issues id 4 and ids 1 to 3 keep their titles.
  - 13: `tests/test_add_list.py` and `tests/test_smoke.py` pass unedited.
- By hand, with `TODO_FILE="$TMPDIR/todo.json" ./todo add "Buy milk"`, then `./todo done 1`, then `./todo list`, as in AGENTS.md.
