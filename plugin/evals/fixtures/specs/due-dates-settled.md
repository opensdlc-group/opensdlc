---
kind: spec
status: draft
intent: intent.md@<pin>
context: <pinned by `opensdlc pin`>
risk: high
---
# Spec: Due dates

## Problem Statement
Some todos have a deadline, and the list should put them first (intent, ticket #4). Today a todo has only an id, a title and whether it is done (GLOSSARY: Todo), so a deadline cannot be recorded and the list cannot show which todos are urgent.

## Solution
`./todo add` takes an optional `--due YYYY-MM-DD`. Every todo then prints with a `due` field: the date, or `null` when it has none. `./todo list` shows todos that have a due date first, earliest first, then the todos without one; todos that tie keep the order they were added in. Marking a todo done keeps its due date. A due date that is not a real calendar date written exactly as YYYY-MM-DD is invalid input: exit 2, one line on stderr, nothing saved.

## User Stories
1. As a person adding a todo, I want to give it a due date with `--due YYYY-MM-DD`, so that its deadline is recorded.
2. As a person adding a todo, I want a date that does not exist (`2026-02-30`) or is not a date (`tomorrow`) refused with an error, so that nothing wrong is saved.
3. As a person adding a todo without `--due`, I want it to work as it does today, so that existing habits and scripts keep working.
4. As a person reading any todo, I want to see its due date or that it has none, so that I know what is urgent.
5. As a person reading the list, I want dated todos first, earliest first, so that the most urgent are at the top.
6. As a person reading the list, I want undated todos after the dated ones, in the order I added them, so that nothing is lost or shuffled.
7. As a person with two todos due the same day, I want them to stay in the order I added them, so that the list is predictable.
8. As a person ticking off a todo, I want it to keep its due date, so that I can still see when it was due.
9. As a script author, I want `due` present on every todo that `add`, `list` and `done` print, always a string or `null`, so that I can parse it without special cases.
10. As a person with a file saved before this change, I want my old todos to still work and to print `"due": null`, so that I lose nothing by upgrading.
11. As a person with todos that have ids, I want ordering the list never to change an id, so that the ids I stored still point at the same todos (ADR 0001).

## Implementation Decisions
- **Due date** is a new term for the glossary: a calendar date by which a todo is meant to be done, written YYYY-MM-DD, with no time of day. The Todo entry would grow to "a title, an id, whether it is done and, optionally, a due date". Proposed for the glossary owners; this spec does not edit it.
- **Format.** Valid means exactly four ASCII digits, a hyphen, two ASCII digits, a hyphen, two ASCII digits, and a real date in the proleptic Gregorian calendar (year 0001 to 9999). Nothing is trimmed or normalised: `2026-2-3`, `20260203`, ` 2026-02-03`, a date with a time, and non-ASCII digits are all invalid. Python's lenient ISO parser is not the definition of valid.
- **Past dates are accepted.** The ticket rejects only dates that do not exist, and "overdue" handling is out of scope.
- **Command line.** `add` accepts `--due` as a separate argument followed by exactly one value, anywhere among the words of the title (before or after). The remaining words form the title as today. `--due` with no value, an empty value, or `--due` given more than once is invalid input (exit 2). The value is validated as a date, so `--due --due` and `--due Buy` fail on the date. The `--due=DATE` spelling is not an option: it stays part of the title, as it does today. Validation happens before anything is read from or written to the file, so an invalid date leaves no file behind and an existing file untouched.
- **Stored shape.** A new todo is saved with a `due` field holding the date string, or `null`. Todos already in a file have no `due` and are not rewritten by this change.
- **Printed shape.** Every todo printed by `add`, `list` and `done` has `id`, `title`, `done` and `due`. A todo whose stored `due` is missing, or is anything other than a valid date string, prints `"due": null` and counts as having no due date. This is applied to what is printed, never to what is stored, so `done` on an already done legacy todo still changes nothing in the file. `delete` prints `{"deleted": <id>}` as before.
- **List order.** `list` prints a sorted copy; the stored order is never changed. Dated todos come first by due date ascending, then undated todos. Ties, and all undated todos, keep their position in the file, which is the order they were added in (todos are only ever appended and ids only grow, ADR 0001), so the order never compares ids and works whether an id is a string or an integer. The rule applies to done and open todos alike: a done todo with an early due date sorts ahead of open ones. A list with no dated todo is in the order it is today.
- **Ids** are untouched: `next_id`, the id of every todo and the rules for issuing them do not change.
- **Done** sets `done` and nothing else, so the due date is kept.
- **Errors** follow the interface: invalid input exits 2, a one-line message on stderr, nothing saved. The message names the offending value.
- **Interface document.** `knowledge/architecture/interface.md` should list `due` among the fields of a printed todo, describe `add`'s `--due` option, and state the list order. Proposed for its owner (product-owner); this spec does not edit it.

## Testing Decisions
- **One seam: the command line.** Every test runs `./todo` as a subprocess with `TODO_FILE` pointing into a temporary directory and checks the exit status, stdout, stderr and the file. Everything this change does is observable there, and it is the public contract. No test reaches into a module.
- A good test here adds todos through `./todo add`, reads them back through `./todo list` and `./todo done`, and compares parsed JSON. Files written by hand are used only for todos saved before this change, string ids and unexpected `due` values.
- Prior art: `tests/test_add_list.py` and `tests/test_done.py` (helpers `run_todo`, `assert_refused_unchanged`, one test per numbered behaviour). New tests follow them.
- Existing tests that compare a whole todo with `{"id", "title", "done"}` must expect the added `due: null`. This is the accepted contract change itself, not a test being weakened. No test is skipped or deleted.

## Acceptance Criteria
1. `./todo add "Pay rent" --due 2026-11-01` prints `{"id": 1, "title": "Pay rent", "done": false, "due": "2026-11-01"}`, exits 0, and `./todo list` shows the same todo. (stories 1, 4, 9)
2. `./todo add "Buy milk"` prints `"due": null`. (3, 4, 9)
3. `--due` before the title (`add --due 2026-11-01 Pay rent`) and after it give the same todo. (1)
4. Each of these exits 2 with exactly one line on stderr, empty stdout, and a store that is absent or byte-identical: `2026-02-30`, `tomorrow`, `2026-2-3`, `20260203`, `2026-02-03 ` (trailing space), `2026-02-03T10:00`, `0000-01-01`, `2026-13-01`, an empty value, `--due` with no value, `--due` twice, and a non-ASCII-digit date. (2)
5. `2024-02-29` is accepted and `2026-02-29` is refused. A date in the past is accepted. (1, 2)
6. With todos added in this order — A (no due), B (2026-12-01), C (2026-11-01), D (no due), E (2026-12-01) — `list` prints C, B, E, A, D. (5, 6, 7)
7. The ids in that list are those assigned when each was added; no id changes. The file is not reordered: the stored order is still A, B, C, D, E. (11)
8. Marking a done todo with an early due date: `done` prints it with its `due` unchanged, and `list` still sorts it by that date ahead of open todos with later dates. (8)
9. A file with todos saved before this change (no `due`) lists with `"due": null` on each, in file order after any dated ones; `done` on one prints `"due": null`; and `done` on an already done one leaves the file byte-identical. (10)
10. A stored `due` that is not a valid date string (for example `5` or `"soon"`) prints as `null` and sorts with the undated todos. (10)
11. Todos with string ids tie-break by position in the file, not by id. (7, 11)
12. `delete` still prints `{"deleted": <id>}`, and after deleting, a new todo gets an id never issued before. (11)
13. `add "--due=2026-11-01"` still creates a todo whose title is `--due=2026-11-01`, with `"due": null`. (3)
14. `make build`, `make test` and `make lint` are healthy.

## Out of Scope
Changing or removing a due date after a todo is added; reminders and "overdue" marking; times of day; relative dates such as "tomorrow"; filtering the list by date; a `--` end-of-options marker; the `--due=DATE` spelling; reordering the stored file; time zones; any change to `delete`; editing `GLOSSARY.md`, `knowledge/architecture/interface.md` or any ADR.

## Concerns
- **`add` stops accepting `--due` as a title word** (policy: public-contract): today `./todo add --due 2026-11-01` saves a todo titled `--due 2026-11-01`; after this change `--due 2026-11-01` is read as the option, so that input is refused for want of a title (and `add --due` alone is refused for want of a date). That is a change in meaning of input that works today, though the intent requires the option. The title can no longer begin with, contain or consist of the word `--due`. **Carried:** see Carried-forward Questions; the policy owner must approve this spec. Risk is set to high for this reason.
- **Every printed todo gains `due`, and `list` order changes when dates are present** (policy: public-contract): both are additions that break nothing for a script that never uses `--due` (such a list keeps today's order), so rule 1 holds. A script that compares a whole todo with exactly three fields will see a fourth, which the interface already allows ("Tickets add fields"). **Resolved:** recorded under Implementation Decisions (printed shape, list order).
- **Existing tests compare a todo with exactly `id`, `title` and `done`**: they must expect `due: null` once the field exists. **Resolved:** Testing Decisions; the code is not bent to fit the old expectation, and no test is skipped or deleted.
- **Open question on legacy todos** (intent): printed with `"due": null` and listed after dated ones. **Resolved:** Implementation Decisions (printed shape, list order).
- **Open question on past dates**: accepted. **Resolved:** Implementation Decisions (past dates).
- **Open question on format strictness**: exactly YYYY-MM-DD, nothing trimmed. **Resolved:** Implementation Decisions (format).
- **Open question on `--due` with no value, empty, repeated, or before the title**: refused for the first three, allowed before or after for the last. **Resolved:** Implementation Decisions (command line).
- **Open question on ties and id types**: by position in the file, which is the order added; ids are never compared. **Resolved:** Implementation Decisions (list order), ADR 0001.
- **Open question on done todos**: ordered like open ones, taking the intent literally. **Resolved:** Implementation Decisions (list order). The intent never says done todos sort differently; a product owner who wants them last would change what is built, so this is the reading to confirm at acceptance.
- **Open question on whether the stored file is reordered**: it is not. **Resolved:** Implementation Decisions (list order).
- **Open question on which commands print `due`**: `add`, `list` and `done`. **Resolved:** Implementation Decisions (printed shape).
- **Open question on extending the interface document**: yes, and adding a field is non-breaking under the policy (rule 1). **Carried:** the document is the product owner's, and headless I may not edit it; see Carried-forward Questions.
- **"Due date" is not in the glossary**: **Carried:** see Carried-forward Questions.
- **A stored `due` that is not a valid date** is not covered by the intent. **Resolved:** treated as no due date and printed as `null`, never rewritten (Implementation Decisions, printed shape).

## Carried-forward Questions
- Is it acceptable that a title can no longer contain the word `--due`, with no escape such as `--` provided in this change? (@todo/platform, owner of public-contract, before plan.)
- Should done todos sort by due date like open ones, as specified? (product owner, at acceptance of this spec, before plan.)
- Add "Due date" to `GLOSSARY.md` and extend the Todo entry as proposed. (glossary owners, before build.)
- Extend `knowledge/architecture/interface.md` with the `due` field, the `--due` option and the list order. (product-owner, before build.)
