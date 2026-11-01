---
kind: intent
status: accepted
author: ticket reporter (ticket #1)
source: ticket
ref: #1
started: 2026-10-29T04:14:20Z
tags: interface, todo, ids
---
# Intent: Keep a list of things to do

## Problem
"I keep forgetting small jobs." Today there is no way to write a todo down and see everything written down so far.

## Proposed outcome
"I want to write a todo down in one step and see everything I have written down, in the order I added it."

- A todo has a title. Spaces at either end don't count. A title can't be empty or longer than 200 characters; the reporter wants to be told when it is, and nothing saved.
- Every todo gets an id the reporter can use to refer to it later. Ids never change and are never reused, even after a todo is gone.
- A new todo is not done.
- `./todo add <title>` prints the new todo.
- `./todo list` prints a JSON array of every todo.

## Affected users and systems
- The reporter, and anyone else who runs `./todo` from the command line.
- The command-line interface, which is a public contract (`knowledge/architecture/interface.md`).
- Wherever todos are stored (the `TODO_FILE` file named in AGENTS.md).

## Constraints
- Ids are permanent: they never change and are never given to another todo (ADR 0001).
- A rejected title saves nothing.
- Python 3.12 standard library only (AGENTS.md).
- Terms follow GLOSSARY.md: Todo, Title, Id, Done.

## Out of scope
The ticket asks only for adding and listing. It does not ask for ticking a todo off, deleting, or clearing, though it mentions ids surviving deletion and a todo being "not done".

## Open questions
- What fields does a todo have in the JSON (`id`, `title`, done flag), and what are they called?
- What does `add` print: the todo as JSON, or text? Same shape as an item in `list`?
- What is the id: a number counting up, or something else? Where does the first one start?
- Is the 200-character limit counted before or after dropping the spaces at either end?
- What does the reporter see when a title is empty or too long: the message, and the exit status?
- What does `list` print when there are no todos yet (`[]`)?
- Can the title be given as several words without quotes (`./todo add buy milk`)?
- What about spaces or line breaks inside a title, and a title that is only spaces (treated as empty)?
- "In the order I added it": is that the same as id order? Is it guaranteed?
- Ids are never reused "even after a todo is gone", but the ticket has no way to remove one. Should the rule be kept and tested now, and how does it survive an empty or lost store?
- Does `list` show done todos too? The ticket says "every todo".
- Is the existing interface contract in `knowledge/architecture/interface.md` to be extended, and does this count as a breaking change to it?
