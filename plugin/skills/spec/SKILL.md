---
name: spec
description: Produces the Design-stage artifact changes/<id>/spec.md from an accepted intent.md, applying the knowledge and policies that govern the change and flagging concerns. Use when an intent has been accepted, when asked to spec or design a change, or when a pipeline invokes the design stage.
argument-hint: "<changes/<id> folder> [(write | revise, headless)]"
---
# Write the spec

Collapse requirements and design into one pass over the accepted intent, with live policy applied while writing, not discovered in review.

Change folder and mode: $ARGUMENTS

1. Read `intent.md`. Stop if its `status` is not `accepted`. If `spec.md` exists, you are revising it because the intent or its knowledge changed: keep what still holds, change what is now required, and list what changed and why under Concerns.
2. Get the context: pipelines hand you `.opensdlc/out/context-<id>-spec.md`; interactively, run `python3 -m opensdlc context <id> --stage spec`. Read every document it lists, and use every policy skill those policies generate. If a document you know applies is missing, say so: its `systems`, `tags` or `paths` need fixing.
3. Explore the codebase enough to design against what exists. Follow the `opensdlc:domain` skill: use `GLOSSARY.md` terms and respect the ADRs.
4. Choose the seams under test before writing Testing Decisions: the public boundaries where behavior can be observed without reaching inside a module. Prefer existing seams, the highest possible, as few as possible. Interactively, confirm them with the user.
5. Write `spec.md` from [template.md](template.md). Keep every heading.
6. Be loud about concerns. Any policy you cannot satisfy, any conflict between policies, any ambiguity in the intent is a bullet under Concerns. Cite a policy as `(policy: <name>)`, with the name from its document, only in a concern its owner has to decide: one the spec cannot satisfy, or one that needs their judgement. Citing makes the owner approve the spec, so a policy the spec simply follows goes under Implementation Decisions, uncited, even where earlier specs cited it: a concern you resolve by following the policy is not the owner's to decide. Every concern ends in one of three ways, and its bullet says which:
   - **Resolved**: the codebase, glossary, ADRs, knowledge or intent settles it. Record the decision under Implementation Decisions and name it in the bullet.
   - **Carried**: the spec holds whichever way it is answered. Add it to Carried-forward Questions with who must answer it and before which stage.
   - **Escalated**: the answer changes what the spec builds, and only a person can give it. Ask; headless, write it to `.opensdlc/out/escalate.md`.

   A proposed resolution nobody has agreed to is none of these. A policy the spec has to bend is cited and carried, not escalated: write the spec the intent asks for, and carry the question to the policy's owner, who decides by approving the spec or not. Going back on an accepted ADR is escalated, because only people can write the ADR that supersedes it.
7. Set `risk`: `high` for anything touching auth, permissions, payments, PII, migrations or infrastructure, for a change that breaks a public contract (removes or alters behavior others rely on), or with a policy concern; `low` for small, well-covered changes, including additions to a public contract that break nothing; `standard` otherwise. High risk needs a tech lead's approval too.
8. Answer the intent's open questions where the codebase, glossary, ADRs or knowledge answer them; carry the rest forward the same way, with who must answer each and before which stage.
9. Interactively, pin with `python3 -m opensdlc pin <id>`, which records the intent and every knowledge document you were given. Never type a hash.
10. Interactively, when the spec is ready for decision, run `python3 -m opensdlc accept <id> --kind spec`. The PR is then a request for acceptance, and the approvals check decides who must approve it. Leave `status: draft` while it is still being shaped. Headless, skip steps 9 and 10: the pipeline does both, so neither is a concern.

When the arguments say `headless`, a pipeline is running you and nobody is watching. Never ask for confirmation or permission and never wait for an answer: decide, record the decision, and finish. Don't commit, branch or push; leave your changes in the working tree and the pipeline proposes them as a PR. Write only in the change folder: the pipeline refuses the whole patch if it touches anything else, so propose changes to `GLOSSARY.md`, ADRs, knowledge or `AGENTS.md` in the spec for their owners. Record each decision you would have asked about under Implementation Decisions or Carried-forward Questions. The pipeline pins and proposes acceptance for you. If you reach a question only a person can answer and the answer changes what the spec builds, write it to `.opensdlc/out/escalate.md`; the pipeline then leaves the spec in draft and labels the PR for a human. After you finish, the pipeline runs the `opensdlc:gate` skill on your spec in a session of its own, and its verdict can escalate too.

If the team's issue tracker is the source of truth for specs, publish the spec there too and record the issue in the intent's `ref`.
