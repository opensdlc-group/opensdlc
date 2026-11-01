---
kind: spec
status: accepted
intent: intent.md@a5f592759ef4
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Spec: Remove todos I no longer need

## Problem Statement
"Some todos stop mattering." A todo can be added, listed and ticked off, but never got rid of, so a todo that no longer matters stays in the list for good (intent: Problem).

## Solution
One new command on the existing command-line interface:

- `./todo delete <id>` removes the todo with that id (GLOSSARY: Id) and prints `{"deleted": <id>}`.

The deleted todo no longer appears in `./todo list`. The other todos keep their ids, titles, done state and order. The deleted id is never given to another todo (ADR 0001). An id that no todo has is refused with a message and nothing is changed.

## User Stories
1. As the reporter, I want to run `./todo delete 2` and see `{"deleted": 2}`, so that I know the todo is gone.
2. As the reporter, I want a deleted todo to disappear from `./todo list`, so that the list shows only what still matters.
3. As the reporter, I want the other todos to keep their order, ids, titles and done state when I delete one, so that nothing else moves.
4. As the reporter, I want to delete a todo that is already done, so that finished todos can be cleaned up too.
5. As the reporter, I want an id that does not exist to be refused with a message and nothing changed, so that a typo is not mistaken for success and does not remove anything.
6. As a script author, I want an unknown id to exit 3 and a malformed or missing id to exit 2, so that I can tell "no such todo" from "bad command".
7. As a script author, I want a repeated `delete` of the same id to be refused as unknown, so that a stale id never silently succeeds or acts on another todo.
8. As a script author, I want a deleted id never to be reissued, including the highest one, so that an id I stored earlier cannot point at a different todo (ADR 0001).
9. As a script author, I want a todo found by its id and never by its place in the list, so that deleting earlier todos does not change which todo an id means.
10. As a script author, I want existing commands (`add`, `list`, `done`) to behave exactly as before, so that nothing I rely on changes.

## Implementation Decisions
Governed by `knowledge/architecture/interface.md`, the public-contract policy and ADR 0001. Terms are the GLOSSARY ones: Todo, Id, Done. The intent's "remove" is the glossary's "deleted". This builds on the accepted specs `2026-10-keep-a-list-of-things-to-do` and `2026-10-tick-todos-off`; their todo shape, store, id-argument and error decisions stand.

**Command.** `delete` takes exactly one argument, the id. `./todo delete <id>` is the whole interface; no option is added.

**Output.** On success `delete` prints exactly one compact single-line JSON object with the single key `deleted`, whose value is the integer id of the removed todo, and exits 0. This is not a todo object and is not meant to be: the contract says a *todo* prints with `id`, `title` and `done`, and the deleted todo no longer exists to print. The contract's rule for every command, exactly one JSON value on stdout, holds. (Answers the intent's first open question: a different shape is intended; adding the command is an addition, not a break.)

**Id in the output.** `<id>` is the todo's stored integer id, which is the same value as the typed digits read as a decimal integer (`delete 03` prints `{"deleted": 3}`). Ids this product issues are integers, so the output is always a JSON number. (Answers the id-type question.)

**Id argument.** Exactly as for `done`: the argument is an id only if it is ASCII digits and nothing else, read as a decimal integer, and a todo is matched on its integer `id`, never on its place in the list. Missing, several, or non-numeric arguments are invalid input.

**Errors.** Same as `done`, and the same exit codes the contract already gives:
- Invalid input exits 2, with a one-line message on stderr, stdout empty and the store untouched: no id, more than one argument, or an argument that is not ASCII digits. `TODO_FILE` unset is also exit 2. The argument is checked before the store is read. The message for a wrong number of arguments names `delete`, not `done`.
- Unknown id exits 3, with a one-line message on stderr that names the id (for example "no todo with id 7"), stdout empty and the store untouched. A well-formed id that is zero, larger than any issued id, or already deleted is simply unknown. When the store file does not exist yet, an unknown id leaves it absent, as for `done`. (Answers the unknown-id question: yes, the contract's exit 3 and one-line stderr message are what is wanted.)
- An unreadable store exits 1 with a one-line message and is not touched.

**Done todos.** A done todo may be deleted like any other. (Answers the done question; the glossary says a done todo stays until it is "cleared or deleted".)

**Order.** `delete` removes exactly one todo and does not move, renumber or rewrite any other todo. The remaining todos stay in the order they were added.

**Ids stay permanent.** The store already keeps the next id to issue (`next_id`) separately from the todos it holds, and `add` takes ids from it. `delete` removes the todo and leaves `next_id` as it was, so deleting the todo with the highest id still leaves that id unused: the next `add` issues the id after it. Nothing is added to the store layout. (Answers the ADR 0001 question: remembered by the counter that already exists, which `delete` must not lower.)

**Store.** The write on a successful delete is the same atomic temp-file-and-rename as for `add` and `done`. Stores written by earlier versions work as they are.

**Contract record.** This change only adds to the public contract: one command and a second output shape for it. Nothing is renamed, removed or reinterpreted, and exit 2 and 3 keep their meaning. So the public-contract policy is satisfied and not cited, and the risk is low. Deleting is destructive for the person's data, but it is the requested behavior and affects only the todo named. Updating `knowledge/architecture/interface.md` to list `delete` and its output shape is for its owner and is proposed here, not done here (headless runs write only in the change folder); this spec, once accepted, is the record meanwhile.

**Modules.** The store module gains the lookup-and-remove step; command dispatch in the entry point gains `delete`; id parsing is shared with `done`, with the "takes exactly one id" message naming the command. Placement is for plan.md.

## Testing Decisions
**Seam: the `todo` command line.** Run `./todo` as a subprocess with `TODO_FILE` pointed at a file in a temporary directory and observe stdout, stderr, exit status and the store file's presence or bytes. This is the existing seam (`tests/test_add_list.py`, `tests/test_done.py`, `tests/test_smoke.py`) and the public contract itself; it is the highest available and the only one needed. No test reaches into modules or writes the store layout. The "id is never reissued" checks are made through `add` and `list`, not by reading `next_id`.

A good test sets up its todos by running `add`, asserts on parsed JSON rather than text spacing, and for every refused command checks stdout empty, a one-line stderr, the right exit status, and the store byte-for-byte as it was (or still absent). Prior art: `tests/test_done.py` (helpers `run_todo`, `assert_refused`, `assert_refused_unchanged`).

## Acceptance Criteria
With `TODO_FILE` set to a path in a temporary directory, and todos "Buy milk" (id 1), "Walk dog" (2), "Call mum" (3) added in that order:
1. `./todo delete 2` prints `{"deleted": 2}` (as parsed JSON: that one key and value), exits 0.
2. After that, `./todo list` has exactly the todos 1 and 3, in that order, with titles and `done` values unchanged.
3. `./todo delete 2` a second time exits 3, a one-line message on stderr, empty stdout, store unchanged.
4. After deleting id 2, `./todo add "Feed cat"` issues id 4, not 2.
5. After deleting id 3 (the highest), `./todo add "Feed cat"` issues id 4, not 3; ids 1 and 2 keep their titles.
6. After deleting every todo, `./todo list` prints `[]` and the next `add` issues id 4.
7. A todo that has been ticked off with `done` can be deleted: `./todo delete 1` after `./todo done 1` prints `{"deleted": 1}`, exits 0, and `list` no longer shows it.
8. Deleting id 1 leaves ids 2 and 3 with their titles; `done 3` still ticks off "Call mum" and `done 1` exits 3.
9. `./todo delete 7` exits 3, a one-line message on stderr, empty stdout, store unchanged.
10. `./todo delete 0` exits 3 in the same way.
11. With no store file yet, `./todo delete 1` exits 3 and the file is still absent.
12. `./todo delete 02` removes id 2, prints `{"deleted": 2}`, exits 0.
13. `./todo delete`, `./todo delete 1 2`, `./todo delete abc`, `./todo delete -1`, `./todo delete 1.0`, `./todo delete ""` and `./todo delete " 1"` each exit 2, a one-line message on stderr, empty stdout, store unchanged.
14. With `TODO_FILE` unset, `./todo delete 1` exits 2 with a message.
15. A store holding invalid JSON makes `delete 1` exit 1 with a message and leaves the file unchanged.
16. `add`, `list`, `done`, an unknown command, and `./todo` with no command behave as in the accepted specs (the existing tests still pass).

## Out of Scope
Deleting several todos at once, clearing done todos, undoing a delete, any change to `add`, `list` or `done`, and locking against two commands running at once. Rewriting `knowledge/architecture/interface.md` and the glossary (owners' files; see Carried-forward Questions).

## Concerns
- **Intent ambiguity: output shape and type of the id, exit status and message for an unknown id, missing/extra/non-numeric id, deleting a done todo, id reuse after deleting the highest id.** **Resolved:** each answered under Implementation Decisions (Output, Id in the output, Id argument, Errors, Done todos, Ids stay permanent).
- **`{"deleted": <id>}` is a second output shape, and the contract only describes a todo's shape** (policy: Public contract): a new command with a new shape adds to the contract and removes or alters nothing. **Resolved:** treated as an addition, not a break (Implementation Decisions: Output, Contract record). The policy is satisfied; its owner is not asked to approve.
- **Ids stay permanent only if `delete` never lowers the stored next-id counter** (policy: Public contract; ADR 0001): a delete that recomputed the counter from the remaining todos would reissue the highest id. **Resolved:** `delete` leaves the counter alone (Implementation Decisions: Ids stay permanent), and acceptance criteria 4 to 6 prove it through `add`.
- **Interface contract document is behind the accepted additions** (policy: Public contract): `interface.md` does not yet list `add`, `list`, `done`, `delete`, integer ids or exit 1. **Carried:** see Carried-forward Questions. Not a break; the accepted specs are the record meanwhile.
- **Refused `delete` on a missing store file does not create it, while the contract says commands create the file when it is missing** (policy: Public contract): the contract also says a refused command changes nothing, and the two cannot both hold. **Resolved:** "change nothing" wins, as already decided for `done` (Implementation Decisions: Errors).

## Carried-forward Questions
- Update `knowledge/architecture/interface.md` to record `add`, `list`, `done`, `delete` and its `{"deleted": <id>}` output, integer ids, the title rules and exit 1 (product-owner, before release).
- Is accepting leading zeros (`delete 02` is id 2) wanted? It follows the `done` decision, which carried the same question; accepting is built, and a stricter rule would be a later, contract-visible tightening (product-owner, before plan).
- The glossary says a done todo stays "until it is cleared or deleted", but no "clear" command exists; no action needed for this ticket (product-owner, before release, if a future ticket adds one).
