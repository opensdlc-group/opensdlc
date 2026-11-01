---
kind: intent
status: draft
author: ticket reporter (ticket #4)
source: ticket
ref: #4
started: 2026-10-29T04:42:25Z
tags: interface, todo, done, deleted
---
# Intent: Clear out finished todos

## Problem
"The list fills up with done todos." Today a done todo (GLOSSARY: Done) stays in the list until someone deletes it, so the reporter has to deal with finished todos one at a time.

## Proposed outcome
"I want to remove all of them in one step and be told how many went."

- Every done todo is removed in a single step.
- "Todos that aren't done stay, in the same order."
- "If nothing is done, nothing is removed and I'm told none went."
- `./todo clear` removes every done todo and prints `{"removed": <count>}`.

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- The command-line interface, which is a public contract (`knowledge/architecture/interface.md`).
- Wherever todos are stored (the `TODO_FILE` file).

## Constraints
- Todos that are not done keep their ids and their order.
- Ids are permanent and never given to another todo (ADR 0001): after a clear, a later `add` must not reuse the id of a todo that went.
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Done, Id. The ticket's "remove" is the glossary's "deleted"; the glossary already names this action "cleared".

## Out of scope
The ticket asks only for removing all done todos at once. It does not ask for removing one todo by its id, removing todos that are not done, undoing a clear, or any change to `add`, `list` or `done`.

## Open questions
- `{"removed": <count>}` is not a todo object, which the interface contract describes for todo output. Is a different shape intended, and does `knowledge/architecture/interface.md` need extending? Is adding a command a breaking change to the contract?
- Is `<count>` a JSON integer? When nothing is done, is it `{"removed": 0}`? The ticket says only "I'm told none went".
- Does `clear` take any arguments? What should happen if one is given (invalid input, exit 2)?
- Does `clear` on an empty list, or one with no done todos, exit 0 and leave the file unchanged?
- Does clearing the todo with the highest id still leave that id unused by the next `add` (ADR 0001), and how is that remembered if the store holds only the remaining todos?
- The ticket gave no opening time, so `started` is when this intent was drafted.
