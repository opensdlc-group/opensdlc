# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from fnmatch import fnmatch
from pathlib import Path
from unittest import mock

from support import BENCH, TEMPLATE
from test_artifacts import filled

from opensdlc_bench import cli
from opensdlc_bench.acceptance import CheckRunner, matches, resolve, run_checks
from opensdlc_bench.adapters import adapter_for
from opensdlc_bench.agent import Agent, AgentRun, AgentUnavailable, ClaudeCode
from opensdlc_bench.model import Scenario, Target
from opensdlc_bench.pipeline import BenchRun, RunRecord, TicketRecord
from opensdlc_bench.report import Difference, compare_markdown, run_markdown, suite_markdown, summary
from opensdlc_bench.stages import INTAKE_TOOLS, REVIEW_TOOLS, BuildStage, Context, Settings, StageRecord
from opensdlc_bench.verify import verify_reference
from opensdlc_bench.workspace import SANDBOX_PLACEHOLDERS, Workspace

CHANGE = re.compile(r"changes/([a-z0-9-]+)")


class ScriptedAgent(Agent):
    def __init__(self, target: Target, escalate_spec: bool = False, important: int = 0, rogue_build: bool = False, gate: str = "continue",
                 cite_policy: bool = False):
        self.target = target
        self.escalate_spec = escalate_spec
        self.cite_policy = cite_policy
        self.gate = gate
        self.important = important
        self.rogue_build = rogue_build
        self.prompts: list[str] = []
        self.models: list[str] = []

    def run(self, prompt, cwd, tools, max_turns, model=""):
        self.prompts.append(prompt)
        self.models.append(model)
        change = CHANGE.search(prompt).group(1) if CHANGE.search(prompt) else None
        if prompt.startswith("/opensdlc:intent"):
            number = re.search(r"# Ticket #(\d+)", (cwd / ".opensdlc/out/ticket.md").read_text()).group(1)
            self.write(cwd / "changes" / f"2026-10-ticket-{number}" / "intent.md", filled("intent", "draft"))
        elif prompt.startswith("/opensdlc:spec"):
            spec = filled("spec", "draft")
            if self.cite_policy:
                spec = spec.replace("## Concerns\nReal content.", "## Concerns\n- **Reuses ids** (policy: public-contract): breaks ADR 0001. **Escalated.**")
            self.write(cwd / "changes" / change / "spec.md", spec)
            if self.escalate_spec and "(write" in prompt:
                self.write(cwd / ".opensdlc/out/escalate.md", "Which storage?")
        elif prompt.startswith("/opensdlc:plan"):
            files = "\n".join(f"- `{p.relative_to(self.target.reference)}`: implement" for p in self.target.reference.rglob("*") if p.is_file())
            plan = filled("plan", "draft").replace("## Files that change\nReal content.", f"## Files that change\n{files}")
            self.write(cwd / "changes" / change / "plan.md", plan)
        elif prompt.startswith("/opensdlc:build"):
            shutil.copytree(self.target.reference, cwd, dirs_exist_ok=True)
            if self.rogue_build:
                self.write(cwd / ".github" / "workflows" / "steal.yml", "on: push")
        elif prompt.startswith("/opensdlc:gate"):
            if prompt.endswith(" build (headless)"):
                self.write(cwd / ".opensdlc/out/verify.md", "PASS\n")
                (cwd / "scratch.txt").write_text("left behind by verification")
            reasons = ["The spec picks a behaviour the intent leaves open."] if self.gate == "escalate" and " spec " in prompt else []
            self.write(cwd / ".opensdlc/out/gate.json", json.dumps({"verdict": "escalate" if reasons else "continue", "reasons": reasons}))
        elif prompt.startswith("/opensdlc:review"):
            findings = [{"axis": "spec", "severity": "important", "key": "missing-check", "file": "src/x.py", "line": 1, "summary": "gap"}] * self.important
            self.important = 0
            self.write(cwd / ".opensdlc/out/review.json", json.dumps({"findings": findings + [{"axis": "standards", "severity": "nit", "key": "naming", "file": "src/x.py", "line": 2, "summary": "name"}]}))
        return AgentRun(prompt, True, cost=0.01, turns=3, seconds=0.1)

    @staticmethod
    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class CutOffAgent(ScriptedAgent):
    def __init__(self, target: Target, answers: int):
        super().__init__(target)
        self.answers = answers

    def run(self, prompt, cwd, tools, max_turns, model=""):
        if len(self.prompts) == self.answers:
            raise AgentUnavailable("API Error: 400 You have reached your specified workspace API usage limits.")
        return super().run(prompt, cwd, tools, max_turns, model)


def run(target: str, agent_options: dict | None = None, tickets: str = "01,02", max_cost: float | None = None) -> tuple[dict, ScriptedAgent]:
    scenario = Scenario.load("todo")
    target_ = scenario.target(target)
    agent = ScriptedAgent(target_, **(agent_options or {}))
    record = BenchRun(scenario, target_, scenario.select(tickets.split(",")), agent, Settings(), max_cost=max_cost).execute()
    return json.loads(json.dumps(record.as_json(), default=str)), agent


class Scenarios(unittest.TestCase):
    def test_every_target_documents_every_ticket_but_only_briefs_the_ones_that_need_not_escalate(self):
        scenario = Scenario.load("todo")
        for target in scenario.targets([]):
            for ticket in scenario.tickets:
                surface = target.interface(ticket).strip()
                self.assertTrue(surface, f"{target.name}: {ticket.id}")
                self.assertEqual(surface in target.brief(ticket, 1), not ticket.must_escalate, f"{target.name}: {ticket.id}")

    def test_only_the_product_owner_can_settle_a_ticket_that_must_escalate(self):
        scenario = Scenario.load("todo")
        settled = [t for t in scenario.tickets if t.must_escalate]
        self.assertEqual([t.id for t in settled], ["06-hide-done", "07-small-ids"])
        for ticket, answer in zip(settled, ("--remaining", "position")):
            brief = scenario.target("cli").brief(ticket, 6)
            self.assertNotIn("## Interface", brief)
            self.assertNotIn(answer, brief)
            self.assertIn(answer, ticket.answers)

    def test_a_brief_carries_the_ticket_and_the_targets_interface(self):
        scenario = Scenario.load("todo")
        target = scenario.target("api")
        brief = target.brief(scenario.tickets[1], 2)
        self.assertTrue(brief.startswith("# Ticket #2: Tick todos off"))
        self.assertIn("POST /todos/:id/complete", brief)

    def test_every_skeleton_keeps_the_templates_verifying_section(self):
        section = re.search(r"## Verifying your work\n(.*?)\n\n", (TEMPLATE / "AGENTS.md").read_text(), re.S).group(1)
        for target in Scenario.load("todo").targets([]):
            self.assertIn(section, (target.skeleton / "AGENTS.md").read_text(), target.name)

    def test_the_command_each_agents_md_says_to_try_by_hand_is_one_the_build_stage_allows(self):
        commands = 0
        for target in Scenario.load("todo").targets([]):
            for command in re.findall(r"by hand.*`([^`]+)`$", (target.skeleton / "AGENTS.md").read_text(), re.M):
                commands += 1
                self.assertTrue(any(fnmatch(f"Bash({command})", rule) for rule in target.build_tools.split(",")), f"{target.name}: {command}")
        self.assertGreaterEqual(commands, 2)

    def test_the_bench_runs_the_same_tools_as_the_workflows(self):
        workflows = TEMPLATE / ".github" / "workflows"
        self.assertIn(INTAKE_TOOLS, (workflows / "opensdlc-intake.yml").read_text())
        self.assertIn(REVIEW_TOOLS, (workflows / "opensdlc-review.yml").read_text())


class Matching(unittest.TestCase):
    def test_expectations_are_subsets_and_lists_are_exact(self):
        self.assertTrue(matches({"title": "a"}, {"title": "a", "id": 1}))
        self.assertFalse(matches([{"title": "a"}], [{"title": "a"}, {"title": "b"}]))
        self.assertFalse(matches({"done": True}, {"done": 1}))
        self.assertTrue(matches({"due": None}, {"due": None}))

    def test_an_unknown_id_has_the_same_shape_as_a_real_one(self):
        for real, unknown in ((7, 1_000_006), ("7", "1000006"), ("a1b2", "a1b2-unknown")):
            self.assertEqual(resolve({"id": {"unknown": "$todo.id"}}, {"todo": {"id": real}}), {"id": unknown})


class References(unittest.TestCase):
    def test_the_python_references_pass_every_check(self):
        scenario = Scenario.load("todo")
        for name in ("cli", "library"):
            result = verify_reference(scenario, scenario.target(name))
            self.assertTrue(result.ok, [(c.key, c.detail) for c in result.checks if c.status == "fail"])

    def test_a_broken_implementation_fails_the_checks_that_cover_it(self):
        scenario = Scenario.load("todo")
        target = scenario.target("library")
        with tempfile.TemporaryDirectory() as scratch:
            broken = Path(scratch) / "broken"
            shutil.copytree(target.reference, broken)
            source = broken / "src" / "todo" / "todos.py"
            source.write_text(source.read_text().replace("title = raw.strip()", "title = raw").replace('(t.due is None, t.due or "")', "t.id"))
            workspace = Workspace.create(target, Path(scratch) / "work", overlay=broken)
            results = run_checks(adapter_for(target.adapter, target.root, workspace.root), target.name, [c for t in scenario.tickets for c in t.checks])
        failed = {r.key for r in results if r.status == "fail"}
        self.assertEqual(failed, {
            "01-add-and-list: spaces at either end of a title are dropped",
            "01-add-and-list: an empty title is rejected and nothing is saved",
            "04-due-dates: dated todos come first, earliest first, ties in the order added",
        })

    def test_checks_a_target_cannot_express_are_skipped(self):
        check = next(c for c in Scenario.load("todo").tickets[1].checks if c.excluded)
        self.assertEqual(CheckRunner(None, "web").run(check).status, "skip")


class Pipeline(unittest.TestCase):
    def test_every_target_maps_every_operation_the_checks_use(self):
        scenario = Scenario.load("todo")
        used = {s["op"] for t in scenario.tickets for c in t.checks for s in c.steps} - {"distinct"}
        for target in scenario.targets([]):
            mapped = set(target.adapter["ops"]) if "ops" in target.adapter else set(adapter_for(target.adapter, target.root, target.root).driver.OPS)
            self.assertEqual(mapped, used, target.name)

    def test_each_session_runs_on_the_model_its_stage_names(self):
        configure = Workspace.configure

        def a_model_per_stage(workspace, target):
            configure(workspace, target)
            path = workspace.root / ".opensdlc" / "config.json"
            config = json.loads(path.read_text())
            for name, stage in config["stages"].items():
                stage["model"] = f"{name}-model"
            path.write_text(json.dumps(config))

        with mock.patch.object(Workspace, "configure", a_model_per_stage):
            _, agent = run("cli", tickets="01")
        chosen = {(prompt.split()[0], model) for prompt, model in zip(agent.prompts, agent.models)}
        self.assertEqual(chosen, {("/opensdlc:intent", ""), ("/opensdlc:spec", "spec-model"), ("/opensdlc:plan", "plan-model"),
                                  ("/opensdlc:build", "build-model"), ("/opensdlc:gate", "gate-model"), ("/opensdlc:review", "")})

    def test_a_ticket_goes_through_every_stage_and_is_scored(self):
        data, agent = run("cli", {"escalate_spec": True, "important": 1})
        self.assertEqual(data["error"], "")
        first = data["tickets"][0]
        self.assertEqual([s["stage"] for s in first["stages"]], ["intake", "spec", "plan", "build", "review", "fix", "review"])
        spec = first["stages"][1]
        self.assertEqual((spec["status"], spec["notes"]["escalations"], spec["notes"]["gate"], len(spec["runs"])), ("ok", 1, "continue", 3))
        self.assertEqual([r["prompt"].split()[0] for r in first["stages"][3]["runs"]], ["/opensdlc:build", "/opensdlc:gate"])
        build = first["stages"][3]
        self.assertTrue(all(build["notes"]["ci"].values()))
        self.assertTrue(build["notes"]["planMatch"])
        self.assertEqual(build["notes"]["existingTestsChanged"], [])
        s = summary(data)
        self.assertEqual((s["acceptance"], s["ticketsCompleted"], s["importantFound"], s["importantLeft"], s["regressions"]), (1.0, 2, 1, 0, 0))
        self.assertIn("(revise, headless). It was escalated: .opensdlc/out/answers.md has what was raised", " ".join(agent.prompts))
        self.assertIn("| 01-add-and-list |", run_markdown(data))

    def test_a_finished_ticket_is_implemented_and_added_to_the_interface(self):
        scenario = Scenario.load("todo")
        target = scenario.target("cli")
        record = BenchRun(scenario, target, scenario.select(["01"]), ScriptedAgent(target), Settings(), keep=True).execute()
        try:
            root = Path(record.workspace)
            self.assertIn("status: implemented", (root / "changes" / record.tickets[0].change / "plan.md").read_text())
            self.assertIn("## Keep a list of things to do\n\n- ", (root / "knowledge/architecture/interface.md").read_text())
            workspace = Workspace(root)
            self.assertEqual(workspace.git("status", "--porcelain"), "")
            self.assertTrue(workspace.opensdlc("check").ok, workspace.opensdlc("check").output)
        finally:
            shutil.rmtree(Path(record.workspace).parent, ignore_errors=True)

    def test_a_gate_that_escalates_sends_the_draft_back_with_the_product_owners_answers(self):
        data, agent = run("cli", {"gate": "escalate"}, tickets="01")
        spec = data["tickets"][0]["stages"][1]
        self.assertEqual((spec["status"], spec["notes"]["escalations"], spec["notes"]["gateEscalations"]), ("escalated", 1, 2))
        self.assertIn("It was escalated: .opensdlc/out/answers.md", " ".join(agent.prompts))
        self.assertEqual(summary(data)["unneededEscalations"], 2)
        self.assertIn("| 01-add-and-list | ✓ | ⚠ gate |", run_markdown(data))
        self.assertIn("- 01-add-and-list: spec, by the gate 1/1", suite_markdown({"cli": [data]}))

    def test_escalations_are_scored_as_missed_or_unneeded(self):
        silent, _ = run("cli", tickets="01,06")
        asking, _ = run("cli", {"escalate_spec": True}, tickets="01,06")
        self.assertEqual((summary(silent)["missedEscalations"], summary(silent)["unneededEscalations"]), (1, 0))
        self.assertEqual((summary(asking)["missedEscalations"], summary(asking)["unneededEscalations"]), (0, 1))
        self.assertIn("| 06-hide-done (must escalate) | ✓ | ⚠✓ |", run_markdown(asking))
        self.assertIn("- 06-hide-done (must escalate): spec, by the author 1/1", run_markdown(asking))
        self.assertIn("- 06-hide-done (must escalate): not escalated 1/1", run_markdown(silent))
        self.assertNotIn("- 01-add-and-list:", run_markdown(silent))

    def test_a_spec_that_cites_a_policy_is_counted(self):
        data, _ = run("cli", {"cite_policy": True}, tickets="01")
        spec = data["tickets"][0]["stages"][1]
        self.assertEqual(spec["notes"]["citedPolicies"], ["public-contract"])
        self.assertEqual((summary(data)["policyConcerns"], summary(data)["policyFindings"]), (1, 0))
        self.assertIn("| 01-add-and-list | ✓ | ✓ cites public-contract |", run_markdown(data))

    def test_a_patch_that_touches_the_pipeline_blocks_the_ticket(self):
        data, _ = run("cli", {"rogue_build": True}, tickets="01")
        build = data["tickets"][0]["stages"][-1]
        self.assertEqual((build["stage"], build["status"]), ("build", "blocked"))
        self.assertTrue(any(".github/workflows/steal.yml" in p for p in build["problems"]))
        self.assertEqual(summary(data)["patchRefusals"], 1)

    def test_reports_aggregate_and_compare_runs(self):
        data, _ = run("library", tickets="01")
        worse = json.loads(json.dumps(data))
        worse["tickets"][0]["acceptance"][0]["status"] = "fail"
        grouped_before, grouped_after = {"library": [data, data]}, {"library": [worse, data]}
        self.assertIn("Checks that did not pass in every run", suite_markdown(grouped_after))
        comparison = compare_markdown(grouped_before, grouped_after)
        self.assertIn("| Acceptance checks passing at the end | 100% | 93% | −7% ± 14% | within noise |", comparison)
        self.assertIn("01-add-and-list: a new list is empty: 100% → 50% (within noise)", comparison)
        steady = compare_markdown({"library": [worse, worse, worse]}, {"library": [data, data, data]})
        self.assertIn("| Acceptance checks passing at the end | 86% | 100% | +14% ± 0% | better |", steady)

    def test_a_difference_counts_only_when_it_clears_the_noise_between_runs(self):
        noisy = Difference.of([2.0, 4.0, 3.0], [3.0, 5.0, 4.0])
        self.assertEqual((noisy.change, noisy.verdict("down")), (1.0, "within noise"))
        self.assertEqual(Difference.of([9.0, 9.1, 9.2], [7.0, 7.1, 6.9]).verdict("down"), "better")
        self.assertEqual(Difference.of([1.0], [2.0]).verdict("up"), "within noise")
        self.assertEqual(Difference.of([1.0, 1.0], [1.0, 1.0]).verdict("up"), "")

    def test_a_run_the_agent_stopped_answering_is_recorded_and_left_out_of_results(self):
        scenario = Scenario.load("todo")
        target = scenario.target("cli")
        bench = BenchRun(scenario, target, scenario.select(["01"]), CutOffAgent(target, answers=3), Settings())
        with self.assertRaises(AgentUnavailable):
            bench.execute()
        broken = json.loads(json.dumps(bench.record.as_json(), default=str))
        self.assertIn("usage limits", broken["error"])
        good, _ = run("cli", tickets="01")
        self.assertIn("(1 run)", suite_markdown({"cli": [good, broken]}))
        self.assertIn("Left out because they did not finish", suite_markdown({"cli": [good, broken]}))
        self.assertIn("1 runs at", compare_markdown({"cli": [good]}, {"cli": [good, broken]}))

    def test_the_cost_cap_is_checked_before_every_stage(self):
        data, _ = run("cli", tickets="01", max_cost=0.025)
        spent = [r["cost"] for s in data["tickets"][0]["stages"] for r in s["runs"]]
        self.assertGreaterEqual(sum(spent), 0.025)
        self.assertLess(sum(spent[:-1]), 0.025)
        self.assertRegex(data["stopped"], r"^stopped before the \w+ stage of 01-add-and-list: \$0\.03 spent, the cap is \$0\.03$")
        self.assertEqual(summary(data)["ticketsCompleted"], 0)
        self.assertTrue(data["tickets"][0]["acceptance"])

    def test_reports_name_the_models_that_ran_and_comparisons_flag_a_change_of_model(self):
        data, _ = run("cli", tickets="01")
        opus, sonnet = priced(data, {"claude-opus-5-5": 0.009, "claude-haiku-5-5": 0.001}), priced(data, {"claude-sonnet-5-5": 0.01})
        self.assertIn("model default (claude-opus-5-5 $", run_markdown(opus))
        self.assertIn("different models (claude-opus-5-5 → claude-sonnet-5-5)", compare_markdown({"cli": [opus]}, {"cli": [sonnet]}))
        self.assertNotIn("different models", compare_markdown({"cli": [opus]}, {"cli": [opus]}))


def priced(run_data: dict, models: dict[str, float]) -> dict:
    copy = json.loads(json.dumps(run_data))
    for ticket in copy["tickets"]:
        for stage in ticket["stages"]:
            for agent_run in stage["runs"]:
                agent_run["models"] = models
    return copy


class ClaudeCodeSessions(unittest.TestCase):
    def test_a_stage_model_overrides_the_run_model(self):
        self.assertEqual(ClaudeCode("sonnet").command("p", Path("repo"), "Read", 5, "abc", "haiku")[-2:], ["--model", "haiku"])
        self.assertEqual(ClaudeCode("sonnet").command("p", Path("repo"), "Read", 5, "abc")[-2:], ["--model", "sonnet"])

    def test_a_session_sees_what_ci_sees(self):
        command = ClaudeCode().command("p", Path("repo"), "Read,Edit(out/**),Bash(make test)", 5, "abc")
        self.assertEqual(command[command.index("--tools") + 1], "Read,Edit,Write,Bash")
        self.assertEqual(command[command.index("--setting-sources") + 1], "project,local")
        host = {"PATH": "/bin", "CLAUDECODE": "1", "CLAUDE_CODE_SYNC_SKILLS": "1", "CLAUDE_CONFIG_DIR": "/c", "CLAUDE_CODE_OAUTH_TOKEN": "t",
                "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_USE_CCR_V2": "1", "ANTHROPIC_API_KEY": "k"}
        with mock.patch.dict(os.environ, host, clear=True):
            self.assertEqual(ClaudeCode.environment(), {**{name: host[name] for name in
                                                           ("PATH", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "ANTHROPIC_API_KEY")},
                                                        "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})

    def test_a_session_records_its_id_and_what_each_model_cost(self):
        self.assertIn("--session-id", ClaudeCode().command("p", Path("repo"), "Read", 5, "abc"))
        output = json.dumps({"subtype": "success", "total_cost_usd": 0.5, "num_turns": 2, "result": "done",
                             "modelUsage": {"claude-sonnet-5-5": {"costUSD": 0.4}, "claude-haiku-5-5": {"costUSD": 0.1}}})
        agent_run = ClaudeCode.parse("p", subprocess.CompletedProcess([], 0, output, ""), 1.0, "abc")
        self.assertEqual((agent_run.ok, agent_run.session), (True, "abc"))
        self.assertEqual(agent_run.models, {"claude-sonnet-5-5": 0.4, "claude-haiku-5-5": 0.1})

    def test_an_api_error_or_a_spent_subscription_stops_the_run_instead_of_scoring_it(self):
        for refusal in ("API Error: 400 You have reached your specified workspace API usage limits.",
                        "You've hit your 5-hour limit · resets 5pm (Asia/Tokyo)"):
            output = json.dumps({"subtype": "success", "is_error": True, "result": refusal})
            with self.assertRaisesRegex(AgentUnavailable, "limit"):
                ClaudeCode.parse("p", subprocess.CompletedProcess([], 0, output, ""), 1.0, "abc")

    def test_a_failed_session_reports_what_went_wrong(self):
        output = json.dumps({"subtype": "error_max_turns", "is_error": True, "result": "Reached the maximum number of turns"})
        agent_run = ClaudeCode.parse("p", subprocess.CompletedProcess([], 0, output, ""), 1.0, "abc")
        self.assertEqual((agent_run.ok, agent_run.error), (False, "Reached the maximum number of turns"))

    def test_transcripts_are_kept_for_failed_sessions_and_stages_with_problems(self):
        with tempfile.TemporaryDirectory() as scratch:
            projects = Path(scratch) / "config" / "projects" / "-tmp-repo"
            projects.mkdir(parents=True)
            for session in ("hung", "untallied", "fine"):
                (projects / f"{session}.jsonl").write_text("{}\n")
            build = StageRecord("build", runs=[AgentRun("p", False, error="timed out", session="hung"), AgentRun("p", True, session="fine")])
            review = StageRecord("review", runs=[AgentRun("p", True, session="untallied")]).block("the reviewer wrote no tally")
            record = RunRecord("todo", "cli", "", "default", "", "", tickets=[TicketRecord("01-add", "Add", None, [build, review], [])])
            kept = Path(scratch) / "run-1-sessions"
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(Path(scratch) / "config")}):
                cli.RunCommand.keep_sessions_with_problems(record, ClaudeCode(), kept)
            self.assertEqual(sorted(p.name for p in kept.iterdir()), ["01-add-build-hung.jsonl", "01-add-review-untallied.jsonl"])


class TestEdits(unittest.TestCase):
    def test_adding_tests_is_fine_but_changing_existing_ones_is_counted(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / ".opensdlc").mkdir()
            (root / ".opensdlc" / "config.json").write_text(json.dumps({"tests": ["tests/**"]}))
            (root / "tests").mkdir()
            (root / "tests" / "test_a.py").write_text("one\ntwo\n")
            workspace = Workspace(root)
            workspace.git("init", "-q", "-b", "main")
            workspace.commit("base")
            ctx = Context(workspace, None, None, None, 1, Settings(), None, base=workspace.head())
            (root / "tests" / "test_a.py").write_text("one\ntwo\nthree\n")
            (root / "tests" / "test_b.py").write_text("new\n")
            workspace.commit("add tests")
            self.assertEqual(BuildStage().rewritten_tests(ctx), [])
            (root / "tests" / "test_a.py").write_text("one\nthree\n")
            workspace.commit("weaken a test")
            self.assertEqual(BuildStage().rewritten_tests(ctx), ["tests/test_a.py"])


class Sandbox(unittest.TestCase):
    def test_the_bench_and_ci_hide_the_same_sandbox_placeholders(self):
        action = (TEMPLATE / ".github" / "actions" / "opensdlc-sandbox" / "action.yml").read_text()
        for name in SANDBOX_PLACEHOLDERS:
            self.assertRegex(action, rf"\n\s+{re.escape(name)}\n", name)


class Layout(unittest.TestCase):
    def test_results_are_not_committed(self):
        self.assertIn("results/", (BENCH / ".gitignore").read_text())

    def test_it_runs_from_the_repository_root(self):
        result = subprocess.run([sys.executable, "bench", "list"], cwd=BENCH.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("target web", result.stdout)

    def test_native_windows_gets_told_to_use_wsl(self):
        with mock.patch.object(cli.os, "name", "nt"), mock.patch("sys.stderr") as stderr:
            self.assertEqual(cli.main(["verify"]), 2)
        self.assertIn("WSL2", "".join(call.args[0] for call in stderr.write.call_args_list))

    def test_an_old_python3_is_named_before_anything_builds(self):
        with mock.patch.object(cli, "python3_at_least", return_value=False), mock.patch("sys.stderr") as stderr:
            self.assertEqual(cli.main(["verify"]), 2)
        self.assertIn("Python 3.12", "".join(call.args[0] for call in stderr.write.call_args_list))

    def test_the_python3_check_reads_the_python3_on_the_path(self):
        self.assertTrue(cli.python3_at_least(3, 0))
        self.assertFalse(cli.python3_at_least(99, 0))

    def test_every_workspace_starts_with_the_scenarios_knowledge_and_passes_check(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Workspace.create(Scenario.load("todo").target("cli"), Path(scratch))
            for path in ("GLOSSARY.md", "docs/adr/0001-todo-ids-are-permanent.md", "knowledge/policies/public-contract.md",
                         ".claude/skills/public-contract/SKILL.md", "knowledge/architecture/interface.md"):
                self.assertTrue((workspace.root / path).is_file(), path)
            self.assertFalse((workspace.root / "knowledge/policies/secure-api.md").exists())
            self.assertTrue(workspace.opensdlc("check").ok, workspace.opensdlc("check").output)
            self.assertEqual(workspace.git("status", "--porcelain"), "")

    def test_what_verification_leaves_behind_never_reaches_the_patch(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Workspace.create(Scenario.load("todo").target("cli"), Path(scratch))
            (workspace.root / "feature.py").write_text("print(1)\n")
            workspace.git("add", "feature.py")
            (workspace.root / "feature.py").write_text("print(2)\n")
            (workspace.root / "scratch.txt").write_text("left behind")
            workspace.restore()
            self.assertEqual((workspace.root / "feature.py").read_text(), "print(1)\n")
            self.assertFalse((workspace.root / "scratch.txt").exists())

    def test_scripts_stay_executable_when_an_unzip_dropped_the_bit(self):
        with tempfile.TemporaryDirectory() as scratch:
            target_root = Path(scratch) / "cli"
            shutil.copytree(Scenario.load("todo").target("cli").root, target_root)
            (target_root / "skeleton" / "todo").chmod(0o644)
            workspace = Workspace.create(Target.load(target_root), Path(scratch) / "work")
            self.assertTrue(os.access(workspace.root / "todo", os.X_OK))


if __name__ == "__main__":
    unittest.main()
