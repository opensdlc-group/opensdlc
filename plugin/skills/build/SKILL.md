---
name: build
description: Implements an accepted plan.md slice by slice, test-first at the spec's seams, keeping the plan in sync with the diff and verifying before it reports done. Use when a plan has been accepted and it is time to write the code, or when a pipeline runs the build stage for a low-risk change.
argument-hint: "<changes/<id> folder> [write] [headless]"
---
# Build from the plan

Change folder: $ARGUMENTS

When the arguments say `headless`, a pipeline is running you and nobody is watching. Never ask for confirmation or permission and never wait for an answer: decide, record the decision, and finish. Don't commit, branch or push; leave your changes in the working tree and the pipeline proposes them as a PR. Change code and this change folder only: the pipeline refuses the whole patch if it touches another change folder, `GLOSSARY.md`, ADRs, knowledge, `REVIEW.md`, `AGENTS.md`, `CLAUDE.md` or eval cases, so name changes those need in your report for their owners.

1. Read `intent.md`, `spec.md` and `plan.md`. Stop if the plan's `status` is not `accepted`. Interactively, also stop if `python3 -m opensdlc check` reports it stale; headless, the pipeline has checked.
2. Get the context: pipelines hand you `.opensdlc/out/context-<id>-build.md`; interactively, run `python3 -m opensdlc context <id> --stage build`. Use every policy skill it lists while you write.
3. Work the plan's slices in dependency order: any slice whose blockers are done. Build each with the `opensdlc:test-first` skill at the seams named in the spec's Testing Decisions.
4. Run single test files as you go and the full suite at the end of each slice. The build stays green slice to slice.
5. When the implementation departs from the plan, update `plan.md` in the same commit, including Files that change. The plan-match check fails any PR whose files the plan does not list.
6. Run every command in the plan's Proof section. The OpenSDLC hooks will not let the session finish until the commands in `verify.commands` have passed after your last edit, on their own: no `||`, `;` or pipes. Never skip, weaken or delete a failing test.
7. Interactively, run the `opensdlc:review` skill on the branch, fix every Important finding, and note judgment calls for the human reviewer. Headless, skip this: the pipeline's review stage runs next.
8. Interactively, get a final check from a context that did not write the code: the `opensdlc:verifier` agent, or the `opensdlc:verify` skill in a fresh session. Fix what it reports and re-run it. Headless, skip this: the pipeline's gate session verifies the build with `opensdlc:verify` before it judges, in a context of its own.
9. Interactively, set the plan's `status: implemented` in the final commit and put `Change: <id>` in the PR description. Headless, leave both to the pipeline: it marks the plan implemented when nothing escalated.
10. Report what changed, the verification output, and what the reviewer should look at first.

## Escalating from a headless run

If you reach a question only a person can answer, write it to `.opensdlc/out/escalate.md` and stop without marking the plan implemented. The pipeline labels the PR for a human.
