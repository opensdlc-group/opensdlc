# todo-web

A single-page todo app.

## Commands
- Build: `make build` (healthy: ends with "built in")
- Test: `make test` (healthy: "Test Files  N passed")
- Test one file: `npx vitest run <file>`
- Lint: `make lint` (healthy: no output)

## Verifying your work
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.
In the sandbox, `ls` also lists empty placeholder devices for files such as `CLAUDE.local.md`, `.mcp.json` and `.bashrc`. They are not part of the repository: ignore them.

## How work flows here
Work moves through `changes/<id>/`: `intent.md` → `spec.md` → `plan.md` → code. Start implementation only from an accepted `plan.md`, and update `plan.md` in the same commit when the code departs from it.

## Conventions
- TypeScript, React 19 and Vite. Dependencies are fixed; don't add packages.
- Test components with Testing Library in Vitest, next to the code as `*.test.tsx`. Call `cleanup()` after each test if you render more than once.
- The page's `data-testid` attributes are a public contract: `knowledge/architecture/interface.md`.

## Architecture
- `src/App.tsx`: the app.
- `src/main.tsx`: mounts it.
