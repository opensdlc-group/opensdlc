# todo-api

An HTTP API for a todo list.

## Commands
- Build: `make build` (healthy: no output)
- Test: `make test` (healthy: "Test Files  N passed")
- Test one file: `npx vitest run <file>`
- Lint: `make lint` (healthy: no output)
- Run: `PORT=3000 npm start`
- Try by hand: `./try 'POST /todos {"title":"Buy milk"}' 'GET /todos'` starts the server, sends each request, prints each status and body, then stops the server. In the sandbox every command gets its own network, so a server started in one command can't be reached from the next.

## Verifying your work
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.
In the sandbox, `ls` also lists empty placeholder devices for files such as `CLAUDE.local.md`, `.mcp.json` and `.bashrc`. They are not part of the repository: ignore them.

## How work flows here
Work moves through `changes/<id>/`: `intent.md` → `spec.md` → `plan.md` → code. Start implementation only from an accepted `plan.md`, and update `plan.md` in the same commit when the code departs from it.

## Conventions
- TypeScript on Node 22 with Hono. Dependencies are fixed; don't add packages.
- Test routes with `app.request(...)` in Vitest, next to the code as `*.test.ts`.
- The HTTP API is a public contract: `knowledge/architecture/interface.md`.

## Architecture
- `src/app.ts`: the Hono app and its routes.
- `src/server.ts`: starts the server on `PORT`.
