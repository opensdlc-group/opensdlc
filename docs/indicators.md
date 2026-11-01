# Indicators

The playbook gives every play a leading and a lagging indicator. OpenSDLC collects all 35 with `python3 -m opensdlc metrics`, and the `OpenSDLC indicators` workflow publishes them weekly to a pinned issue, comparing each with the previous window and, once `metrics.adoptedAt` is set, with the same span before adoption.

An indicator whose source is not configured reports what it needs instead of a number. Nothing is estimated.

## How the data gets there

Most indicators come from places your team already writes to: git history, pull requests, reviews, CI runs and deployments. OpenSDLC adds a few signals of its own so the rest can be computed deterministically:

| Signal | Written by | Feeds |
| :- | :- | :- |
| `started` in `intent.md` | `/opensdlc:intent`, and `/opensdlc:incident` from the breach time | Capture time |
| Pinned artifact chain and statuses in `changes/` | Every stage, `opensdlc pin` | Plan, Design and plan-mode indicators |
| `Files that change` in `plan.md` | `/opensdlc:plan` | Plan match |
| `<!-- opensdlc:review {...} -->` comment on each PR | `opensdlc-review.yml`, from the review tally | Repeat findings, policy findings, caught versus escaped |
| `<!-- opensdlc:breach {...} -->` in monitor PRs | `opensdlc-monitor.yml` | Breach to intent, findings to fixes |
| `incident` field in eval cases | `/opensdlc:learn` | Incident to eval |
| `opensdlc-evals` artifact per run | `opensdlc-evals.yml` | Eval pass rate, regressions caught |
| `Change: <id>` in a PR body | `/opensdlc:build` and the pipeline | Plan match, artifact-to-code links |
| `ref: #<issue>` in `intent.md`, `Closes #<issue>` on the build PR | `/opensdlc:intent`, `opensdlc-intake.yml`, the pipeline | Ticket proxies |

## Incidents

Incidents come from GitHub issues labelled `incident` by default, or from any command that prints the same fields. With issues, use labels and one body line:

- `found-in:production`, `found-in:ci`, `found-in:review` or `found-in:external`
- `class:<name>`, so repeats of the same class can be counted
- `regression`, `defect`, `security` or `gate-violation` where they apply
- `Caused-by: #<PR>` or `Caused-by: <deployed sha>` in the body

## Before and after adoption

Most indicators only exist once OpenSDLC does: there is no `intent.md` to time before anyone writes one. To show whether adopting it helped, set `metrics.adoptedAt` to the day you switched it on. Every row then gains a baseline column measured over the same number of days before that date, wherever the source existed then (pull requests, CI runs, deployments and incidents usually did).

Two tracker proxies cover the stages that had no artifact before adoption. They read issues carrying `metrics.baseline.issueLabel` (`feature` by default) and the pull requests that closed them, so they compare like with like across the adoption date:

| Indicator | Stage | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| Ticket opened to closed | Plan | lagging | days | down | `tickets` | `proxy.ticket-lead-time` |
| Ticket opened to first pull request | Design | leading | days | down | `tickets`, `prs` | `proxy.ticket-to-first-pr` |

## Sources that need your backend

Concurrent sessions and hook blocks come from Claude Code's OpenTelemetry export, and Claude Security findings from its exports. OpenSDLC does not assume a backend; configure a command that prints JSON:

```json
"metrics": {
  "otel": {
    "sessions": { "run": ["./scripts/otel-sessions.sh"] },
    "hookBlocks": { "run": ["./scripts/otel-hook-blocks.sh"] }
  },
  "security": {
    "findings": { "run": ["./scripts/security-findings.sh"] },
    "repositories": { "run": ["./scripts/security-repos.sh"] }
  },
  "gates": [{ "name": "release", "workflow": "deploy.yml", "job": "deploy-production" }],
  "team": { "new-joiner-login": "2026-09-01" }
}
```

- **sessions** prints `[{"user", "start", "end"}]`, one per Claude Code `session.id`, from its first and last event timestamps.
- **hookBlocks** prints the timestamps of `claude_code.tool_decision` events with `source` `hook` and `decision` `reject`.
- **findings** prints `[{"id", "reported", "scan", "patchPr"}]`; **repositories** prints `[{"name", "scheduled"}]`.
- **gates** names the job that waits on environment approval; the wait is the time between the job being created and starting.

## Catalog

### Plan

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| First conversation to committed intent.md | Capture as intent.md | leading | hours | down | `changes` | `plan.capture-time` |
| Intents accepted into Design | Capture as intent.md | lagging | share | up | `changes`, `prs` | `plan.survival-rate` |
| Intent edits after the first spec | Capture as intent.md | lagging | per change | down | `changes` | `plan.intent-edits-after-spec` |

### Design

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| Accepted intent to spec.md | Requirements and design | leading | hours | down | `changes` | `design.intent-to-spec` |
| Spec edits after the first plan | Requirements and design | lagging | per change | down | `changes` | `design.spec-rework-after-plan` |

### Build

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| Changes merged from the first implementation pass | Plan mode | leading | share | up | `prs` | `build.first-pass-merge` |
| Plan accepted to implementation merged | Plan mode | leading | hours | down | `changes` | `build.plan-to-merge` |
| Rework cycles per change | Plan mode | lagging | per PR | down | `prs` | `build.rework-cycles` |
| Merged diffs that match plan.md | Plan mode | lagging | share | up | `prs`, `changes` | `build.plan-match` |
| Repeated mistakes AGENTS.md should have caught | CLAUDE.md | leading | per reviewed PR | down | `prs`, `agents_md_commits` | `claudemd.repeat-findings` |
| New joiner's time to first merged PR | CLAUDE.md | lagging | days | down | `prs`, `team` | `claudemd.new-joiner-first-merge` |
| Skill change opened to merged | Skills as institutional knowledge | leading | hours | down | `prs` | `skills.policy-to-skill` |
| Review findings that cite a policy | Skills as institutional knowledge | lagging | per reviewed PR | down | `prs` | `skills.policy-findings` |
| Concurrent sessions per engineer | Parallel sessions and subagents | leading | sessions | up | `sessions` | `parallel.concurrent-sessions` |
| Changes merged per engineer per week | Parallel sessions and subagents | lagging | per week | up | `prs` | `parallel.throughput` |

### Test

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| Agent changes green on first CI run | Feedback loop | leading | share | up | `prs`, `runs` | `test.first-pass-ci` |
| PR opened to approved | Feedback loop | lagging | hours | down | `prs` | `test.review-time` |
| Merged changes that caused an incident | Feedback loop | lagging | share | down | `prs`, `incidents` | `test.change-failure-rate` |
| Eval pass rate | Continuous evals | leading | share | up | `eval_runs` | `evals.pass-rate` |
| Incident opened to permanent eval | Continuous evals | leading | days | down | `eval_cases`, `incidents` | `evals.incident-to-eval` |
| Regressions caught in CI rather than production | Continuous evals | lagging | share | up | `eval_runs`, `incidents` | `evals.regressions-caught` |

### Deploy

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| PR opened to first review | AI in the PR review loop | leading | minutes | down | `prs` | `review.time-to-first-review` |
| Review comments resolved without a human touching the branch | AI in the PR review loop | leading | share | up | `prs` | `review.agent-resolved` |
| Defects caught before merge rather than in production | AI in the PR review loop | lagging | share | up | `prs`, `incidents` | `review.caught-vs-escaped` |
| Time waiting on approval gates | Hooks as approval gates | leading | minutes | down | `gate_waits` | `gates.wait` |
| Gate violations reaching production | Hooks as approval gates | lagging | count | down | `incidents` | `gates.violations` |
| CI failures triaged by Claude | CI/CD integration | leading | share | up | `runs` | `cicd.failures-triaged` |
| DORA: deploys per week | CI/CD integration | lagging | per week | up | `deployments`, `incidents` | `cicd.dora` |

### Maintain

| Indicator | Play | Kind | Unit | Better | Needs | ID |
| :- | :- | :- | :- | :- | :- | :- |
| Band breach to intent.md in the triage queue | Closing the loop | leading | minutes | down | `prs` | `maintain.breach-to-intent` |
| Monitor findings that became merged fixes | Closing the loop | lagging | share | up | `prs`, `changes` | `maintain.findings-to-fixes` |
| Repeat incidents of the same class | Closing the loop | lagging | count | down | `incidents` | `maintain.repeat-incidents` |
| Repositories on a scan schedule | Recurring codebase scans | leading | share | up | `security_repos` | `security.scan-coverage` |
| Finding reported to patch in the review gate | Recurring codebase scans | leading | hours | down | `security_findings`, `prs` | `security.finding-to-patch` |
| Vulnerabilities found by scans rather than production | Recurring codebase scans | lagging | share | up | `security_findings`, `incidents` | `security.scan-vs-production` |
| Findings per scan | Recurring codebase scans | lagging | per scan | down | `security_findings` | `security.findings-per-scan` |

## Sources

| Source | Where it comes from |
| :- | :- |
| `changes` | git history of changes/ |
| `agents_md_commits` | git history of AGENTS.md and CLAUDE.md |
| `prs` | GitHub pull requests through the gh CLI |
| `runs` | GitHub Actions runs through the gh CLI |
| `gate_waits` | metrics.gates: the workflow and job that wait on release approval |
| `deployments` | GitHub deployments to metrics.deployEnvironment |
| `incidents` | metrics.incidents: {"type": "github-issues"} or a command printing incidents |
| `eval_runs` | runs of the OpenSDLC evals workflow |
| `eval_cases` | evals/cases with an incident field |
| `sessions` | metrics.otel.sessions: a command printing [{user, start, end}] from your OpenTelemetry backend |
| `hook_blocks` | metrics.otel.hookBlocks: a command printing the times of claude_code.tool_decision events with source=hook, decision=reject |
| `security_findings` | metrics.security.findings: a command printing [{id, reported, scan, patchPr}] from Claude Security exports |
| `security_repos` | metrics.security.repositories: a command printing [{name, scheduled}] |
| `team` | metrics.team: join dates for team members |
| `tickets` | metrics.baseline.issueLabel: the label your tracker puts on feature tickets |
