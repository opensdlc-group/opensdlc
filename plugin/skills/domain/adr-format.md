# ADR format

File name: `docs/adr/NNNN-<kebab-title>.md`, numbered in order. The frontmatter lets `opensdlc context` select the decision for changes that touch the same area.

```markdown
---
kind: decision
status: accepted
date: YYYY-MM-DD
change: changes/<id>/   # if one prompted it
systems: <systems this constrains>
paths: <globs of the code it governs>
---
# NNNN. <Decision as a short statement>

## Context
<The forces at play and what made this decision necessary.>

## Decision
<What we decided, stated plainly.>

## Alternatives
<Each option rejected and why.>

## Consequences
<What becomes easier, what becomes harder, what we will watch.>
```

To supersede a decision, write a new ADR and set the old one's `status: superseded by NNNN`.
