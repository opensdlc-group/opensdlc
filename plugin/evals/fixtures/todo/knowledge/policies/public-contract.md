---
kind: policy
owner: @todo/platform
review-by: 2027-12-31
description: Apply the public contract whenever a change adds to, alters or removes anything people or scripts use, such as commands, options, routes, methods, fields, page elements, ids, ordering or errors
always: true
stages: spec, plan, build, review
skill: public-contract
---
# Public contract

People and scripts depend on this product. Everything `knowledge/architecture/interface.md` describes, and everything an accepted change has added since, is the public contract.

## Rules

1. **Add, never take away.** Add commands, options, routes, methods, fields and page elements freely. Never rename or remove one, and never change the type, format or meaning of one that exists.
2. **Keep recorded promises.** Behaviour an accepted ADR promises, such as how ids are issued, changes only through a new ADR that supersedes it.
3. **Say so.** A spec that would break rule 1 or 2 cites this policy under Concerns, so its owner has to approve it before anything is built.

## How to check

Compare the change with `knowledge/architecture/interface.md`, the accepted specs in `changes/` and the ADRs in `docs/adr/`. In review, flag any removed or altered surface whose spec does not cite this policy.
