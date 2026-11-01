# Security policy

OpenSDLC runs AI agents inside other people's CI with access to their code, so we treat security reports as our highest priority.

## Reporting a vulnerability

Report it privately through [GitHub's private vulnerability reporting](https://github.com/opensdlc-group/opensdlc/security/advisories/new). Please don't open a public issue, pull request or discussion.

Include what you can of:

- the component: a hook, the CLI, a template workflow, a skill or the bench
- how to reproduce it, ideally as a repository, ticket text or pull request an agent would act on
- what an attacker gains, for example writing to a protected path, escaping a stage's scope, reading a secret or getting a change merged without its approvals

We aim to acknowledge a report within 5 working days and to agree a fix and disclosure date with you. We follow coordinated disclosure: we publish an advisory once a fix is released, or 90 days after the report, whichever is sooner, and credit you unless you'd rather we didn't.

## Supported versions

Only the latest release gets security fixes. Adopting repositories pin a release in `.opensdlc/config.json`; upgrade by changing that pin in a pull request.

## Scope

[docs/security-model.md](docs/security-model.md) describes what OpenSDLC defends against, how, and what is out of scope. Prompt injection that makes an agent write something harmful is in scope when it gets past a control that model describes, such as `patch-check`, the sandbox, a stage's tool rules or the approval rules. An agent writing poor code that review then catches is not a vulnerability.
