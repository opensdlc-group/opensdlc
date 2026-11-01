# How OpenSDLC maps to the AI-native SDLC playbook

OpenSDLC is an independent, open-source implementation of the stage-by-stage process in Anthropic's [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). It is not affiliated with or endorsed by Anthropic. This table shows where each play lives.

| Stage | Play | OpenSDLC |
| :- | :- | :- |
| Plan | Capture as `intent.md` | `/opensdlc:intent` skill and template; the claude.ai skill for non-engineers; `opensdlc-intake.yml` drafts one from a ticket labelled `intent` and links it back; a product owner accepts it by approving the PR that proposes `status: accepted` |
| Design | Requirements and design in one pass | `/opensdlc:spec`, run automatically on an accepted intent by `opensdlc-advance.yml`; reads the policies, architecture and domain documents `opensdlc context` selects, cites them in Concerns, and needs each cited policy owner's approval |
| Build | Plan mode as the starting point | `/opensdlc:plan` with a `risk` tier and "Files that change"; drafted automatically on an accepted spec for the engineer to refine; `plan-match` holds the code PR to it |
| Build | `CLAUDE.md` | Template `AGENTS.md`, imported by a one-line `CLAUDE.md`, with Commands, Verifying and "Things agents get wrong"; `/opensdlc:learn` and repeat review findings suggest new rules |
| Build | Skills as institutional knowledge | Stage skills ship in the plugin; policies in `knowledge/` with `skill` generate `.claude/skills/<skill>/SKILL.md`, kept current by `check`; shared policies sync in from one organization repository |
| Build | Hooks as build-time guardrails | Plugin hooks: protected paths, `.env` and frozen tests for file tools and shell writes alike, secrets in edits, formatter on edit, verify-before-done on Stop |
| Build | Parallel sessions and subagents | `verifier`, `simplifier` and `researcher` agents; the review keeps its three axes apart in one session and hands one to a sub-agent only when the diff is too large to hold |
| Build | Auto mode for routine work | `stages.build.autoRisk`: accepted plans at that risk build headlessly, read-only and sandboxed, into a PR |
| Test | Feedback loop | `AGENTS.md` Verifying; the Stop hook blocks "done" until `verify.commands` pass after the last edit; `/opensdlc:repro` with a hook-enforced test freeze |
| Test | Continuous evals in CI | `evals/cases/*.json` run several times each by `opensdlc-evals.yml`, failing on a drop against main's last run, overall or per case |
| Deploy | AI in the PR review loop | `REVIEW.md` and `/opensdlc:review` on three axes with the change's policies; keyed findings flag repeats and suggest `AGENTS.md` rules; reactions rate precision monthly; `@claude` fix loop; `/opensdlc:shepherd` |
| Deploy | Hooks as approval gates | Per-environment autonomy: development free, staging asks, production needs `RELEASE_APPROVAL`; managed settings example |
| Deploy | CI/CD integration | Agent jobs read-only and sandboxed, writes applied by a separate job after `patch-check`; `opensdlc-checks` and `opensdlc-approvals` judged by the base branch's rules; deterministic secret, dependency and static-analysis scans |
| Maintain | Closing the loop | `python3 -m opensdlc monitor`: deterministic Western Electric bands, tiered `log` / `diagnose` / `propose`, `/opensdlc:incident` writes `intent.md`, a pre-approved `production-rollback` runbook rehearsed weekly against staging |
| Maintain | Confidence gate between stages | `gate` skill, run by the pipeline in a session of its own after every headless spec, plan and build, verifying a build with the `verify` skill before it judges; `opensdlc gate-check` reads its verdict, fails closed, and checks in code what needs no judgement (verification passed, existing tests changed only where the plan lists them, every concern settled), and an escalation keeps the artifact in draft and labels the PR `needs-human` |
| Maintain | Incidents become evals | `/opensdlc:learn` writes an eval case per incident or fixed vulnerability |
| All | How to measure it | All 35 leading and lagging indicators through `python3 -m opensdlc metrics` and the weekly `OpenSDLC indicators` issue, each compared with the window before and, with `metrics.adoptedAt`, the period before adoption; see [indicators.md](indicators.md) |

## Not covered

- **Claude Security** and **Claude Tag** are hosted products. OpenSDLC's `incident` skill accepts their findings the same way it accepts a breached band, and `/opensdlc:learn` turns fixes into evals.
- **Managed settings** are deployed by your platform team through MDM or the admin console. [managed-settings.example.json](managed-settings.example.json) is a starting point that force-enables the OpenSDLC plugin so its hooks survive `allowManagedHooksOnly`.
