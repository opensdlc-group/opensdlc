# Security model

OpenSDLC's agents read untrusted text for a living: tickets, PR descriptions, CI logs, diffs from contributors. Any of it can carry a prompt injection. The design assumes an agent will one day follow one, and limits what that agent can reach.

## Agent jobs are read-only

Every workflow that runs Claude headlessly, except `@claude`, splits into a read-only agent job and a PR job. `opensdlc-advance` adds a read-only gate job between them.

**The agent job** has `contents: read` and nothing that writes.

- `actions/checkout` runs with `persist-credentials: false`, so no token sits in `.git/config`.
- Claude Code runs through one shared step, `.github/actions/opensdlc-agent`, which holds the pinned action and stops the job unless it has exactly one credential.
- Claude Code runs with `.opensdlc/ci-settings.json`:
  - Bash runs inside the OS sandbox (`bubblewrap` and `socat`, installed by `.github/actions/opensdlc-sandbox`), and Claude Code refuses to start if the sandbox is unavailable.
  - Shell commands cannot see `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` or the Actions runtime and OIDC tokens.
  - Network from shell commands reaches GitHub and the npm and PyPI registries only.
  - File tools and sandboxed commands cannot write what the running job loads: `.github/`, any `.claude/`, `.claude.json`, `.mcp.json`, any `AGENTS.md`, `CLAUDE.md` or `CLAUDE.local.md`, and the OpenSDLC CLI and config.
  - Everything else a human must own, such as knowledge, eval cases, `REVIEW.md` and `.gitattributes`, is left to `patch-check`, which refuses it anywhere in the patch. So are nested copies of the files above, because the sandbox does not expand `**` patterns for shell commands.
  - File tools cannot read SSH, Docker, cloud CLI or Claude credentials in the home directory.
  - Inside the sandbox, Claude Code stands `/dev/null` in for dotfiles such as `.bashrc` and `.mcp.json` and for denied paths that don't exist. `.github/actions/opensdlc-sandbox` lists them in `.git/info/exclude` so `git status` doesn't show agents phantom files.
  - Bypass-permissions mode is disabled, and each job passes its own `--allowedTools`.
  - Each job also passes `--tools` with the built-in tools those rules name, so a tool the agent may not use is not even offered. A job whose rules name no Bash is not offered Bash at all.
  - Claude Code's bundled skills are off (`disableBundledSkills`), leaving the plugin's and the repository's.
  - A Bash command runs only when the job's `Bash(...)` rules name it, even inside the sandbox (`autoAllowBashIfSandboxed` is off; Claude Code turns it on by default). The sandbox then bounds what it can do.
  - The plugin, with its skills and hooks, is checked out at the repository and ref `.opensdlc/config.json` pins, into the runner's temporary directory, before the agent runs. Agents cannot change the pin, and an upgrade is a reviewed PR that runs the eval suite.
  - If the plugin repository is private, `OPENSDLC_PLUGIN_TOKEN` reads it. Only that checkout sees the token, and it is not kept in the checkout's git config, so no agent can reach it.
  - Every Bash command starts in the repository root (`CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR`). Claude Code resolves path rules against the session's working directory, so without it a single `cd` would point every allow and deny rule for file tools at the wrong folder: a denied `CLAUDE.md` becomes writable, and an allowed `.opensdlc/out/` does not.
- Untrusted text reaches the agent as files the workflow wrote beforehand: `ticket.md`, `pr.diff`, `failed.log`, `.opensdlc/out/evidence/`. CI triage reads the failing PR's code from `pr/`, while the sandbox setup and settings come from the default branch. The skills tell Claude to treat all of it as data.
- When Claude finishes, the job builds a patch against a copy of `.git` taken before Claude ran, so nothing the agent did to the repository's git configuration (hooks, filters, `fsmonitor`) executes. It uploads the patch and any `escalate.md`, `runbook.json`, `review.json` or `triage.md` as an artifact. Nothing runs from the workspace after Claude.

**The gate job** judges the work from a context that did not write it. Like the agent job, it is read-only, checks out without credentials and runs Claude Code in the sandbox. It applies the agent's patch only after `patch-check` passes, so a patch that rewrites `CLAUDE.md` or the gate's own instructions never reaches the session that judges it. For a build, the one gate session verifies the build with the `verify` skill before it judges, so a single context that did not write the code both runs the proof and decides. It uploads only `gate.json` and `verify.md`, and the gate may write nothing else.

**The PR job** has write permissions and never runs anything the agent wrote. It reads the gate's verdict with `opensdlc gate-check`, which fails closed: a missing or malformed verdict, or a build without a verification report starting `PASS`, counts as an escalation. `gate-check` also escalates, in code, a build that changes an existing test its plan does not list and a spec with a concern that says neither resolved, carried nor escalated.

- It checks out the commit the agent started from and applies the patch to a scratch index, leaving the workspace untouched. `opensdlc patch-check` then reads what git staged there, using the checkout's own CLI and config. It fails when the patch:
  - touches a path in `pipeline.forbiddenPaths`, compared without regard to case;
  - leaves the stage's scope: a spec or plan run may only touch its own change folder, and a build run may touch code but no other change folder;
  - creates more than one change folder, or edits an existing one, when the run may only start a new change (intake and monitors);
  - adds a symlink or submodule.
- Only then is the patch applied to the workspace. Every CLI call runs as `python -P`, so a module the patch adds at the repository root cannot shadow the CLI or the standard library.
- It pins, proposes acceptance unless the agent escalated, requests the reviewers the approval rules name, and opens the PR as the pipeline's GitHub App, with a token created for that job and revoked when it ends, or with `OPENSDLC_PR_TOKEN` when no App is set. PR bodies are written from files, never interpolated into shell or `GITHUB_OUTPUT`.
- Review findings are posted by `opensdlc review-publish`, which validates the reviewer's tally and recounts it rather than trusting its totals.

## Rules a PR cannot loosen

`opensdlc-checks` and `opensdlc-approvals` run on `pull_request_target` and replace the PR's `.opensdlc/` with the base branch's before judging. A PR that edits the approval rules, the forbidden paths or the CLI is judged by the rules it is trying to change, and nothing from the PR executes.

- The approvals check counts only approvals of the PR's latest commit, and never the author, Claude or a bot. An accepted or implemented artifact whose content changes needs approval again, so a build cannot quietly widen its own plan.
- Plan match only honours a plan that is accepted on the base branch, so a PR cannot bring its own permissive plan.

`pull_request_review` events run the workflow file from the PR, so a PR that edits `opensdlc-approvals.yml` could report its own approvals as met. Agents cannot change `.github/`, so this is a question of people. Close it by requiring code-owner review on `.github/`, and, where your plan allows, by adding both workflows as required workflows in a repository or organization ruleset pinned to the default branch.

## Evals

Eval runs execute the case commands in `evals/cases/` outside the sandbox, so those commands never see the API key or GitHub tokens, and agents cannot write eval cases.

## Autonomy is per environment

The plugin's hooks gate deploys by environment: development runs freely, staging asks in the session, production is denied unless the pipeline has set the release authorization.

In CI, the monitor runs a runbook only when Claude asks for one that the breached tier pre-approves, with the inputs the tier fixes. Claude cannot choose the environment. The CI failure-rate monitor counts only pushes to the default branch, so failing fork PRs cannot manufacture a breach. `rollback-deploy` runs in a `production-rollback` environment whose credentials can only roll back and whose deployment branches are limited to `main`. Rolling back is the pre-approved decision; add required reviewers to that environment if your team would rather approve each one. The weekly drill proves the rollback still works against `staging-rollback`.

## What this does not cover

- **`@claude`** needs write access to push fixes to the PR it was asked about. It is gated to repository members, runs sandboxed with the same settings, and cannot change workflows, but it is the one agent that can push.
- **Collaborators.** Anyone who can push a branch can run a workflow with the repository's secrets. OpenSDLC protects against untrusted content and agents, not against people with write access.
- **Fork PRs** get no secrets, so the review and eval stages skip them.
- **Local sessions** are protected by the plugin hooks and whatever managed settings your organization deploys. [managed-settings.example.json](managed-settings.example.json) turns on the same sandbox locally and forces the plugin on so its hooks survive `allowManagedHooksOnly`.
