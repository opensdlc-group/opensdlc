## What and why

<!-- What changes, and the problem it solves. Link the issue. -->

## Evidence

<!-- For skills, agents, template files or default settings: the eval cases you ran and, if it can change cost or quality across a ticket, `bench compare` before and after with 95% margins. Name the metric you expected to move. For code: the tests you added. -->

## Checks

- [ ] `PYTHONPATH=plugin/template/.opensdlc/cli python3 -m unittest discover -s tests`
- [ ] `python3 bench verify`, if the bench or a target changed
- [ ] actionlint on a copy of `plugin/template/.github`, if a template workflow changed
- [ ] Docs updated in this pull request, and `docs/evidence.md` if you measured a change
