---
name: verify
description: Checks that a built change works by running the plan's proof and the app, from a session that did not write the code, and reports PASS or FAIL with the evidence. Use after implementation and before a change is called done, or when a pipeline runs verification after a build.
argument-hint: "<changes/<id> folder> [headless]"
---
# Verify a change

Change folder: $ARGUMENTS

You verify; you never fix. Leave every file as you found it.

1. Read the change's `plan.md` Proof section and the Verifying section of `AGENTS.md`.
2. Run every listed command. Start the app if the plan's proof needs it, exercise the changed behavior, and exercise the two nearest neighboring flows. Run each command as its own Bash call, written the way `AGENTS.md` shows it: no `;` or `&&` chains, shell functions or `echo $?`. Unattended runs refuse anything their permissions don't name, and the tool already reports each exit code. They also give every command its own network, so a server started in one command cannot be reached from the next: exercise a running app with the one command `AGENTS.md` gives for trying it by hand.
3. Compare what you saw with the plan and the spec's acceptance criteria.

Report:

- `PASS` or `FAIL` on the first line, and nothing else on it.
- Each command you ran with its exit code and the lines of output that matter.
- Every behavior that does not match `plan.md` or `spec.md`, with how to reproduce it.
- Files changed that the plan does not name.

Do not soften a failure. Headless, write the report to `.opensdlc/out/verify.md` with the Write tool; interactively, give it as your answer.
