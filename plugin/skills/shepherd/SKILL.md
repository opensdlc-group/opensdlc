---
name: shepherd
description: Takes a pull request to green by addressing unresolved review comments and failing checks until it waits only on code-owner approval. Use when a PR has open review comments or red checks, or when asked to get a PR ready to merge.
argument-hint: "<pull request number>"
disable-model-invocation: true
---
# Shepherd the PR

PR: $ARGUMENTS

Loop until nothing is left, then report:

1. List unresolved review threads (`gh pr view <n> --comments`, plus `gh api` for review threads) and failing checks (`gh pr checks <n>`).
2. For each failing check, read the log (`gh run view <id> --log-failed`), find the cause, and fix the code. If the failure is flaky, say so with evidence instead of retrying blindly.
3. For each review comment, make the change it asks for, or reply with a reason if you disagree. Resolve nothing a human must judge.
4. Keep `plan.md` in sync with any change that departs from it.
5. Push, wait for checks, repeat.

Never edit a pre-existing test to make it pass, dismiss a review, bypass branch protection, or merge. Stop when the PR is green and only code-owner approval remains, and summarize what you changed and what you declined.
