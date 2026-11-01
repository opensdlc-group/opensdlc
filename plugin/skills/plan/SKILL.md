---
name: plan
description: Produces the Build-stage implementation plan changes/<id>/plan.md from an accepted spec.md, before any code is written. Use when starting implementation of a specced change, when asked for an implementation plan, or when a pipeline drafts a plan for an engineer to refine.
argument-hint: "<changes/<id> folder> [(write | revise, headless)]"
---
# Write the plan

No code until a plan is accepted. The plan is what review and the plan-match check later hold the diff to.

Change folder and mode: $ARGUMENTS

1. Read `intent.md` and `spec.md`. Stop if the spec is not `accepted`. If `plan.md` exists, you are revising it because the spec or its knowledge changed: keep the slices that still hold and record what changed under Alternatives considered.
2. Get the context: pipelines hand you `.opensdlc/out/context-<id>-plan.md`; interactively, run `python3 -m opensdlc context <id> --stage plan`. Read every document it lists.
3. Explore the codebase read-only. In an interactive session, work in plan mode.
4. Break the work into tracer-bullet slices:
   - each slice cuts a narrow but complete path through every layer and is verifiable on its own
   - each slice fits a single fresh context window
   - prefactoring comes first: make the change easy, then make the easy change
   - a wide mechanical refactor is sequenced expand, migrate in batches, contract, never forced into one slice
   - every slice names the slices that block it
5. Write `plan.md` from [template.md](template.md). Name every file under Files that change, one path at the start of each line; globs are allowed for generated output. CI fails a PR that changes a file the plan does not list.
6. Set `risk`:
   - `low`: small blast radius, covered by existing tests, no schema, auth, payments or infra change, and nothing that breaks a public API (additions are fine)
   - `high`: auth, permissions, payments, PII, migrations, infra, a breaking change to a public API, or anything the spec flags
   - `standard`: everything else
7. Interrogate the plan before offering it: what could this break, which slice is riskiest, what did you choose not to do. Record the answers under Risks and Alternatives considered.
8. Iterate with the engineer until someone who never saw the conversation could implement from the plan alone.
9. Interactively, pin with `python3 -m opensdlc pin <id>`, then propose acceptance with `python3 -m opensdlc accept <id> --kind plan` when it is ready. The approvals check requires an engineer, and a tech lead for `high` risk. The author never counts. Headless, skip this step: the pipeline does both, so neither is a concern.

When the arguments say `headless`, a pipeline is running you and nobody is watching. Never ask for confirmation or permission and never wait for an answer: decide, record the decision, and finish. Don't commit, branch or push; leave your changes in the working tree and the pipeline proposes them as a PR. Write only in the change folder: the pipeline refuses the whole patch if it touches anything else, so propose changes to `GLOSSARY.md`, ADRs, knowledge or `AGENTS.md` in the plan for their owners. The pipeline pins the plan and proposes acceptance, and the engineer refines it on the PR branch before approving. If you reach a question only a person can answer, write it to `.opensdlc/out/escalate.md`; the pipeline then leaves the plan in draft and labels the PR for a human. After you finish, the pipeline runs the `opensdlc:gate` skill on your plan in a session of its own, and its verdict can escalate too.

If the team works from tickets, create one per slice with its blockers, and link them from the plan.
