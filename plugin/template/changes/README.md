# Changes

Each folder is one change, named `YYYY-MM-<slug>`, and holds the artifact chain for it:

| File | Stage | Written by | Accepted by |
| :- | :- | :- | :- |
| `intent.md` | Plan | Originator with Claude (`/opensdlc:intent`, the claude.ai skill, or a ticket labelled `intent`) | Product owner |
| `spec.md` | Design | Claude (`/opensdlc:spec`, or automatically when an intent is accepted) | Product owner; plus a tech lead for `risk: high`; plus the owner of every policy its Concerns cite |
| `plan.md` | Build | Engineer with Claude in plan mode (`/opensdlc:plan`) | Engineer; plus a tech lead for `risk: high` |

## Acceptance

Acceptance is an approved merge. `python3 -m opensdlc accept <id> --kind <kind>` pins the artifact and sets `status: accepted` on your branch; the PR is then a request for acceptance. The **OpenSDLC approvals** check lists who must approve it, from `approvals` in `.opensdlc/config.json`, and passes only when each group has approved the PR's latest commit. The PR author, Claude and any bot never count. The merge is the record: author, approvers and time all live in git history.

The pipeline proposes acceptance on the PRs it opens, unless its confidence gate escalated. Edit the artifact on that branch before approving if it needs changes.

Merging an accepted artifact starts the next stage:
- accepted `intent.md` → Claude drafts `spec.md` as a PR
- accepted `spec.md` → Claude drafts `plan.md` as a PR for the engineer to refine
- accepted `plan.md` with a risk listed in `stages.build.autoRisk` → Claude implements it as a PR

## Pins

`spec.md` records the exact `intent.md` it was written from, and `plan.md` the exact `spec.md`, as `intent: intent.md@3f2a91c04b7e`. Both also pin the knowledge they were built on in `context`, as `knowledge/policies/secure-api.md@9b1c...`. A pin is a hash of the file's content, ignoring its `status` and `review-by` lines, so accepting or reviewing a document does not invalidate what was built on it, but any other edit does. It is content-addressed, so squash merges and rebases do not break it.

- `python3 -m opensdlc pin <id>` pins every draft to the current upstream. Pipelines run it after each stage; never type a hash by hand.
- An **accepted** artifact whose upstream has moved fails `check`. Either reopen it, which returns it and everything downstream to draft so the pipeline revises them, or re-pin it, which records in the PR that a human judged it still holds:
  - `python3 -m opensdlc reopen <id> --from spec`
  - `python3 -m opensdlc pin <id> --reaccept`
- A **draft** behind its upstream is a warning. When its upstream is accepted and changes, the pipeline revises it.
- Once a change's `plan.md` is **implemented**, knowledge that moves later is history, not an error: the pins record what the change was built against. `python3 -m opensdlc implement <id>` marks it; the pipeline runs it when a build is not escalated.

Editing an accepted intent therefore means deciding, in the same PR, what happens to the spec and plan built on it.

`python3 -m opensdlc check` (with `.opensdlc/cli` on `PYTHONPATH`) validates every folder and the knowledge base. **OpenSDLC checks** runs it on every PR with the base branch's copy of OpenSDLC, so a PR cannot loosen the rules it is judged by, and holds code PRs that name `Change: <id>` to the plan's "Files that change".
