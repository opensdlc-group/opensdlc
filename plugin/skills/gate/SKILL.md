---
name: gate
description: Judges a stage's output adversarially, from a fresh session that did not write it, and decides whether a spec, plan or build continues down the pipeline or goes to a person. Use when a pipeline runs the gate after a stage, or to second-guess a draft before asking for acceptance.
argument-hint: "<changes/<id> folder> <spec | plan | build> [headless]"
---
# Confidence gate

Arguments: $ARGUMENTS

Your job is to find reasons this work should not continue without a person. Assume it is wrong until the evidence says otherwise. You did not write it, and you have only the evidence: the change folder's artifacts, the working-tree diff against `HEAD`, and for a build the verification report in `.opensdlc/out/verify.md`.

For a build, produce that report first: follow the `opensdlc:verify` skill, which writes `.opensdlc/out/verify.md`, and then judge with its report as evidence. Headless, the pipeline runs no separate verification, so a build you do not verify escalates.

Read files with Read and Glob, and run each git command as its own Bash call: unattended runs refuse `cd`, `;` or `&&` chains and loops. The pipeline pins the artifacts and proposes acceptance after you, so unfilled `intent:` or `context:` hashes and `status: draft` are expected. An upstream artifact with `status: accepted` has been approved by the people the approval rules name, together with its `risk` and the questions it carries, so neither is a reason to escalate the stages that follow it.

The pipeline already checks in code what needs no judgement, so leave it alone: `patch-check` keeps agents off paths people own, `plan-match` holds code to the plan's files, and `gate-check` escalates a build whose verification did not pass or that changes an existing test the plan does not list, and a spec with a concern that says neither resolved, carried nor escalated. Judge only:

1. The output does what the previous artifact asked: spec against intent, plan against spec, diff against plan.
2. A spec or plan that touches auth, permissions, payments, PII, migrations or infrastructure says so with `risk: high`.
3. A concern the spec marks resolved is recorded under Implementation Decisions, and one it marks carried is in Carried-forward Questions with who must answer it.
4. For a build, the evidence in the verification report holds up: the commands it quotes ran and passed.

For a spec or a plan, the change folder is the evidence; you need no git commands. Any single failed check means escalate. Do not edit anything except the verdict.

Headless, write the verdict to `.opensdlc/out/gate.json` with the Write tool, and nothing else:

```json
{"verdict": "escalate", "reasons": ["The plan adds a migration, but its risk is low."]}
```

`verdict` is `continue` or `escalate`; `reasons` holds one sentence per failed check, empty when continuing. Interactively, give the verdict on the first line, then one bullet per reason.
