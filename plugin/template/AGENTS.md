# <Project name>

## Commands
- Build: `make build` (healthy: ends with "Build succeeded")
- Test: `make test` (healthy: all green, 0 skipped)
- Test one file: `<the command that runs a single test file>`
- Try by hand: `<one command that starts the app, exercises it and stops it>`
- Lint: `make lint` (healthy: zero warnings)

## Verifying your work
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.
In the sandbox, `ls` also lists empty placeholder devices for files such as `CLAUDE.local.md`, `.mcp.json` and `.bashrc`. They are not part of the repository: ignore them.

## How work flows here
Work moves through `changes/<id>/`: `intent.md` → `spec.md` → `plan.md` → code. Start implementation only from an accepted `plan.md`, and update `plan.md` in the same commit when the code departs from it. Bugs start with a failing test (`/opensdlc:repro`).

## Conventions
- <The few conventions that matter and that the code does not make obvious.>

## Architecture
- <Top-level directories and what lives in each, in one line apiece.>

## Things agents get wrong
- <Add a line when the same correction is needed twice. Keep this file under a page.>
