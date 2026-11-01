---
name: learn
description: Turns a repeated mistake into an AGENTS.md rule or a deterministic check, and a resolved incident or fixed vulnerability into a permanent eval case. Use when Claude makes the same mistake twice, when review flags a repeat finding, or when an incident or security fix has shipped.
argument-hint: "[what went wrong, or incident/PR reference]"
---
# Make the loop learn

Input: $ARGUMENTS

## A repeated mistake

1. Confirm it is a repeat: the same correction in review or conversation at least twice.
2. Classify it. A mechanical mistake (a banned API, an import shape, a file-location rule) gets a deterministic check: a lint rule, an OpenSDLC `protected` path, or a hook. Default to the check over the rule.
3. A judgment call gets one line under "Things agents get wrong" in `AGENTS.md`: an instruction, not a story, with the reason only if it is not obvious. Merge with an existing line rather than adding a near-duplicate, and keep `AGENTS.md` under a page.

## An incident or fixed vulnerability

1. Find the fix commit and the behavior it guards.
2. Write `evals/cases/<id>.json`. `incident` must match the incident's ID in the tracker; the metrics collector uses it to time incident-to-eval.

   ```json
   {
     "id": "<kebab-id>",
     "incident": "<incident ID>",
     "origin": "<PR or incident URL>",
     "ref": "<commit before the fix>",
     "prompt": "<the task an engineer would have given, in their words>",
     "allowedTools": "Read,Edit,Glob,Grep,Bash(make test)",
     "maxTurns": 40,
     "checks": [
       {"type": "command", "run": "make test"},
       {"type": "unchanged", "paths": ["tests/**"]},
       {"type": "contains", "file": "<path>", "pattern": "<regex the fix must satisfy>"}
     ]
   }
   ```

3. Use only check types the runner supports: `command`, `unchanged`, `contains`, `absent`, `output`.
4. Run it once with `python3 -m opensdlc eval --case <id>` and confirm it passes against the fixed code.
