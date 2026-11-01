# OpenSDLC bench

Builds the same product through OpenSDLC again and again, as different kinds of software, and scores each result with acceptance checks the agents never see. Use it to find out whether a change to OpenSDLC's skills, templates, hooks or settings makes the software better, cheaper or more reliable to build.

## How a run works

1. **A fresh repository.** It holds three things. The OpenSDLC template, adopted, without its example policy. The scenario's knowledge, shared by every target: a glossary, ADRs and policies, with the policies' skills generated. And the target's skeleton: its stack, a `Makefile` with `build`, `test` and `lint`, an `AGENTS.md` with a `CLAUDE.md` that imports it, and the product's interface as an architecture knowledge document.
2. **Each ticket goes through the stages the GitHub workflows run.** Claude Code runs headless with this repository's plugin and the CI sandbox settings. A scripted product owner stands in for the humans, so every run gets the same answers.

   | Stage | What runs | What the scripted product owner does |
   | :- | :- | :- |
   | intake | `/opensdlc:intent --ticket` | Files the ticket with the target's interface. If the agent escalates, re-files it with the scenario's answers. |
   | spec, plan | `/opensdlc:spec`, `/opensdlc:plan`, then `/opensdlc:gate` in its own session | Answers escalations from the agent or the gate. Accepts once `opensdlc check` passes, after at most one repair round. |
   | build | `/opensdlc:build`, then `/opensdlc:gate` in its own session, which verifies the build with the `verify` skill before it judges | – |
   | review | `/opensdlc:review` on the ticket's diff | – |
   | fix | Important findings go back to the agent, up to `--fix-rounds` | – |

   Every agent patch passes `opensdlc patch-check` before it lands, as in CI. A build nobody escalated marks its plan implemented, as the pipeline does, and once the ticket is built the scripted product owner signs it off and adds the ticket's surface to the interface knowledge document, which only people may edit. After the build, the run records CI (`make build`, `make test`, `make lint`), `plan-match`, `opensdlc check`, and whether the agent edited tests that already existed.
3. **After each ticket, every acceptance check so far runs against the built product.** A check that passed after one ticket and fails after a later one counts as a regression.

## Commands

From the repository root:

```
python3 bench list
python3 bench verify
python3 bench run --target cli --repeats 3
python3 bench run --target all --tickets 01,02 --max-cost 20 --keep
python3 bench report bench/results/<run folder>
python3 bench compare bench/results/<before> bench/results/<after>
```

- `verify` builds each target's reference implementation and proves it passes CI and every applicable check, without an agent. Run it after changing a check, an interface or an adapter.
- `run` writes `results/<time>-<scenario>/<target>/run-<n>.json` and `.md` for each run, plus a `summary.md` across them. `--keep` keeps each workspace so you can read what the agents wrote.
- `--model` picks the Claude model, `--max-turns` caps every stage, and `--max-cost` starts no new stage once a run has spent that many dollars. The stage already running finishes, so a run can pass the cap by up to one stage.
- Without `--model`, Claude Code uses its default model, which depends on the account it signs in with, and the cost of the same run can differ several times between models. Each result records what every model cost, and `compare` warns when the two sides ran on different models. Pin `--model` for runs you mean to compare.
- Each session starts the way CI starts it: with `.opensdlc/ci-settings.json`, the same `--allowedTools` and `--tools`, your user settings and skills ignored (`--setting-sources project,local`), and none of the calling session's `CLAUDE*` environment variables except `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN` and the `CLAUDE_CODE_USE_BEDROCK`, `_VERTEX` and `_FOUNDRY` provider switches. It also uses the 5-minute prompt cache Claude Code picks for an API key (`CLAUDE_CODE_PROMPT_CACHE_TTL=5m`) rather than the 1-hour cache it picks for a subscription, whose writes cost 2× the input price instead of 1.25×. Running the bench from inside Claude Code, or on a subscription, therefore costs what CI with an API key would.
- When an agent session fails or times out, or its stage hits a problem such as a refused patch or a missing review tally, its transcript is copied to `run-<n>-sessions/` beside the run's results. If the API refuses a session outright (credit, a usage limit, a subscription's 5-hour or weekly limit, or sign-in), the run stops there, no further runs start, and `report` and `compare` leave that run out. A session stopped by the 30-minute timeout reports no cost, so the run's cost leaves it out.

You need the `claude` CLI signed in, git, make, and Python 3.12 or later as `python3`: the bench launches the targets and the OpenSDLC CLI with the `python3` first on your PATH. The api and web targets also need Node 22, the web target needs Playwright with Chromium (`pip install playwright==1.63.0`, then `python3 -m playwright install --with-deps chromium`), and on Linux the sandbox needs `bubblewrap` and `socat`.

`run` and `verify` need Linux, macOS or WSL2: every agent runs in Claude Code's sandbox, which native Windows doesn't have, and the targets are driven through make and shell scripts. On Windows, use WSL2 and keep the repository in the Linux file system (`~/opensdlc`, not `/mnt/c/...`), where it is faster and file permissions survive. `list`, `report` and `compare` work anywhere.

Ubuntu 22.04 ships Python 3.10. Either install Ubuntu 24.04 (`wsl --install -d Ubuntu-24.04` on Windows), or add Python 3.12 and put a virtual environment first on your PATH, without touching the system's `python3`:

```
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.12 python3.12-venv
python3.12 -m venv ~/.venvs/bench
echo 'source ~/.venvs/bench/bin/activate' >> ~/.bashrc
```

## Improve OpenSDLC with it

1. Take a baseline: `run --repeats 3 --model <model>` on the targets you care about.
2. Change one thing: a skill, a template, a hook, a setting.
3. Run again with the same options.
4. `compare` the two folders. Keep the change if acceptance and regressions hold or improve and the metric you meant to move moves.

`compare` gives every difference a 95% margin, 1.96 standard errors of the difference between the two sets of runs, and calls it better or worse only outside that margin; everything else is within the noise between runs. Name the metric you expect to move before you run: with twenty metrics, one clears its margin by chance in most comparisons. Three runs a side resolve only large effects. Cost varies by about $0.30 to $0.70 a run on the todo scenario, so three runs detect a change of about 10%, and a 5% change needs about thirteen. For a change aimed at one stage, read the stage table, which treats each session as a sample and so has far more of them, or test the stage with the plugin's skill evals.

Each result records the OpenSDLC commit it ran, marked `+dirty` when the plugin had uncommitted changes.

## What it measures

| Metric | Why |
| :- | :- |
| Acceptance checks passing at the end | Did the software do what the tickets asked? |
| Checks that passed, then broke | Did later tickets break earlier work? |
| Tickets through every stage, and tickets the reviewer scored | Did the loop get stuck? Review counts mean nothing for tickets the reviewer never scored. |
| Cost, wall time, agent sessions and turns | What did it take? |
| Tickets that needed a person but did not escalate | Did the gates stop when only a person could decide? |
| Escalations on tickets that did not need one | Did the gates stop for nothing? |
| Patches refused by patch-check | How often did an agent write where it may not? |
| Artifacts that failed `opensdlc check` first time | Are the templates and skills easy to follow? |
| Tickets left with red CI | Did "done" mean verified? |
| Tickets whose code left the plan | Did the plan describe the work? |
| Tickets that edited existing tests | Did agents fix code, not tests? |
| Important review findings, and those left after fixes | How good was the first build, and did the fix loop work? |
| Repeated review findings | Is `AGENTS.md` learning? |
| Specs whose Concerns cite a policy, and review findings that cite one | Do the stages apply the knowledge base? Neither has a better direction: citing is right only when the change touches the policy. |

## Scenarios and targets

A scenario is a product built in tickets. Each of its targets is that product as one kind of software, with a pinned stack:

```
scenarios/<scenario>/
  scenario.json             name, description, ticket order, and the tickets that must escalate
  repository/               files every target's repository starts with: GLOSSARY.md, docs/adr/, knowledge/
  tickets/<id>.md           what the requester asks for, in their words
  answers/<id>.md           what the product owner says when an agent escalates, and nothing until it does
  acceptance/<id>.json      checks, written once for every target
  targets/<target>/
    target.json             stack, setup commands, extra build tools, and how the checks reach the product
    skeleton/               the repository before any ticket
    interface/<id>.md       the surface this ticket adds, in this target's terms; a ticket that must escalate leaves it out of its brief, and the product owner documents it once built
    reference/              a correct implementation of every ticket, for `verify`
    driver.py               web targets only: how each operation drives the page
```

The `todo` scenario has seven tickets: adding and listing, completing, deleting, a due-date change request, clearing done items, a request that contradicts itself, and a request to reuse deleted ids, which reads as reasonable on its own but reverses a decision the first ticket settled. Only the product owner can settle the last two, so they must escalate. The first shows its contradiction in its own text; the second only in the repository, where ADR 0001 and the public-contract policy record that ids are permanent, so it tests whether the stages act on what was already decided. Each answer names what to build instead, deliberately not the obvious name or design, and the checks expect exactly that, so a build that guessed instead of asking fails them. Each run's report says, for every ticket that escalated, which stage first raised it and whether the author or the gate did. Its targets are `cli` (Python), `library` (Python), `api` (TypeScript and Hono) and `web` (TypeScript, React and Vite).

### Checks

A check is a list of operations and the result each one should give. Operations name what the user does, never how a target does it:

```json
{"name": "a completed todo stays listed, shown as done", "steps": [
  {"op": "add", "args": {"title": "Buy milk"}, "as": "milk"},
  {"op": "complete", "args": {"id": "$milk.id"}, "expect": {"title": "Buy milk", "done": true}},
  {"op": "list", "expect": [{"title": "Buy milk", "done": true}]}
]}
```

An expected object matches when every key it names matches, and an expected list must match in length and order. `{"error": "invalid"}` and `{"error": "not_found"}` expect the target's error for bad input or an unknown id. `$milk.id` in arguments or expectations stands for the `id` of what the step saved `as` `milk` returned, and `{"unknown": "$milk.id"}` for an id that was never issued, of the same type as a real one. `distinct` asserts that values differ. `"except": ["web"]` skips a check a target cannot express, such as typing an impossible date into a date picker.

### Adapters

`target.json` maps each operation onto the target's surface, so a new product needs data, not code:

| Type | The product is | Operations map to |
| :- | :- | :- |
| `cli` | a command | argument lists, with optional groups such as `["--due", "{due}"]`; exit codes map to errors; each check gets a fresh state file |
| `http` | a server | method, path and body fields; status codes map to errors; each check gets a fresh server |
| `library` | an importable module | method calls on a fresh instance; exception classes map to errors |
| `web` | a page | functions in the target's `driver.py`, driven by Playwright; each check gets a fresh page |

### Adding a target or a scenario

1. Put knowledge every target shares in `repository/`: a glossary, ADRs and policies. They are examples of what an adopting team writes, not part of OpenSDLC.
2. Write the skeleton so `make build`, `make test` and `make lint` pass, and give it an `AGENTS.md`, a `CLAUDE.md` that imports it, and an interface knowledge document with `always: true`.
3. Write `interface/<ticket>.md` for every ticket and a reference implementation of all of them.
4. Map the operations in `target.json`, or in `driver.py` for a web target.
5. Run `verify` until the reference passes every check that applies.

## Limits

- The scripted product owner accepts whenever `opensdlc check` passes. Real reviewers catch more, so read the kept workspaces now and then.
- Every run calls the API and costs money. Five tickets on one target cost about $3 on the defaults; [docs/evidence.md](../docs/evidence.md) has the current figures. Start with `--tickets 01` on one target.
- Results vary between runs of the same commit. Use `--repeats`.
