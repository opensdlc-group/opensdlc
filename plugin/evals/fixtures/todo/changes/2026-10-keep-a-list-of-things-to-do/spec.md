---
kind: spec
status: accepted
intent: intent.md@e24c023b310d
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: standard
---
# Spec: Keep a list of things to do

## Problem Statement
"I keep forgetting small jobs." Today `./todo` cannot write a todo down or show what has been written down (intent: Problem). The reporter wants to add a todo in one step and see every todo, in the order added.

## Solution
Two commands on the existing command-line interface:

- `./todo add <title>` saves a new todo and prints it as one JSON object.
- `./todo list` prints a JSON array of every todo, oldest first.

A todo has an `id`, a `title` and `done`. A new todo is not done. A title that is empty or too long is refused with a message and nothing is saved. Ids are issued once and never come back (ADR 0001).

## User Stories
1. As the reporter, I want to run `./todo add Buy milk` and get the saved todo back, so that I know it was written down and what its id is.
2. As the reporter, I want `./todo list` to show every todo in the order I added it, so that I can see what I have still to do.
3. As the reporter, I want spaces at either end of a title dropped, so that stray spaces don't matter.
4. As the reporter, I want to be told when a title is empty or longer than 200 characters, so that I can fix it, and I want nothing saved when that happens.
5. As the reporter, I want every todo to get an id that never changes, so that I can refer to it later.
6. As a script author, I want ids that are never given to another todo, even after a todo is gone, so that a stored id can never point at the wrong todo.
7. As the reporter, I want a new todo to be not done, so that it shows as still to do.
8. As a script author, I want `list` on a fresh install to print `[]`, so that I can parse the output without special cases.
9. As a script author, I want the exit status to tell success (0) from invalid input (2), so that I can react to a refused title.
10. As a script author, I want `add` to print the todo in the same shape as one item of `list`, so that one parser handles both.

## Implementation Decisions
Governed by `knowledge/architecture/interface.md`, the public-contract policy and ADR 0001. Terms are the GLOSSARY ones: Todo, Title, Id, Done.

**Todo shape.** A todo is a JSON object with exactly `id`, `title` and `done`. `id` is an integer, `title` a string, `done` a boolean (`false` for a new todo). The interface contract already allows these three fields; no field is added.

**Output.** `add` prints the new todo as one JSON object on stdout. `list` prints one JSON array of todo objects on stdout. Both print compact single-line JSON and exit 0. Same object shape in both (story 10).

**Ids.** Integers, counting up from 1. The store keeps a separate counter of the next id to issue, so the id comes from the counter and never from the todos currently in the list. This keeps ADR 0001's promise once deleting and clearing exist: removing the newest todo must not let its id be issued again. The counter is advanced and saved together with the new todo in one write.

**Store.** The file named by `TODO_FILE` holds one JSON object with the next id and the list of todos in the order added. This layout is internal; the contract promises only that the file is JSON, is created when missing, and is read and written by every command. Later tickets (done, delete, clear) must keep the counter. A missing file is treated as an empty store, and is created by `add`. `list` also creates it, as the contract says every command writes it back. The write goes to a temporary file in the same directory and is renamed over the store, so a failed write cannot leave half a file. If `TODO_FILE` is not set, the command is invalid input: exit 2 with a message.

**Order.** The list is kept in the order added, which is also ascending id order. `list` prints it as stored; ids only grow, so both orderings agree and are guaranteed.

**Title rules.**
- Title = the argument(s) with whitespace at either end dropped. Everything inside is kept as given (inner spaces and line breaks are not changed).
- Several arguments are joined with one space, so `./todo add buy milk` saves "buy milk". Unquoted words reach the program separately and their original spacing is already lost.
- Length is counted in characters (Unicode code points) after dropping the ends. 200 characters is accepted, 201 is refused.
- Empty after dropping the ends (including no argument, or only spaces) is refused.

**Errors.** Invalid input (empty title, title over 200 characters, no command beyond what exists today, an unknown command, extra arguments to `list`, `TODO_FILE` unset) exits 2 with a one-line message on stderr, stdout empty, and the store not touched. The messages say which rule failed, e.g. "title is empty" and "title is longer than 200 characters". The no-command usage message and exit 2 stay as they are. No command in this change takes an id, so exit 3 is unused here.

**Unreadable store.** If the store exists but is not valid JSON of the expected shape, the command exits 1 with a one-line message on stderr and changes nothing. The contract defines no status for this case; 1 is added and does not alter 0, 2 or 3.

**Contract record.** This change only adds to the public contract: two commands, the title rules, integer ids from 1, and exit 1 for an unreadable store. Nothing is renamed, removed or reinterpreted, so the public-contract policy is satisfied and not cited as a concern. The intent's question whether this counts as breaking is answered: it does not. Updating `knowledge/architecture/interface.md` to list the new commands and rules is for its owner (product-owner) and is proposed here, not done here; this spec, once accepted, is the record of the additions in the meantime.

**Modules.** One module for the store (read, write, issue ids), one for the title rules, and the command dispatch in the existing entry point. Placement is for plan.md.

## Testing Decisions
**Seam: the `todo` command line.** Run `./todo` as a subprocess with `TODO_FILE` pointed at a file in a temporary directory, and observe stdout, stderr, exit status and the store file's presence or contents. This is the existing seam (the smoke test uses it) and the public contract itself, so it is the highest available and the only one needed. Title rules, id issuing and ordering are all observable through it; no test reaches into modules.

A good test here sets up a store by running commands, not by writing internal layout, asserts on parsed JSON rather than text spacing, and checks that a refused command left the store byte-for-byte as it was. Prior art: `tests/test_smoke.py` (subprocess, `unittest`).

The never-reused promise cannot be driven through the commands until a removal command exists. Until then one test seeds a store whose counter is ahead of its highest id (as it would be after a delete) and checks that `add` issues the counter's id, not highest + 1. That test writes the store layout directly, so it is a deliberate exception to the rule above; it is replaced by an end-to-end add, delete, add test when the delete ticket lands.

## Acceptance Criteria
With `TODO_FILE` set to a path that does not exist yet:
1. `./todo list` prints `[]`, exits 0.
2. `./todo add "Buy milk"` prints `{"id": 1, "title": "Buy milk", "done": false}` (as parsed JSON: those three keys, those values), exits 0.
3. After a second `./todo add "Walk dog"` (id 2), `./todo list` prints an array of both, Buy milk first.
4. `./todo add "  Buy milk "` saves and prints title "Buy milk".
5. `./todo add buy milk` saves title "buy milk".
6. A title of exactly 200 characters is saved; one of 201 exits 2 with a message on stderr, empty stdout, and the store unchanged (or still absent).
7. 200 characters plus spaces at both ends is saved (limit counts after dropping the ends).
8. `./todo add ""`, `./todo add "   "` and `./todo add` exit 2 with a message, empty stdout, store unchanged.
9. Ids of successive adds are 1, 2, 3 and the id of an existing todo is the same in every later `list`.
10. Given a store whose next-id counter is 5 and whose highest id is 2, `add` issues id 5, then 6.
11. `add` output equals the matching item in `list`.
12. A store holding invalid JSON makes `add` and `list` exit 1 with a message and leave the file unchanged.
13. `./todo frobnicate` and `./todo list extra` exit 2 with a message and empty stdout.
14. `./todo` with no command still prints a usage message and exits 2.
15. With `TODO_FILE` unset, `add` and `list` exit 2 with a message.

## Out of Scope
Ticking a todo off, deleting, clearing (the intent's Out of scope). Any command that takes an id, hence exit 3. Filtering `list`. Locking against two commands running at once. Editing a title. Rewriting `knowledge/architecture/interface.md` and the glossary (owners' files; see Concerns).

## Concerns
- **Never-reused ids cannot be fully proven now** (policy: Public contract, rule 2, ADR 0001): there is no delete, so the promise is only exercised through a seeded counter. **Resolved:** ids come from a stored counter, not from the list (Implementation Decisions: Ids), tested as in Testing Decisions.
- **A lost or deleted store file restarts ids at 1** (policy: Public contract, rule 2, ADR 0001): a missing `TODO_FILE` is treated as empty, so a script's stored ids could point at new todos if the file is deleted. The program cannot know what ids were issued before. **Carried:** see Carried-forward Questions.
- **Interface contract document is behind the accepted additions** (policy: Public contract): `interface.md` does not yet list `add`, `list`, the title rules, integer ids or exit 1. **Carried:** see Carried-forward Questions. Not a break; the spec is the record meanwhile.
- **Intent ambiguity: fields, output form, id form, start value, length counting, error text and status, empty list, multi-word title, inner whitespace, ordering, done todos in list, contract impact.** **Resolved:** each answered under Implementation Decisions (Todo shape, Output, Ids, Title rules, Errors, Order, Contract record). `list` shows every todo, done or not, as the ticket says "every todo".
- **Exit 1 for an unreadable store is a new status the contract does not name** (policy: Public contract): an addition, not a change to 0, 2 or 3. **Resolved:** see Implementation Decisions: Unreadable store.
- **Whitespace dropped is any whitespace, not only the space character**, as the glossary says "spaces" and the ticket "spaces". **Resolved:** whitespace of all kinds is dropped at the ends (Title rules); a title of only line breaks is therefore empty.

## Carried-forward Questions
- Should a missing `TODO_FILE` on `list` or `add` be treated as a fresh store, or refused once a store has existed, to protect ids from a deleted file? The spec holds either way for this ticket; treating it as fresh is built. (product-owner and @todo/platform, before release.)
- Update `knowledge/architecture/interface.md` and, if wanted, the Todo/Id entries in `GLOSSARY.md` to record the commands, title rules and integer ids. (product-owner, before release.)
- Should titles with inner line breaks or control characters be refused rather than kept? Kept here, since the ticket forbids only empty and over-long. (product-owner, before build; a change would be an additive tightening of the title rules.)
