# todo

A todo-list library for other Python code to import.

## Commands
- Build: `make build` (healthy: no output)
- Test: `make test` (healthy: ends with "OK")
- Test one file: `python3 -m unittest tests.test_<name>`
- Lint: `make lint` (healthy: no output)

## Verifying your work
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.
In the sandbox, `ls` also lists empty placeholder devices for files such as `CLAUDE.local.md`, `.mcp.json` and `.bashrc`. They are not part of the repository: ignore them.
To try the package by hand: `PYTHONPATH=src python3 -c "import todo; print(todo.__file__)"`

## How work flows here
Work moves through `changes/<id>/`: `intent.md` → `spec.md` → `plan.md` → code. Start implementation only from an accepted `plan.md`, and update `plan.md` in the same commit when the code departs from it.

## Conventions
- Python 3.12 standard library only. Code under `src/todo/`, tests under `tests/` with `unittest`; tests put `src` on the path.
- The public API is a contract: `knowledge/architecture/interface.md`.

## Architecture
- `src/todo/`: the package.
- `tests/`: unit tests.
