# OpenSDLC setup checklist

## Repository
- [ ] `.claude/settings.json`: `opensdlc-group/opensdlc` points at the marketplace you install from; change it only if you run your own fork.
- [ ] `.github/CODEOWNERS`: real teams in place of `@YOUR-ORG/...`.
- [ ] `.opensdlc/config.json`:
  - [ ] `protected`, `tests`, `format` and `verify.commands` match this repo.
  - [ ] `environments`: the command and MCP tool patterns this repo deploys with, per environment, and the autonomy each gets.
  - [ ] `approvals.groups`: the teams or logins that accept intents, specs and plans.
  - [ ] `stages.build.allowedTools`: the repo's real build, test and lint commands, and the command that runs one test file, written as `AGENTS.md` shows them.
  - [ ] `stages.verify.allowedTools`: the same build, test and lint commands, and the one command that starts the app, exercises it and stops it, since every sandboxed command gets its own network. Check that command runs inside the sandbox: a tool that listens on a Unix socket, such as the `tsx` command, cannot.
  - [ ] `stages.<stage>.model` for any stage that should not run on the account's default model, such as `"haiku"`.
  - [ ] `metrics`: agent signals, CI workflow, incident source, release gate job, ticket label, and `adoptedAt` (today) so the report keeps a pre-adoption baseline.
- [ ] `AGENTS.md`: real commands with healthy output, under a page.
- [ ] `knowledge/`: the policies, architecture notes and domain rules a spec must respect, each with an owner and a `review-by` date, one rule or decision per document, linked with `requires`. List the tags you use in `knowledge.tags`. Run `python3 -m opensdlc skills` after adding a policy with `skill`.
- [ ] `rollback-deploy.yml`: the real rollback command, or the monitor's `runbooks` list emptied.
- [ ] The CI workflow name in `opensdlc-ci-triage.yml` and the `ci-failure-rate` monitor matches this repo's CI workflow.

## Secrets and variables (admin)
- [ ] Install the Claude GitHub App on the repository.
- [ ] Secret `ANTHROPIC_API_KEY` (or switch the workflows to `claude_code_oauth_token` or workload identity federation).
- [ ] Secret `OPENSDLC_PR_TOKEN` (required): a GitHub App's token, or a fine-grained token on a machine account, with contents and pull-requests write and no workflows permission. Never a person's own token: OpenSDLC opens every PR with it, and GitHub never lets a PR's author approve it. The PRs then trigger the checks and can request team reviews.
- [ ] Secret `OPENSDLC_ORG_TOKEN`: read access to organization team membership, so the approvals check can resolve `@org/team` groups. Not needed if `approvals.groups` lists logins only.
- [ ] `plugin` in `.opensdlc/config.json`: the OpenSDLC repository and the tag or commit every workflow loads, e.g. `{"repository": "opensdlc-group/opensdlc", "ref": "v0.7.0"}`. Upgrade by changing it in a PR, which runs the eval suite before anyone merges it.
- [ ] Optional: secret `OPENSDLC_PLUGIN_TOKEN` if the plugin repository `plugin.repository` names is private: a fine-grained token with read access to that repository's contents and nothing else.
- [ ] Optional: variable `OPENSDLC_KNOWLEDGE_REPO` (`owner/repo` holding shared knowledge, under `knowledge/` or `OPENSDLC_KNOWLEDGE_PATH`) and secret `OPENSDLC_KNOWLEDGE_TOKEN` if that repository is private.
- [ ] Optional: variable `OPENSDLC_BLOCK_ON_IMPORTANT=true` to fail the review check on Important findings.
- [ ] Label `intent`, for tickets the intake workflow should turn into intents. Only people with write access can trigger it.

## Environments (admin)
- [ ] `production`: required reviewers, for normal deploys.
- [ ] `production-rollback`: credentials that can only roll back, deployment branches limited to `main`. Without required reviewers it is the pre-approved rollback the monitor may trigger at its `propose` tier; add reviewers if you want to approve each one.
- [ ] `staging-rollback`: the same rollback against staging, for the weekly drill.

## Branch protection on main (admin)
- [ ] Require pull requests; no direct pushes, including for automation.
- [ ] Require code-owner review, and dismiss stale approvals when new commits are pushed. Code-owner review on `.github/` is what stops a PR from editing the workflows that judge it.
- [ ] Where your plan allows, add `opensdlc-checks.yml` and `opensdlc-approvals.yml` as required workflows in a ruleset pinned to the default branch.
- [ ] Require the checks `artifacts`, `plan-match`, `approvals`, `review`, `secret-scan`, `dependency-scan`, `static-analysis`, and your CI.
- [ ] Set `planMatch.required` to `true` once every code PR names its change with `Change: <id>`.

## Teams of one or two
Every approval rule above assumes someone other than the author is free to review. With one or two people, approving every artifact becomes the queue the work waits in. Drop the wait, not the look: approve what carries risk, and read the rest after it merges.

```json
"approvals": {
  "groups": { "owners": ["your-login"] },
  "rules": {
    "intent": { "require": ["owners"] },
    "spec": { "require": ["owners"] },
    "plan": { "require": [], "high": ["owners"] }
  }
},
"stages": {
  "gate": { "model": "opus" }
}
```

- [ ] One group naming the people, used by every rule, and the same logins in place of the teams in `CODEOWNERS`.
- [ ] Plans wait for approval only when `/opensdlc:plan` rates them `high` risk. The gate checks that rating and escalates a plan that touches auth, payments, PII, migrations or infrastructure without it. Intents and specs keep their approval.
- [ ] `stages.gate.model` names a different model from the one specs and plans run on, which is the account's default unless `stages.spec.model` and `stages.plan.model` say otherwise, so the gate doesn't share the author's blind spots. A larger gate model costs more per session.
- [ ] Required approvals on the branch ruleset set to 0, with `approvals` a required check, so the rules above decide who approves. Code-owner review still applies to `.github/`, `knowledge/` and `docs/adr/`.
- [ ] A team of one: add yourself to the ruleset's bypass list, for pull requests only. Agents can't touch `.github/`, `knowledge/` or `docs/adr/`, so those changes are yours, and nobody can approve their own pull request.
- [ ] `AGENTS.md`: every pull request description carries a walk-through of what changed and why, with screenshots for any change to the UI. Read them after the merge; that's where you catch what no check measures.
- [ ] Label `ceremony`, added to any pull request whose approval taught you nothing. After a month, `opensdlc metrics` shows which approvals to drop.

A plan that needs no approval still needs merging; that click is the one wait left.

## Managed settings (platform team)
- [ ] Deploy [managed-settings.example.json](https://github.com/opensdlc-group/opensdlc/blob/main/docs/managed-settings.example.json), adapted, through MDM or the admin console. It force-enables the plugin so its hooks keep running under `allowManagedHooksOnly`, and turns on the sandbox for local sessions.

## Switch on in this order
1. `AGENTS.md`, `REVIEW.md`, the plugin's hooks, `opensdlc-review.yml` and `opensdlc-security.yml`. Tune for a fortnight; `opensdlc-review-tuning.yml` reports what to change.
2. `changes/` and `knowledge/` with `opensdlc-checks.yml` and `opensdlc-approvals.yml`; write intents and specs with the skills. Give product owners the claude.ai skill.
3. `opensdlc-evals.yml` once there are 20 to 50 real cases in `evals/cases/`.
4. `opensdlc-intake.yml` and `opensdlc-advance.yml` for ticket → intent → spec → draft plan. Leave `stages.build.autoRisk` empty at first.
5. `opensdlc-ci-triage.yml`, then `opensdlc-monitor.yml` with `diagnose` tiers only.
6. `opensdlc-rollback-drill.yml` until it passes every week.
7. `autoRisk: ["low"]` and `propose` tiers, once the review gate, evals and rollback drill have proven themselves.
