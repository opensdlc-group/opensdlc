---
kind: spec
status: accepted
intent: intent.md@17a5224801be
context: knowledge/architecture/interface.md@32d3432d8351, knowledge/policies/public-contract.md@3febb2f29207, docs/adr/0001-todo-ids-are-permanent.md@245359031b11
risk: low
---
# Spec: Tick todos off

## Problem Statement
"When I finish something I want to mark it done by its id, and still see it in the list, shown as done." Today a todo can be added and listed, but there is no way to say it is finished (intent: Problem).

## Solution
One new command on the existing command-line interface:

- `./todo done <id>` marks the todo with that id done and prints it as one JSON object, with `done` set to `true`.

A done todo stays in `./todo list`, in the same place, shown with `done: true`. Marking a todo that is already done changes nothing and prints it the same way. An id that no todo has is refused with a message and nothing is changed.

## User Stories
1. As the reporter, I want to run `./todo done 2` and get that todo back with `done` true, so that I know it is ticked off.
2. As the reporter, I want a done todo to stay in `./todo list` and show as done, so that I can still see what I have finished.
3. As the reporter, I want the other todos to keep their order, ids, titles and done state when I tick one off, so that nothing else moves.
4. As the reporter, I want ticking off a todo that is already done to change nothing, so that a repeated command is harmless.
5. As a script author, I want `done` on an already-done todo to print the same shape and exit 0 as the first time, so that a retry needs no special case.
6. As the reporter, I want an id that does not exist to be refused with a message, so that a typo is not mistaken for success, and I want nothing changed when that happens.
7. As a script author, I want an unknown id to exit 3 and a malformed or missing id to exit 2, so that I can tell "no such todo" from "bad command".
8. As a script author, I want a todo found by its id and never by its place in the list, so that an id stored earlier still acts on the same todo (ADR 0001).
9. As a script author, I want `done` to print the todo in the same shape as one item of `list`, so that one parser handles both.
10. As a script author, I want existing commands (`add`, `list`) to behave exactly as before, so that nothing I rely on changes.

## Implementation Decisions
Governed by `knowledge/architecture/interface.md`, the public-contract policy and ADR 0001. Terms are the GLOSSARY ones: Todo, Id, Done. This builds on the accepted spec `2026-10-keep-a-list-of-things-to-do`; its todo shape, store and error decisions stand.

**Command.** `done` takes exactly one argument, the id. `./todo done <id>` is the whole interface; no option is added.

**Output.** On success `done` prints the todo after marking, as one compact single-line JSON object with exactly `id`, `title` and `done` (`done` is `true`), and exits 0. Same shape as `add` and one item of `list`. No field is added, no existing field changes type or meaning.

**Already done.** A todo that is already done is not changed. `done` prints it exactly as it prints after a first tick (same object, `done` true) and exits 0. The store content is left as it was. (Answers the intent's first open question.)

**Id argument.** The argument is an id only if it is made of ASCII digits and nothing else (`3`, `03`; not `-1`, `+3`, `3.0`, ` 3`, `abc`, an empty string). It is read as a decimal integer, so `03` means id 3. A todo is matched on its integer `id`, whatever the text typed, never on its place in the list. Ids issued by this product are integers (previous spec), so matching on the integer is complete. If a store ever held a string id, `done` does not match it; that cannot arise from this product's own commands. (Answers the intent's id-type question.)

**Errors.**
- Invalid input exits 2, with a one-line message on stderr, stdout empty and the store untouched: no id, more than one argument, or an argument that is not ASCII digits. `TODO_FILE` unset is also exit 2, as for the other commands. The argument is checked before the store is read, as `add` checks its title.
- Unknown id exits 3, with a one-line message on stderr that names the id (for example "no todo with id 7"), stdout empty and the store untouched. This is the contract's existing unknown-id status; it is first used here. A well-formed id that is zero or larger than any issued id is simply unknown. When the store file does not exist yet, an unknown id leaves it absent: "change nothing" wins over "create it when missing" for a refused command.
- An unreadable store exits 1 with a one-line message, as for the other commands, and is not touched.

**Order and list.** `done` only sets `done` on one todo. It does not move, renumber, remove or rewrite any other todo, the order added, or the next-id counter. `list` needs no change: it already prints every todo, done or not, and shows `done` as stored. (Answers the intent's order question: order is unchanged, and "shown as done" is `done: true`.)

**Store.** Only the matching todo's `done` changes. The write on a successful first tick is the same atomic temp-file-and-rename as for `add`. Nothing in the layout changes, so stores written by earlier versions work as they are.

**Contract record.** This change only adds to the public contract: one command and its use of exit 3. Nothing is renamed, removed or reinterpreted, and the `done` field already existed and now becomes `true`, which is what the field means. So the public-contract policy is satisfied and not cited. Adding a command is not a breaking change (answers the intent's last open question). Updating `knowledge/architecture/interface.md` to list `done` is for its owner and is proposed here, not done here (headless runs write only in the change folder); this spec, once accepted, is the record meanwhile.

**Modules.** The store module gains the lookup-and-mark step; command dispatch in the entry point gains `done`. Id parsing may sit with the dispatch or in its own small module. Placement is for plan.md.

## Testing Decisions
**Seam: the `todo` command line.** Run `./todo` as a subprocess with `TODO_FILE` pointed at a file in a temporary directory and observe stdout, stderr, exit status and the store file's presence or bytes. This is the existing seam (`tests/test_add_list.py`, `tests/test_smoke.py`) and the public contract itself; it is the highest available and the only one needed. No test reaches into modules or writes the store layout.

A good test sets up its todos by running `add`, asserts on parsed JSON rather than text spacing, and for every refused command checks stdout empty, a one-line stderr, the right exit status, and the store byte-for-byte as it was (or still absent). Prior art: `tests/test_add_list.py` (helpers `run_todo`, `assert_refused_unchanged`).

## Acceptance Criteria
With `TODO_FILE` set to a path in a temporary directory, and todos "Buy milk" (id 1), "Walk dog" (2), "Call mum" (3) added in that order:
1. `./todo done 2` prints `{"id": 2, "title": "Walk dog", "done": true}` (as parsed JSON: those three keys, those values), exits 0.
2. After that, `./todo list` still has all three todos in the order 1, 2, 3, with only id 2 done and the others `done: false`, titles and ids unchanged.
3. `./todo done 2` a second time prints the same object as the first time, exits 0, and the store file is byte-for-byte the same as before the second call.
4. The output of `done` equals the matching item in `list` afterwards.
5. `./todo done 7` exits 3, a one-line message on stderr, empty stdout, store unchanged.
6. `./todo done 0` exits 3 in the same way.
7. With no store file yet, `./todo done 1` exits 3 and the file is still absent.
8. `./todo done 02` marks id 2 done, exits 0.
9. `./todo done`, `./todo done 1 2`, `./todo done abc`, `./todo done -1`, `./todo done 1.0`, `./todo done ""` and `./todo done " 1"` each exit 2, a one-line message on stderr, empty stdout, store unchanged.
10. With `TODO_FILE` unset, `./todo done 1` exits 2 with a message.
11. A store holding invalid JSON makes `done 1` exit 1 with a message and leaves the file unchanged.
12. After ticking id 2 off, `./todo add "Feed cat"` issues id 4 (the counter is untouched), and ids 1 to 3 keep their titles.
13. `add`, `list`, an unknown command, and `./todo` with no command behave as in the accepted add/list spec (the existing tests still pass).

## Out of Scope
Un-marking a done todo, deleting, clearing, hiding done todos from `list`, filtering `list`, marking several ids at once, locking against two commands running at once (the intent's Out of scope, and previously out of scope). Rewriting `knowledge/architecture/interface.md` and the glossary (owners' files; see Carried-forward Questions).

## Concerns
- **Intent ambiguity: output for an already-done todo, unknown-id message and status, missing, extra or non-numeric id, id type, order after ticking, how "shown as done" is expressed, contract impact.** **Resolved:** each answered under Implementation Decisions (Already done, Errors, Id argument, Order and list, Output, Contract record). The unknown-id status is the contract's existing exit 3.
- **Refused `done` on a missing store file does not create it, while the contract says commands create the file when it is missing** (policy: Public contract): the contract also says a refused command changes nothing, and the two cannot both hold. **Resolved:** "change nothing" wins (Implementation Decisions: Errors). No effect on any existing behavior, since `add` and `list` still create the file.
- **Interface contract document is behind the accepted additions** (policy: Public contract): `interface.md` does not yet list `add`, `list`, `done`, the title rules, integer ids or exit 1. **Carried:** see Carried-forward Questions. Not a break; the accepted specs are the record meanwhile.
- **Ids are matched as integers only**, so a string id in a hand-edited store would never be found. **Resolved:** this product only issues integer ids (Implementation Decisions: Id argument), so nothing it writes can hit this.

## Carried-forward Questions
- Update `knowledge/architecture/interface.md` to record `add`, `list`, `done`, integer ids, the title rules and exit 1 (product-owner, before release).
- Is accepting leading zeros (`done 02` is id 2) wanted, or should the argument be refused unless it is the canonical digits? The spec holds either way for this ticket; accepting is built, and a stricter rule would be a later, contract-visible tightening (product-owner, before plan).
