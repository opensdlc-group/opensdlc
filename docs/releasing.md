# Releasing

Adopting repositories pin a release in `.opensdlc/config.json`, and every workflow checks out OpenSDLC at that tag. A release is therefore a tag that the template's own pin already names.

1. Run the full checks in [CONTRIBUTING.md](../CONTRIBUTING.md), the skill evals, and a bench run on every target. Add anything new to [evidence.md](evidence.md).
2. In one pull request, set the new version in `plugin/.claude-plugin/plugin.json`, the template's `plugin.ref` in `plugin/template/.opensdlc/config.json`, and the heading in `CHANGELOG.md`. `tests/test_plugin.py` fails if the three disagree.
3. After it merges, run the **Release** workflow on `main`. It packages the source as `opensdlc-<version>.tar.gz`, signs it with Sigstore, records its build provenance, and drafts release `v<version>` at that commit with the changelog entry and both files attached.
4. Read the draft and publish it. Publishing creates the tag, and releases are immutable, so the archive and its signature can't change afterwards. Anyone can check them with `gh attestation verify opensdlc-<version>.tar.gz --repo opensdlc-group/opensdlc`, or with `cosign verify-blob --bundle opensdlc-<version>.tar.gz.sigstore.json --certificate-identity-regexp '^https://github.com/opensdlc-group/opensdlc/' --certificate-oidc-issuer https://token.actions.githubusercontent.com opensdlc-<version>.tar.gz`.
5. Until 1.0, say in the changelog which defaults changed, so adopters can decide whether to move their pin.
