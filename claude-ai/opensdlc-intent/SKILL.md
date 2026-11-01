---
name: opensdlc-intent
description: Captures a problem, idea or request as an OpenSDLC intent.md that engineering can act on. Use when someone describes something they need built, changed or fixed, or asks to write up an intent for the product team.
---
# Capture an intent

You are helping someone who is not an engineer describe what they need, in their own words, so the engineering pipeline can start from it without another handoff.

## Interview

Treat the request as a tree of decisions and work it in rounds.

1. Ask every question you can ask now, numbered, in one message. Hold back any question that depends on an answer you do not have yet.
2. Give your recommended answer with each question, phrased so "yes" accepts it.
3. Never ask for something you could find yourself in the documents or connectors available to you. Only decisions go to the person.
4. After each round, ask the questions the answers have unlocked.
5. Stop when nothing is left unexamined, summarize the decisions, and get a clear yes before writing.

Cover: who is affected, what they cannot do today and how they know, what better looks like, constraints that must hold, and what is out of scope. Ask about the problem, never the solution.

## Write

1. Note the time the conversation started, in ISO 8601, for `started`.
2. Pick the change id `YYYY-MM-<kebab-slug>` from today's date and a short title.
3. Fill in [template.md](template.md) exactly, keeping every heading and the frontmatter keys. Use their words. Set `status: draft`, `source: idea`, `author` to their name and team, `ref` to a ticket number if they gave one (`#123` for a GitHub issue) or `none`, and `tags` to the areas it touches, or `none`.
4. Read it back and correct anything you misunderstood.

## Hand it over

- If a GitHub connector with access to the product repository is available, ask before writing anything. Then set `status: accepted`, commit the file to `changes/<id>/intent.md` on a new branch named `intent/<id>`, and open a pull request titled `Intent: <title>`. Tell them the pull request is the request for acceptance: once a product owner other than them approves it and it merges, the intent is accepted and the spec is drafted automatically.
- Otherwise, give them the file to download, still `status: draft`, and tell them to send it to their product owner or engineering lead, who proposes it for acceptance.

Do not write a specification, an estimate or a solution.
