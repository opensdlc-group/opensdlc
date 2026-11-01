---
name: adopt
description: Scaffolds OpenSDLC into the current repository and tailors it to the codebase. Use when a team starts using OpenSDLC in a repository, or asks to set it up or bring a partial setup up to date.
disable-model-invocation: true
allowed-tools: Bash(cp -R -n ${CLAUDE_PLUGIN_ROOT}/template/. .) Bash(git status *) Bash(git ls-files *)
---
# Adopt OpenSDLC

1. Check `git status`. Stop if the tree is dirty.
2. Copy the template without overwriting anything: `cp -R -n ${CLAUDE_PLUGIN_ROOT}/template/. .`
3. List what already existed and was therefore not copied (`AGENTS.md`, `CLAUDE.md`, `REVIEW.md`, `.claude/settings.json`, workflows). For each, propose a merge rather than replacing it. A `CLAUDE.md` that holds instructions moves into `AGENTS.md`, and `CLAUDE.md` keeps only the line `@AGENTS.md`, so every agent reads the same file.
4. Tailor to the repo, reading the build files and layout:
   - `AGENTS.md`: real build, test and lint commands with an example of healthy output; conventions; architecture in a few lines.
   - `.opensdlc/config.json`: `protected` paths (generated code, frozen packages, migrations), `tests` globs for this stack, `format` commands that exist here, `verify.commands` that prove a change works, `environments` with the command and tool patterns this repo deploys with, `stages.build.allowedTools` with the repo's real build, test and lint commands and the command that runs one test file.
   - `.claude/settings.json`: pre-approve the safe inner loop (build, test, lint, git read commands).
   - `.github/CODEOWNERS`: owners for `.github/`, `.claude/`, `.opensdlc/`, `evals/`, `AGENTS.md`, `CLAUDE.md`, `REVIEW.md` and `knowledge/`.
   - `.opensdlc/config.json` `approvals.groups`: who accepts intents, specs and plans.
   - `.opensdlc/config.json` `metrics`: the agent signals this repo uses (bot logins, branch prefixes, labels), the CI workflow name, how incidents are tracked, the release gate job, and `adoptedAt` set to today.
   - `knowledge/`: ask which policies, architecture notes and domain rules a spec here must respect, and who owns each. Write the ones the user can state now; list the rest as gaps.
5. Leave `evals/cases/` with the example only. Real cases come from real past work.
6. Finish by walking the user through [checklist.md](checklist.md): secrets, repository variables, branch protection, and the order to switch stages on. Tick off what you could do here and list what needs an admin.
