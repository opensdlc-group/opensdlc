---
kind: intent
status: draft
author: ticket reporter (ticket #4)
source: ticket
ref: #4
started: 2026-10-29T00:00:00Z
tags: interface, todo, ids, deleted
---
# Intent: Keep todo numbers small

## Problem
"My todo ids keep climbing even though I delete most of what I add." Because a deleted todo's id is never given out again, the numbers the reporter types keep getting longer.

## Proposed outcome
"Once a todo is deleted, the next new todo should take its number back, so the numbers I type stay short."

- "Use the smallest number that's free."
- "Nothing else about adding, listing, ticking off or deleting changes."

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- How `add` issues an id (GLOSSARY: Id), and the command-line interface, which is a public contract (`knowledge/architecture/interface.md`).
- Wherever todos are stored (the `TODO_FILE` file).
- Scripts that store an id to act on a todo later (ADR 0001).

## Constraints
- This asks for the opposite of ADR 0001 ("Todo ids are permanent"): "no id is issued twice, even after its todo is deleted". The ADR names "reusing the smallest free id" as an alternative it rejected, because a stale id then acts on the wrong todo without any error. The ADR, and the GLOSSARY entry for Id that cites it, can change only through a new ADR that supersedes it (policy: public contract, rule 2). Proposed for their owners; this intent does not edit them.
- Nothing else about adding, listing, ticking off or deleting changes (the ticket).
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Id, Done. The ticket's "ticking off" is the glossary's "done".

## Out of scope
The ticket asks only that a new todo take the smallest free number. It does not ask for renumbering existing todos, changing the order of the list, or any change to `list`, `done` or `delete` beyond the ids that `add` gives out.

## Open questions
- Do the owners accept giving up ADR 0001's promise, with a new ADR superseding it? The ADR's concern is a stale id, held by a script or typed from memory, acting on a different todo with no error. Is that risk accepted, or should it be reduced in some way the reporter wants?
- If the ADR is superseded, GLOSSARY's Id entry ("never given to another todo", "the third todo ever added keeps its id after the first two are deleted") needs rewording. Who proposes it?
- "Smallest number that's free": does numbering start at 1, and what does the reporter expect when ids stored in an existing `TODO_FILE` are strings, or are not numbers at all? The contract allows an id to be a string or an integer.
- Does the new todo's id print as an integer, as it does now? Is a changed meaning for an id a breaking change to the contract (policy: public contract, rule 1), given that the type and format stay the same?
- Is a done todo's number free once it is deleted, as for any other? Is a done todo that has not been deleted still holding its number?
- Do todos already stored keep their ids unchanged? The ticket reads that way.
- The ticket gave no opening time, so `started` is when this intent was drafted, date only.
