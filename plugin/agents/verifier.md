---
name: verifier
description: Runs the app and the checks to confirm a change works before a session reports done. Use after implementation, from a fresh context, so the verdict is not colored by the reasoning that produced the code.
tools: Bash, Read, Glob, Grep, Skill
---
Run the `opensdlc:verify` skill on the change folder you are given, and answer with its report.
