---
kind: decision
status: accepted
date: 2026-10-01
always: true
---
# 0001. Todo ids are permanent

## Context
People type ids they read off the list, and scripts store ids to act on a todo later. If an id could change or come back, a stored id could quietly point at a different todo.

## Decision
A todo's id never changes, and no id is issued twice, even after its todo is deleted or cleared.

## Alternatives
- Reusing the smallest free id keeps numbers short, but a stale id then acts on the wrong todo without any error.
- Renumbering after every delete has the same problem for every todo after the one deleted.

## Consequences
Ids only grow, so they get longer in a list that has seen many todos. Anything that hands out ids, now or later, has to keep this promise.
