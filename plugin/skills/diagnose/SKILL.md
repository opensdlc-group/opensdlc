---
name: diagnose
description: Finds the cause of a bug, regression, failed build or breached metric before anything changes. Use when something is broken, slow or behaving unexpectedly and the cause is not yet proven.
---
# Diagnose before you fix

1. **Get a fast, reliable signal.** A failing test, a script, a query or a log filter that shows the problem on demand. If it is intermittent, find the conditions that make it reproducible. Without a signal, nothing that follows can be confirmed.
2. **Narrow the window.** What changed: commits, merged PRs, deploys, configuration, dependencies, data, traffic. `git log`, `git bisect` and deploy history usually halve the search faster than reading code.
3. **Form hypotheses and rank them.** List each plausible cause with the evidence for and against it. Test the cheapest discriminating one first.
4. **Prove the cause.** A cause is proven when changing it turns the signal on and off. Correlation in a log is a lead, not a cause.
5. **Record what you ruled out.** The alternatives eliminated, and how, belong in the write-up so nobody repeats them.

Redact secrets, tokens and personal data in anything you quote. Do not fix while diagnosing; a fix made before the cause is proven hides the evidence.
