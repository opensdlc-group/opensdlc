---
kind: intent
status: accepted
author: ticket reporter (ticket #3)
source: ticket
ref: #3
started: 2026-10-29T04:23:53Z
tags: interface, todo, ids, deleted
---
# Intent: Remove todos I no longer need

## Problem
"Some todos stop mattering." Today a todo can be added, listed and ticked off, but there is no way to get rid of one, so a todo that no longer matters stays in the list.

## Proposed outcome
"I want to remove one by its id so it disappears from the list."

- A todo is removed by its id (GLOSSARY: Id) and no longer appears in `./todo list`.
- "An id that doesn't exist is an error and changes nothing."
- "Removing a todo doesn't change the order of the others."
- `./todo delete <id>` prints `{"deleted": <id>}`.

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- The command-line interface, which is a public contract (`knowledge/architecture/interface.md`).
- Wherever todos are stored (the `TODO_FILE` file).

## Constraints
- Ids are permanent and never given to another todo (ADR 0001): after a delete, the remaining todos keep their ids and a later `add` must not reuse the removed one.
- A todo is found by its id, not its place in the list.
- An unknown id changes nothing.
- The other todos keep their order.
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Id, Done. The ticket's "remove" is the glossary's "deleted".

## Out of scope
The ticket asks only for removing one todo by its id. It does not ask for removing several at once, clearing done todos, undoing a delete, or any change to `add`, `list` or `done`.

## Open questions
- `{"deleted": <id>}` is not a todo object, which the interface contract describes for todo output. Is a different shape for this command intended, and does the contract in `knowledge/architecture/interface.md` need extending for it? Is adding a command a breaking change to it?
- Is `<id>` in the output the id as the todo has it (string or integer) or as typed on the command line? Is `./todo delete 3` matched to id `3` whatever its type?
- What does the reporter see for an id that doesn't exist: the message, and the exit status? The contract says an unknown id exits 3 with a one-line message on stderr; is that what is wanted?
- What does `delete` do with a missing id argument, several ids, or an id that is not a number (invalid input, exit 2)?
- May a done todo be deleted? The glossary says a done todo stays "until it is cleared or deleted", which suggests yes.
- Does deleting the todo with the highest id still leave that id unused by the next `add` (ADR 0001), and how is that remembered if the store holds only the remaining todos?
- The ticket gave no opening time, so `started` is when this intent was drafted.
