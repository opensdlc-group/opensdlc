# Knowledge

Owned, reviewed documents that scope what each stage reads. `python3 -m opensdlc context <change> --stage <stage>` selects the ones that apply to a change and says why; `opensdlc pin` records their exact versions in the spec and plan, so an accepted spec fails `check` when a policy it was built on changes.

## Kinds

| Kind | Folder | What it holds | Required fields |
| :- | :- | :- | :- |
| `policy` | `knowledge/policies/` | Rules that must hold: security, compliance, data handling, brand, UX, API conventions | `owner`, `review-by`, `description` |
| `architecture` | `knowledge/architecture/` | How a system or area is built and why, what not to break | `owner`, `review-by` |
| `domain` | `knowledge/domain/` | Domain rules and processes beyond what `GLOSSARY.md` defines | `owner`, `review-by` |
| `decision` | `docs/adr/` | Architecture decision records | none |

`GLOSSARY.md` is read at every stage but never pinned: terms get added all the time, and that should not reopen accepted specs.

## Frontmatter

```yaml
---
kind: policy
owner: @YOUR-ORG/security          # a team or a login; approves every change to this document
review-by: 2027-04-30              # check warns 14 days before and fails 14 days after
description: Secure external APIs  # policies only; becomes the generated skill's trigger
systems: claims-api, portal        # selected when the intent or spec names one of these
tags: api, auth                    # selected when the intent's tags include one of these
paths: src/api/**, **/routes/**    # selected when the plan or PR touches a matching file
stages: spec, plan, review         # defaults to every stage
always: false                      # true selects it for every change
skill: secure-api-review           # policies only; generates .claude/skills/<skill>/SKILL.md
---
```

`review-by` and `status` changes do not invalidate pins: reviewing a document without changing it leaves accepted specs alone.

## Policies become skills

A policy with `skill` generates `.claude/skills/<skill>/SKILL.md` with `python3 -m opensdlc skills`, so Claude applies the policy while writing, not only at review. `check` fails when a generated skill is missing, edited by hand, or behind its policy. Edit the policy, never the generated skill.

## Ownership

The owner's approval is required on every PR that changes their document, and on every spec whose Concerns cite their policy as `(policy: <name>)`. The approvals check enforces both.

## Shared organization knowledge

To share documents across repositories, keep them in one repository and sync them into `knowledge/org/` here with `opensdlc-knowledge-sync.yml`. The sync PR then fails `check` on every accepted spec built on a changed policy, which is the review of that policy's impact on this repository.
