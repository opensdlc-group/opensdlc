---
kind: plan
status: draft
spec: spec.md@<pin>
context: <pinned by `opensdlc pin`>
risk: <low | standard | high>
---
# Plan: <short title>

## Files that change
<One line per file created, modified or deleted, as `path/to/file` followed by why. Review and metrics compare this list with the merged diff.>

## Slices
<Numbered tracer-bullet slices. Each: title, blocked by, the end-to-end behavior it makes work, and the acceptance criteria from spec.md it satisfies. Prefactoring first. Each slice leaves the build green.>

## Risks
<What could break, the riskiest slice, rate limits, migrations, data, rollout.>

## Alternatives considered
<Options rejected and why.>

## Proof
<The exact commands and checks that prove the change works, mapped to every acceptance criterion.>
