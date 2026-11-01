---
name: domain
description: Keeps the project's shared language and decisions current in GLOSSARY.md and docs/adr/. Use when a term is fuzzy or used inconsistently, when a hard-to-reverse decision is made, or when writing an intent or spec that should use the project's vocabulary.
---
# Domain language and decisions

Every artifact in the loop should speak the same language as the code and the people. This skill maintains that language.

## Reading

Before writing an intent, spec or plan, read `GLOSSARY.md` and the ADRs in `docs/adr/` that touch the area. A project without them yet is normal; don't report their absence as a problem. Use glossary terms exactly; respect accepted decisions or say explicitly that the change revisits one.

## Sharpening

- When someone uses a term differently from the glossary, say so at once and ask which meaning they intend.
- When a term is vague or overloaded, propose one precise word and the boundary it draws.
- Test definitions against concrete edge cases until the boundary is clear.
- When the code contradicts what someone says, show them where.

## Writing

- Update `GLOSSARY.md` as soon as a term is settled, in [glossary-format.md](glossary-format.md). It holds meanings only: no implementation detail, no plans.
- Record an ADR only when a decision is hard to reverse, would surprise a future reader, and came from a real trade-off. Use [adr-format.md](adr-format.md) and the next number in `docs/adr/`.
- Create either file the first time there is something to put in it.
- In a headless run, never edit `GLOSSARY.md` or `docs/adr/`. People own them, and the pipeline refuses the whole patch if it touches them. Write the settled term or the decision into the artifact you are producing, as a proposal for its owner to add.
