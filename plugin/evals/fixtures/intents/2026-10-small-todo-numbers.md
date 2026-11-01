---
kind: intent
status: draft
author: ticket reporter (ticket #4)
source: ticket
ref: #4
started: 2026-10-29T00:00:00Z
tags: todo, ids
---
# Intent: Keep todo numbers small

## Problem
"My todo ids keep climbing even though I delete most of what I add." The numbers the reporter types keep getting longer.

## Proposed outcome
"Once a todo is deleted, the next new todo should take its number back, so the numbers I type stay short."

- "Use the smallest number that's free."
- "Nothing else about adding, listing, ticking off or deleting changes."

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- How `add` picks the id of a new todo.

## Constraints
- Nothing else about adding, listing, ticking off or deleting changes (the ticket).
- Python 3.12 standard library only (AGENTS.md).

## Out of scope
Renumbering existing todos, and any change to `list`, `done` or `delete`.

## Open questions
- Does numbering start at 1?
- Do todos already stored keep their ids?
