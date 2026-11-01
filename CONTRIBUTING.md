# Contributing to OpenSDLC

Thanks for helping. Bug reports, questions, fixes, new bench scenarios and evidence from your own adoption are all welcome.

## Before you start

- **Bugs and small fixes:** open a pull request, or an issue if you're not sure it's a bug.
- **New features or changes to how a stage works:** open an issue first and describe the problem. A skill, hook or template change alters every adopting repository, so it is worth agreeing on the approach before you write it.
- **Security issues:** don't open an issue. Follow [SECURITY.md](SECURITY.md).

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up

You need Python 3.12 or later and git. The CLI, hooks and bench use the standard library only. To run the bench and the skill evals you also need [Claude Code](https://code.claude.com), and for the api and web bench targets, Node 22. Workflow linting needs [actionlint](https://github.com/rhysd/actionlint).

Check everything before you open a pull request:

```
PYTHONPATH=plugin/template/.opensdlc/cli python3 -m unittest discover -s tests
claude plugin validate .
claude plugin validate ./plugin
python3 bench verify
```

The template's workflows run in an adopting repository, so lint them from a copy:

```
lint=$(mktemp -d) && cp -R plugin/template/.github "$lint/" && (cd "$lint" && git init -q && actionlint)
```

## How changes are judged

OpenSDLC asks adopters to gate agent configuration changes on evals. It holds itself to the same rule.

- **Code** (CLI, hooks, bench, workflows) needs tests. The tests drive hooks through stdin exactly as Claude Code does, and `tests/test_workflows.py` holds every workflow to the security model. Keep them passing rather than loosening them.
- **Skills, agents, hooks' messages, template files and default settings** change what agents do, so they need evidence as well:
  - Run the skill evals for the skills you touched, with `--case '<skill>-*'` added to the command in [plugin/evals/README.md](plugin/evals/README.md).
  - For anything that can change cost or quality across a ticket, run the bench before and after with at least three runs each, then `python3 bench compare <before> <after>`. Say in the pull request which metric you expect to move before you run it, and report the 95% margins `compare` prints. A difference inside its margin is noise, not a result.
  - [docs/evidence.md](docs/evidence.md) records what earlier changes did. Add your result to it.

A change that makes no measurable difference can still be right, for example a security control, but say so and show it costs nothing measurable.

## Style

- **Code speaks for itself.** Name things so they don't need a comment, and comment only what the code can't say: why it is this way, a constraint it works around, or a source it follows. Small classes with one job, registries over conditionals, and no dead code.
- **Every source file starts with the licence header** the others carry: `Copyright <year> The OpenSDLC Authors` and `SPDX-License-Identifier: Apache-2.0`. A test checks it.
- **The CLI stays dependency-free.** It is copied into every adopting repository and runs with `python3 -P`.
- **Skills are short and conditional.** Say what to do interactively and what to do headless, and say why a rule exists when the reason changes behaviour. Every skill description is in the third person and says when to use it.
- **Docs change with the code**, in the same pull request. If you notice a doc that is wrong, fix it or delete it.

## Commits and pull requests

Write commit messages as a short imperative summary, then why the change is needed and the evidence for it. One logical change per pull request. The pull request template asks for the checks above.

## Licence

OpenSDLC is licensed under [Apache 2.0](LICENSE). By contributing you agree that your contribution is licensed under the same terms, as section 5 of the licence describes.
