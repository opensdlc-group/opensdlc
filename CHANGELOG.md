# Changelog

OpenSDLC follows [Semantic Versioning](https://semver.org). Until 1.0, a minor version can change how a stage behaves; read the notes before you move your pin.

## 0.6.0 (2026-11-10)

The first public release.

### Added

- A Claude Code plugin with stage skills (`intent`, `spec`, `plan`, `build`, `repro`, `review`, `shepherd`, `incident`, `learn`, `adopt`), practice skills, the `gate` and `verify` judgement skills, three agents, and guardrail and approval hooks.
- A repository template with the artifact chain, owned knowledge, a dependency-free CLI and GitHub workflows from intake to monitoring, installed with `/opensdlc:adopt`.
- A claude.ai skill for capturing an intent outside Claude Code.
- All 35 of the playbook's leading and lagging indicators through `opensdlc metrics`.
- A skill eval suite (`plugin/evals/`) and a benchmark (`bench/`) that builds one product as a CLI, a library, an HTTP API and a web app, with 95% margins on every comparison.
- The OpenSDLC logo, icon, social preview and brand guide in `brand/`.

### Defaults, and the evidence for them

- One gate session verifies a build and then judges it.
- Every headless session is offered only the tools its rules name, Claude Code's bundled skills are off in CI, and sandboxed Bash runs only the commands a job's rules name.
- Build runs on Haiku 5.5; every other stage and every judge runs on the default model.
- CI loads the plugin at the release `.opensdlc/config.json` pins, never whatever the marketplace holds.
- Every third-party action in the template is pinned to a commit, and the template ships a Dependabot configuration to keep the pins current.

[docs/evidence.md](docs/evidence.md) records what each default did on the bench.
