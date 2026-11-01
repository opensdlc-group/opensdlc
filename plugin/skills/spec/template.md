---
kind: spec
status: draft
intent: intent.md@<pin>
context: <pinned by `opensdlc pin`>
risk: <low | standard | high>
---
# Spec: <short title>

## Problem Statement
<The problem from the user's perspective, traced to the intent.>

## Solution
<The solution from the user's perspective.>

## User Stories
<A long, numbered list: "As a <actor>, I want <feature>, so that <benefit>." Cover every aspect of the feature.>

## Implementation Decisions
<Modules built or changed, interfaces, schema changes, API contracts, architectural decisions. No file paths or code; those belong in plan.md.>

## Testing Decisions
<The seams under test, highest possible and as few as possible; what makes a good test here; prior art in the codebase.>

## Acceptance Criteria
<Observable checks that prove each user story, written so they become tests at the seams above.>

## Out of Scope
<What this spec deliberately does not cover.>

## Concerns
<Every place a policy could not be satisfied, policies conflict, or the intent is ambiguous, one bullet each, written as: - **what** (policy: name): why. **Resolved:** the decision, recorded under Implementation Decisions; or **Carried:** see Carried-forward Questions; or **Escalated:** what was asked. Cite a policy only when its owner has to decide, because the named policy's owner must then approve the spec; a policy the spec simply follows goes under Implementation Decisions. Write None only if there are none.>

## Carried-forward Questions
<Open questions from intent.md that are still open, and new ones, each written as: - question (who must answer, before plan | build | release).>
