---
kind: spec
status: draft
intent: intent.md@97685d54f254
context: knowledge/architecture/interface.md@0afec65d1a8a, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Spec: Clear out finished todos

## Problem Statement
"The list fills up with done todos." A done todo (GLOSSARY: Done) stays in the list until someone deletes it, so the reporter has to deal with finished todos one at a time (intent: Problem).

## Solution
One new command on the existing command-line interface:

- `./todo clear` removes every done todo in one step and prints `{"removed": <count>}`, where `<count>` is how many went.

Todos that are not done stay, with their ids, titles and order unchanged. If nothing is done, nothing is removed and the output is `{"removed": 0}`. Ids of the todos that went are never given to another todo (ADR 0001).

## User Stories
1. As the reporter, I want to run `./todo clear` and have every done todo removed, so that finished todos stop filling the list.
2. As the reporter, I want to be told how many todos went, as in `{"removed": 2}`, so that I can see the command did what I expected.
3. As the reporter, I want todos that are not done to stay with the same ids, titles and order, so that nothing I still need moves.
4. As the reporter, I want `./todo clear` with no done todos to remove nothing and say `{"removed": 0}`, so that I am told none went and it is safe to run at any time.
5. As the reporter, I want `./todo clear` on an empty list to succeed in the same way, so that I do not have to check the list first.
6. As the reporter, I want a second `./todo clear` straight after the first to report `{"removed": 0}`, so that repeating it is harmless.
7. As a script author, I want the count to be a JSON integer under the single key `removed`, so that I can read it without parsing text.
8. As a script author, I want a cleared todo's id never to be reissued, including when the todo with the highest id was cleared, so that an id I stored earlier cannot point at a different todo (ADR 0001).
9. As a script author, I want `clear` to refuse any argument with exit 2 and change nothing, so that a mistyped command such as `clear 3` (meant as `delete 3`) is never mistaken for success or acted on in part.
10. As a script author, I want the other commands (`add`, `list`, `done`, `delete`) to behave exactly as before, so that nothing I rely on changes.

## Implementation Decisions
Governed by `knowledge/architecture/interface.md`, the public contract policy and ADR 0001, all of which this spec follows. Terms are the GLOSSARY ones: Todo, Done, Id. The intent's "remove" is the glossary's "deleted" for a single todo; the glossary already names this action "cleared", and the command is named `clear` accordingly. This builds on the accepted specs `2026-10-keep-a-list-of-things-to-do`, `2026-10-tick-todos-off` and `2026-10-remove-todos-i-no-longer-need`; their todo shape, store, error and exit-code decisions stand.

**Command.** `clear` takes no arguments. `./todo clear` is the whole interface; no option is added.

**What is cleared.** A todo is removed exactly when its `done` value is the JSON `true` (the value `done` writes). Any other value, including a missing or malformed `done`, means the todo is not done and it stays. No todo is touched except by removal.

**Output.** On success `clear` prints exactly one compact single-line JSON object with the single key `removed`, whose value is the integer number of todos removed, and exits 0. It is `{"removed": 0}` when nothing was done. This is not a todo object and is not meant to be: the contract says a *todo* prints with `id`, `title` and `done`, and the removed todos no longer exist to print. The contract's rule for every command, exactly one JSON value on stdout, holds. (Answers the intent's first and second open questions: a different shape is intended, `<count>` is a JSON integer, and the zero case is `{"removed": 0}`.)

**Contract record.** Adding a command, with a second output shape for it, only adds to the public contract: nothing is renamed, removed or reinterpreted, the shapes of existing commands do not change, and exit codes 2 and 3 keep their meaning. It is therefore not a break, the public contract policy is followed rather than strained, and the risk is low. Clearing is destructive for the data it names and has no undo, but it is the requested behavior, it touches only done todos, and a todo can only be done by someone's own `done`. Updating `knowledge/architecture/interface.md` to list `clear` and its output shape is for its owner and is proposed here, not done here (headless runs write only in the change folder); this spec, once accepted, is the record meanwhile. (Answers the first open question's contract part.)

**Arguments.** Any argument is invalid input: exit 2, a one-line message on stderr that names `clear`, stdout empty, the store untouched. The arguments are checked before `TODO_FILE` or the store is read. `TODO_FILE` unset is also exit 2, as for every command. (Answers the arguments question.)

**Order and ids.** The remaining todos keep their relative order, their ids and every field, and none is renumbered or rewritten. Ids stay permanent by the means that already exist: the store keeps the next id to issue (`next_id`) separately from the todos it holds, and `clear` leaves it as it was. So clearing the todo with the highest id still leaves that id unused: the next `add` issues the id after it. Nothing is added to the store layout, and stores written by earlier versions work as they are. (Answers the ADR 0001 question: remembered by the counter that already exists, which `clear` must not lower.)

**Nothing to clear.** On an empty list, or one with no done todos, `clear` exits 0 and prints `{"removed": 0}`. The todos and `next_id` in the store are exactly as before. As with `list`, a successful command on a missing store file creates it, holding an empty list and `next_id` 1, as the contract's rule that commands create a missing file says. (Answers the empty-list question. Whether the file's bytes are rewritten is left to the plan; only its parsed contents are specified.)

**Errors.** An unreadable store exits 1 with a one-line message and is not touched, as for the other commands. `clear` has no id, so exit 3 does not arise.

**Store.** When any todo is removed, the write is the same atomic temp-file-and-rename as for the other commands, so a failed write leaves the earlier file in place and never half of a clear: all done todos go or none do.

**Modules.** The store module gains the remove-all-done step, which returns the count; command dispatch in the entry point gains `clear` with its no-argument check. Placement is for plan.md.

## Testing Decisions
**Seam: the `todo` command line.** Run `./todo` as a subprocess with `TODO_FILE` pointed at a file in a temporary directory and observe stdout, stderr, exit status and the store file's presence or contents. This is the existing seam (`tests/test_add_list.py`, `tests/test_done.py`, `tests/test_delete.py`, `tests/test_smoke.py`) and is the public contract itself; it is the highest available and the only one needed. No test reaches into modules or writes the store layout. The "id is never reissued" checks are made through `add` and `list`, not by reading `next_id`.

A good test sets up its todos by running `add` and `done`, asserts on parsed JSON rather than text spacing, and for every refused command checks stdout empty, a one-line stderr, the right exit status, and the store byte-for-byte as it was (or still absent). Prior art: `tests/test_delete.py` and `tests/test_done.py` (helpers `run_todo`, `assert_refused`, `assert_refused_unchanged`).

## Acceptance Criteria
With `TODO_FILE` set to a path in a temporary directory, and todos "Buy milk" (id 1), "Walk dog" (2), "Call mum" (3), "Feed cat" (4) added in that order, then `done 1` and `done 3`:
1. `./todo clear` prints `{"removed": 2}` (as parsed JSON: that one key, an integer value), exits 0, with empty stderr.
2. After that, `./todo list` has exactly the todos 2 and 4, in that order, with titles and `done` values (both false) unchanged.
3. A second `./todo clear` prints `{"removed": 0}`, exits 0, and `list` is unchanged.
4. After the first clear, `./todo add "Water plants"` issues id 5, not 1 or 3.
5. With todos 1 to 3 added and only `done 3` run, `clear` removes id 3 (the highest) and prints `{"removed": 1}`; the next `add` issues id 4, not 3, and ids 1 and 2 keep their titles.
6. With every todo done, `clear` prints `{"removed": <that number>}`, `list` prints `[]`, and the next `add` issues the id after the highest ever issued.
7. With todos added and none done, `clear` prints `{"removed": 0}`, exits 0, and `list` shows every todo unchanged and in order.
8. With an empty list (after `add` and `delete` of the only todo, or a store that has never held a todo), `clear` prints `{"removed": 0}` and exits 0. With no store file yet, it exits 0 and afterwards `list` prints `[]`.
9. The remaining todos keep their ids after a clear: after clearing 1 and 3 above, `done 2` and `done 4` still tick off "Walk dog" and "Feed cat", and `done 1` exits 3.
10. A todo that was ticked off and then cleared cannot be deleted or ticked off again: `delete 1` and `done 1` exit 3.
11. `./todo clear 1`, `./todo clear all` and `./todo clear ""` each exit 2, a one-line message on stderr, empty stdout, store byte-for-byte unchanged (done todos still listed).
12. With `TODO_FILE` unset, `./todo clear` exits 2 with a message.
13. A store holding invalid JSON makes `clear` exit 1 with a message and leaves the file unchanged.
14. `add`, `list`, `done`, `delete`, an unknown command, and `./todo` with no command behave as in the accepted specs (the existing tests still pass).

## Out of Scope
Removing one todo by its id (that is `delete`), removing todos that are not done, a way to preview or confirm a clear, undoing a clear, clearing only some done todos, any change to `add`, `list`, `done` or `delete`, and locking against two commands running at once. Rewriting `knowledge/architecture/interface.md` (its owner's file; see Carried-forward Questions).

## Concerns
- **Intent ambiguity: output shape, count type, zero case, arguments, empty list, how the highest id stays unused.** **Resolved:** each answered under Implementation Decisions (Output, Arguments, Nothing to clear, Order and ids).
- **Is adding a command a breaking change to the contract?** **Resolved:** no; it adds and removes or alters nothing (Implementation Decisions: Contract record), so risk stays low and no policy owner is asked to approve.
- **The intent's ticket says "remove" where the glossary says "deleted" for one todo and "cleared" for this action.** **Resolved:** the command and this spec use "clear"/"cleared" for removing all done todos, and "delete" for one (Implementation Decisions, intro). No glossary change is needed.
- **Interface contract document is behind the accepted additions** (`interface.md` does not yet list `add`, `list`, `done`, `delete`, integer ids or exit 1, and would also lack `clear`). **Carried:** see Carried-forward Questions. Not a break; the accepted specs are the record meanwhile.
- **A successful `clear` on a missing store file creates it, while the refused commands do not.** **Resolved:** a successful command follows the contract's "create it when it is missing", as `list` does; a refused one changes nothing (Implementation Decisions: Nothing to clear, Errors).
- **`clear` is destructive and has no undo or confirmation, and the intent asks for neither.** **Resolved:** built as asked; the intent's own Out of scope excludes undo (Implementation Decisions: Contract record).

## Carried-forward Questions
- Update `knowledge/architecture/interface.md` to record `add`, `list`, `done`, `delete`, `clear` and its `{"removed": <count>}` output, integer ids, the title rules and exit 1 (product-owner, before release).
- Is exit 2 for any argument to `clear` the wanted rule, or should a future `clear` option be reserved for something else, such as clearing by other criteria? Refusing is built; adding an option later is an addition to the contract (product-owner, before release).
