# Evidence behind the defaults

OpenSDLC's defaults were each measured with the [bench](../bench/README.md) before they were kept. This page records what each change did, so you can see why a default is what it is and what a new change has to beat.

## How these were measured

- **Runs:** three per arm on the todo scenario, tickets 01, 02, 03, 06 and 07. Tickets 06 and 07 need a person, the rest don't. The default model is Sonnet 5.5.
- **Noise:** a change counts as better or worse only when it is larger than its 95% margin, 1.96 standard errors of the difference between the two arms, following [Miller, *Adding Error Bars to Evals* (2024)](https://arxiv.org/abs/2411.00640). Each margin below is that figure. Three runs per arm resolve about a 10% change in cost; smaller effects need more runs.
- **Sessions start the way CI starts them:** with the template's settings, the same tool rules, no user skills or settings, and the 5-minute prompt cache an API key gets. Costs are what CI with an API key pays.

## Changes kept

| Change | What moved | Result |
| :- | :- | :- |
| An ADR and an owned policy in the scenario's knowledge | Acceptance; tickets that needed a person but didn't escalate | 81% → 100%; missed escalations went to 0 |
| Specs cite a policy only where its owner has to decide | Specs whose concerns cite a policy, per run | 4.3 → 0 |
| The gate checks in code what needs no judgement | Cost and quality | Within noise; kept because detection should be deterministic |
| One gate session verifies a build, then judges it | Cost of judging a build | $0.40 → $0.25 (−$0.155 ± $0.020) |
| Each session is offered only the tools its rules name, without Claude Code's bundled skills | Cost per session | Gate −$0.017 ± $0.013; intake −$0.038 ± $0.012 |
| Build runs on Haiku 5.5; intake, spec, plan and every judge stay on the default model | Cost per run; escalations on tickets that needed none | $4.08 → $3.28 (−$0.80 ± $0.45); 0.3 → 0 |
| Sandboxed Bash runs only commands a job's rules name, with the single-test command named in `AGENTS.md` | Cost per run | +$0.20 ± $0.23, within noise; kept because the rules should mean what they say |
| Review leaves building and testing to CI | Refused `make test` and `make build` calls | 5 → 0; cost unchanged |
| Verify exercises a running app with one command, and the api target starts without a Unix socket | Escalations on api tickets that needed none, per run | 3.7 → 1.3 (−2.3 ± 2.9) |
| `review.nitCap` is the only nit cap; `REVIEW.md` no longer repeats it as "five" | Cost per review; nits per run | $0.097 → $0.092 (−$0.005 ± $0.009), within noise; 11.3 → 9, never more than 4 in a review |
| The api and web targets move to vitest 5 and `@hono/node-server` 2, which fix 11 known vulnerabilities | Cost per run; acceptance | Acceptance stayed 100%. Cost within noise on api ($3.15 → $3.02, −$0.12 ± $0.37) and web ($2.78 → $2.83, +$0.05 ± $0.29), and in every stage. The runs alternated between versions, three per target each, because an earlier sequential comparison showed a rise that came from API conditions: time per turn rose in stages that never touch the new packages. |

## Changes rejected

| Change | Why |
| :- | :- |
| Plan on Haiku as well as build | Escalations on tickets that needed none rose 0.3 → 2.7 (+2.3 ± 0.9). The gate was right each time: Haiku plans settled questions the spec left open or departed from it. |
| An evidence file handed to the gate | In the gate evals it took fewer turns, but each session cost more ($0.099 → $0.104). |
| Strict sandboxed Bash without the single-test command | +$0.28 ± $0.21 per run: builds were refused `python3 -m unittest <file>` 17 times. |

## Where it stands

At the current release every target passes every acceptance check on every run:

| Target | Cost per run |
| :- | -: |
| cli | $3.35 |
| api | $2.90 |
| library | $2.83 |
| web | $2.77 |

The bench is one small product in four stacks. Treat these as evidence that a change helps or hurts, not as what your repository will cost.
