# OpenSDLC skill evals

Each case runs one skill once, headless, the way the pipeline runs it, against a small repository: the todo app from the bench after its first three tickets, with the bench's glossary, ADR and public-contract policy. The cases check what the bench can only see at the end of a whole run, such as whether a stage escalates a request that breaks an ADR, for cents a run instead of dollars.

| Case | Skill | Passes when |
| :- | :- | :- |
| `intent-escalates-a-self-contradicting-ticket` | intent | it writes `escalate.md` about the contradiction |
| `intent-escalates-a-ticket-that-breaks-an-adr` | intent | it writes `escalate.md` about ADR 0001 |
| `intent-triggers-on-a-plain-request` | intent | asked in plain words, Claude picks the intent skill and writes an intent |
| `spec-escalates-an-intent-that-breaks-an-adr` | spec | it writes `escalate.md` about ADR 0001 |
| `spec-escalates-a-quiet-intent-that-breaks-an-adr` | spec | it finds ADR 0001 on its own, in an accepted intent that never mentions it, and escalates |
| `spec-settles-a-change-request` | spec | for a change request whose open questions the product owner already answered, it writes the spec, escalates nothing, and says of every Concern whether it is resolved, carried or escalated |
| `spec-cites-no-policy-for-an-addition` | spec | it writes the spec for a purely additive ticket without citing the policy, so the policy owner is not asked to approve it |
| `spec-triggers-on-a-plain-request` | spec | asked in plain words, Claude picks the spec skill and writes the spec |
| `plan-turns-an-accepted-spec-into-a-plan` | plan | it writes a plan that names the code it changes and proves the work with `make test` |
| `build-implements-the-plan-and-leaves-old-tests-alone` | build | it adds the command, runs the tests, edits no test that already existed, and leaves the plan for the pipeline to mark implemented |
| `review-flags-a-change-that-breaks-an-adr` | review | it raises an Important finding on a green PR that reuses deleted ids and rewrites the tests that guarded ADR 0001 |
| `review-passes-a-clean-change` | review | it raises nothing Important on a green PR that implements an accepted plan |
| `review-triggers-on-a-plain-request` | review | asked in plain words, Claude picks the review skill and writes the tally |
| `verify-passes-a-working-build` | verify | its report starts with `PASS` |
| `verify-fails-a-broken-build` | verify | its report starts with `FAIL` and names the failing tests of a build that breaks them |
| `gate-continues-on-a-settled-spec` | gate | its verdict is `continue` |
| `gate-escalates-a-resolution-the-spec-does-not-record` | gate | its verdict is `escalate` for the same spec with one concern marked resolved whose decision the spec never records, which the code checks cannot see |

## Running

From the repository root:

```
claude plugin eval plugin --scaffold --ablation none --trust-plugin \
  --allow-tools Write Edit "Bash(git diff:*)" "Bash(git status:*)" "Bash(git log:*)" \
  "Bash(make build)" "Bash(make test)" "Bash(make lint)" "Bash(./todo:*)" "Bash(TODO_FILE=* ./todo *)"
```

- `--scaffold` lets each case build its repository. The scaffolds copy files and make git commits, nothing else.
- `--ablation none` skips the run without the plugin: the prompts invoke the plugin's skills the way the pipeline does, so a run without it has nothing to compare.
- `--allow-tools` grants what the pipeline grants these stages. Evals allow only read-only tools unless the command line grants more.
- The harness runs each case in its own sandbox, and refuses to grant Bash where it cannot keep credential stores out of reach. Where it cannot run a case, run the case's prompt with `claude -p` in a repository built by its `fixture.sh`, with the same tools allowed, and check the output against the case's grader by hand.
- Add `--case '<glob>'` to run some cases, and `--runs 1` for a quick look. Each case runs on Sonnet three times by default; `--model haiku` or `--model opus` runs the same suite on another model, which the skill authoring guidance asks for before a skill ships.

The bench says whether a change to the skills makes the software better. These cases say, quickly, whether a change to one skill does what it was meant to, so run them first and spend a bench batch only on a change that passes.
