# todo

A command-line todo list.

## Commands
- Build: `make build` (healthy: no output)
- Test: `make test` (healthy: ends with "OK")
- Lint: `make lint` (healthy: no output)

## Verifying your work
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.
In the sandbox, `ls` also lists empty placeholder devices for files such as `CLAUDE.local.md`, `.mcp.json` and `.bashrc`. They are not part of the repository: ignore them.
To try a command by hand, keep its file in `$TMPDIR`, the only place outside the repository the sandbox lets it write: `TODO_FILE="$TMPDIR/todo.json" ./todo list`

## How work flows here
Work moves through `changes/<id>/`: `intent.md` → `spec.md` → `plan.md` → code. Start implementation only from an accepted `plan.md`, and update `plan.md` in the same commit when the code departs from it.

## Conventions
- Python 3.12 standard library only. Code under `src/todo_cli/`, tests under `tests/` with `unittest`.
- The command-line interface is a public contract: `knowledge/architecture/interface.md`.

## Architecture
- `todo`: the entry point, runs `python3 -m todo_cli`.
- `src/todo_cli/`: the program.
- `tests/`: unit and end-to-end tests.
