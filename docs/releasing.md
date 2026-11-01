# Releasing

Adopting repositories pin a release in `.opensdlc/config.json`, and every workflow checks out OpenSDLC at that tag. A release is therefore a tag that the template's own pin already names.

1. Run the full checks in [CONTRIBUTING.md](../CONTRIBUTING.md), the skill evals, and a bench run on every target. Add anything new to [evidence.md](evidence.md).
2. In one pull request, set the new version in `plugin/.claude-plugin/plugin.json`, the template's `plugin.ref` in `plugin/template/.opensdlc/config.json`, and the heading in `CHANGELOG.md`. `tests/test_plugin.py` fails if the three disagree.
3. After it merges, tag the merge commit `v<version>` and publish a GitHub release with the changelog entry.
4. Until 1.0, say in the changelog which defaults changed, so adopters can decide whether to move their pin.
