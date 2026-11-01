# Review instructions

## Axes
Review on three axes and tag every finding with its axis. They run separately so one cannot mask another.
- **Standards**: the diff follows `AGENTS.md`, the documented coding standards and this file. Code smells are judgment calls; a documented standard overrides them.
- **Spec**: the diff implements the change's `spec.md` and `plan.md`: nothing missing, nothing unasked for, nothing implemented wrong. Files the plan does not list, and plan slices with no matching change, are findings.
- **Security**: injection, authentication and authorization gaps, secrets in code, PII in logs or error messages, unsafe deserialization, dependency risk.

## Severity
- **Important**: would break behavior, leak data, breach a policy, edit a pre-existing test in a fix, or repeat something listed under "Things agents get wrong" in `AGENTS.md`.
- **Nit**: style, naming, readability, small simplifications.

## Do not report
- Generated files and lockfiles.
- Anything CI already enforces (formatting, lint, type errors).
- Preferences that contradict `AGENTS.md`.
