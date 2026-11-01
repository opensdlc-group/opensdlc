---
name: interview
description: Interviews someone until an idea, plan or decision has no unexamined branches left. Use when capturing intent, resolving a spec's open questions, or whenever a person's decision is needed before work can continue.
---
# Interview to shared understanding

Treat the topic as a tree of decisions: each answer opens the decisions that depend on it.

1. **Ask what can be answered now.** A question is ready when everything it depends on is settled. Ask every ready question in one numbered round; hold back any question whose answer depends on another question in the same round.
2. **Recommend an answer for each.** Phrase each question so "yes" accepts your recommendation, and make alternatives explicit where they matter.
3. **Look up facts yourself.** Anything the codebase, docs, tracker or glossary can tell you is yours to find, by reading or with the `opensdlc:researcher` agent. Only decisions go to the person. Do not wait on a lookup to ask the questions that do not depend on it.
4. **Recompute after every round.** Settled answers unlock new questions; ask them in the next round.
5. **Stop when nothing is left unexamined.** Every branch visited, nothing silently assumed. Summarize the decisions and get explicit confirmation before acting on them.

Format each question as:

```
**Q1. <short title>**: <the question, with options where they help>
→ Recommended: <your answer and the one-line reason>
```

Ask about problems before solutions, and about the user's world before the system's.
