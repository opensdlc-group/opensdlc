---
kind: intent
status: accepted
author: ticket reporter (ticket #2)
source: ticket
ref: #2
started: 2026-10-29T04:19:12Z
tags: interface, todo, ids, done
---
# Intent: Tick todos off

## Problem
"When I finish something I want to mark it done by its id, and still see it in the list, shown as done." Today a todo can be added and listed, but there is no way to say it is finished.

## Proposed outcome
"I want to mark it done by its id, and still see it in the list, shown as done."

- A todo is marked done by its id.
- A done todo stays in `./todo list`, shown as done (GLOSSARY: Done).
- "Marking a done todo done again changes nothing."
- "An id that doesn't exist is an error and changes nothing."
- `./todo done <id>` prints the todo after marking it done.

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- The command-line interface, which is a public contract (`knowledge/architecture/interface.md`).
- Wherever todos are stored (the `TODO_FILE` file).

## Constraints
- Ids are permanent and never change (ADR 0001); a todo is found by its id, not its place in the list.
- An unknown id changes nothing.
- Marking done again changes nothing.
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Id, Done.

## Out of scope
The ticket asks only for marking a todo done. It does not ask for un-marking, deleting, clearing, or hiding done todos from the list.

## Open questions
- What does `done` print for a todo that was already done: the todo as before, with the same shape as after a first tick?
- What does the reporter see for an id that doesn't exist: the message, and the exit status? The interface contract says an unknown id exits 3 with a one-line message on stderr; is that what is wanted?
- What does `done` do with a missing id argument, several ids, or an id that is not a number (invalid input, exit 2)?
- Ids may be a string or an integer in the contract: is `./todo done 3` matched to id `3` whatever its type?
- Does `list` keep todos in the same order after one is ticked off, and how is "shown as done" expressed (the `done` field becoming `true`)?
- Does the interface contract in `knowledge/architecture/interface.md` need extending for `done`, and is adding a command a breaking change to it?
