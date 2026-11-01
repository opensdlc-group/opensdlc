---
kind: intent
status: draft
author: ticket reporter (ticket #4)
source: ticket
ref: #4
started: 2026-10-29T04:28:57Z
tags: interface, todo, due, list, done
---
# Intent: Due dates

## Problem
"Some todos have a deadline, and the list should put them first." Today a todo has only a title, an id and whether it is done (GLOSSARY: Todo), so a deadline cannot be recorded, and the list cannot show which todos are urgent.

## Proposed outcome
- "When I add a todo I can give it a due date, as a calendar date (YYYY-MM-DD)."
- "A date that doesn't exist, like 2026-02-30 or "tomorrow", is an error and saves nothing."
- "Every todo shows its due date, or that it has none."
- "The list shows todos with a due date first, earliest first, then the todos without one. Todos that tie keep the order they were added in."
- "Marking a todo done keeps its due date."

Interface the reporter gives:
- `./todo add <title> --due YYYY-MM-DD` gives the new todo a due date.
- Every todo prints with `"due": "YYYY-MM-DD"`, or `"due": null` when it has none.

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line or from a script.
- The command-line interface, which is a public contract (`knowledge/architecture/interface.md`): `add` gains an option, and every todo gains a `due` field.
- `./todo list` (order), `./todo add` and `./todo done` (output), and wherever todos are stored (the `TODO_FILE` file), including todos saved before this change.

## Constraints
- A due date is a real calendar date written YYYY-MM-DD. Anything else is invalid input: exit 2, a one-line message on stderr, nothing saved (interface contract).
- Add, never take away: `due` is a new field and `--due` a new option; nothing existing is renamed, removed or changed in meaning (`knowledge/policies/public-contract.md`).
- Ids are permanent and never change (ADR 0001); ordering the list must not change any todo's id.
- Marking done keeps the due date.
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Title, Id, Done. "Due date" is not yet defined there; the owners of the glossary may want to add it (proposed, not edited here).

## Out of scope
The ticket asks only for giving a due date when adding, showing it, and ordering by it. It does not ask for changing or removing a due date after a todo is added, reminders or "overdue" marking, due times of day, relative dates, or filtering the list by date.

## Open questions
None. The product owner answered them before accepting:
- Todos saved before this change have no due date: they print `"due": null` and list after the dated ones.
- A date in the past is accepted. Only exactly `YYYY-MM-DD` for a real calendar date is valid; anything else, an empty value or a repeated `--due`, is invalid input.
- `--due` may come before or after the title. A title can no longer contain the bare word `--due`; that is accepted.
- Ties keep the order the todos were added in. Done todos sort the same way as the rest. Only the printed list is ordered; the file is not rewritten.
- `add`, `list` and `done` print `due`. Adding the field is an addition under the public contract, and the product owner adds it to `knowledge/architecture/interface.md` once the change ships.
