# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from support import git, git_repo, temp_project
from test_artifacts import change, edit_body, set_status

from opensdlc.cli import main
from opensdlc.metrics import indicators as ind
from opensdlc.metrics.dataset import Dataset
from opensdlc.metrics.records import (
    ArtifactCommit, ChangeHistory, Comment, Commit, Deployment, EvalCase, EvalRun, GateWait, Incident,
    PullRequest, Review, Run, SecurityFinding, SecurityRepo, Session, Ticket, Window,
)
from opensdlc.metrics.report import STAGES, build, markdown
from opensdlc.document import Document
from opensdlc.knowledge import plan_files
from opensdlc.metrics.sources import GitHubSource, GitSource, IncidentSource, SessionsSource

END = datetime(2026, 10, 26, tzinfo=timezone.utc)
WINDOW = Window(END - timedelta(days=30), END)
PREVIOUS = Window(END - timedelta(days=60), END - timedelta(days=30))


def at(days_ago: float, hours: float = 0) -> datetime:
    return END - timedelta(days=days_ago) + timedelta(hours=hours)


def commit(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def measure(indicator, data, window=WINDOW):
    return indicator.measure(data, window)


def empty() -> Dataset:
    return Dataset(changes=[], agents_md_commits=[], prs=[], runs=[], gate_waits=[], deployments=[], incidents=[],
                   eval_runs=[], eval_cases=[], sessions=[], hook_blocks=[], security_findings=[], security_repos=[], team={})



def history(id_="c1", started=None, plan_files_=(), **artifacts) -> ChangeHistory:
    return ChangeHistory(id=id_, started=started, plan_files=list(plan_files_),
                         artifacts={k: [ArtifactCommit(t, s, h) for t, s, h in v] for k, v in artifacts.items()})


def pr(number=1, author="dev", created=None, merged=None, **kw) -> PullRequest:
    return PullRequest(number=number, author=author, created=created or at(10), merged=merged, files=kw.pop("files", ["src/a.py"]), **kw)


class Registry(unittest.TestCase):
    def test_every_playbook_indicator_is_registered_once(self):
        ids = [i.id for i in ind.INDICATORS]
        self.assertEqual(len(ids), 35)
        self.assertEqual(len(set(ids)), 35)

    def test_each_indicator_is_well_formed(self):
        for i in ind.INDICATORS:
            self.assertIn(i.kind, ("leading", "lagging"), i.id)
            self.assertIn(i.better, ("up", "down"), i.id)
            self.assertIn(i.stage, STAGES, i.id)
            self.assertTrue(set(i.needs) <= set(ind.SOURCE_NEEDS), i.id)

    def test_every_play_has_a_leading_and_a_lagging_indicator(self):
        plays = {}
        for i in ind.INDICATORS:
            plays.setdefault(i.play, set()).add(i.kind)
        for play, kinds in plays.items():
            self.assertEqual(kinds, {"leading", "lagging"}, play)

    def test_the_catalog_documents_every_indicator(self):
        catalog = (Path(__file__).resolve().parent.parent / "docs" / "indicators.md").read_text()
        for i in ind.INDICATORS + [i for s in ind.SUPPLEMENTS for i in s.indicators]:
            self.assertIn(f"`{i.id}`", catalog, i.id)
            self.assertIn(i.title, catalog, i.id)

    def test_missing_sources_are_reported_not_guessed(self):
        for i in ind.INDICATORS:
            result = measure(i, Dataset())
            self.assertEqual(result.status, "unavailable", i.id)
            self.assertTrue(result.detail, i.id)

    def test_empty_data_is_no_data_not_zero(self):
        for i in ind.INDICATORS:
            result = measure(i, empty())
            self.assertIn(result.status, ("no-data", "ok"), i.id)
            if i.unit in ("share", "hours", "minutes", "days"):
                self.assertIsNone(result.value, i.id)


class PlanAndDesign(unittest.TestCase):
    def test_capture_time_uses_started(self):
        data = empty()
        data.changes = [history(started=at(5), intent=[(at(5, 3), "draft", "a")]), history("c2", intent=[(at(4), "draft", "b")])]
        result = measure(ind.IntentCaptureTime(), data)
        self.assertEqual((result.value, result.n), (3.0, 1))

    def test_survival_counts_rejections_and_abandoned_prs(self):
        data = empty()
        data.changes = [
            history("a", intent=[(at(9), "draft", "x"), (at(8), "accepted", "x")]),
            history("b", intent=[(at(9), "draft", "y"), (at(7), "rejected", "y")]),
        ]
        data.prs = [pr(5, closed=at(6), files=["changes/c/intent.md"])]
        result = measure(ind.IntentSurvival(), data)
        self.assertAlmostEqual(result.value, 1 / 3)
        self.assertIn("1 closed unmerged", result.detail)

    def test_intent_edits_after_spec_ignore_status_only_commits(self):
        data = empty()
        data.changes = [history(
            intent=[(at(10), "draft", "h1"), (at(9), "accepted", "h1"), (at(5), "accepted", "h2"), (at(4), "accepted", "h3")],
            spec=[(at(8), "draft", "s1")],
        )]
        self.assertEqual(measure(ind.IntentEditsAfterSpec(), data).value, 2)

    def test_intent_to_spec_measures_from_acceptance(self):
        data = empty()
        data.changes = [history(intent=[(at(10), "draft", "a"), (at(9), "accepted", "a")], spec=[(at(9, 2), "draft", "s")])]
        self.assertEqual(measure(ind.IntentToSpec(), data).value, 2.0)

    def test_spec_rework_after_plan(self):
        data = empty()
        data.changes = [history(spec=[(at(10), "accepted", "a"), (at(3), "accepted", "b")], plan=[(at(5), "draft", "p")])]
        self.assertEqual(measure(ind.SpecReworkAfterPlan(), data).value, 1)


class Build(unittest.TestCase):
    def reviewed(self, number, extra_commit=False):
        commits = [Commit("dev", at(10))] + ([Commit("dev", at(8))] if extra_commit else [])
        return pr(number, merged=at(7), commits=commits, reviews=[Review("lead", "COMMENTED", at(9))])

    def test_first_pass_and_rework(self):
        data = empty()
        data.prs = [self.reviewed(1), self.reviewed(2, extra_commit=True)]
        self.assertEqual(measure(ind.FirstPassMerge(), data).value, 0.5)
        self.assertEqual(measure(ind.ReworkCycles(), data).value, 0.5)

    def test_artifact_only_prs_are_not_implementation(self):
        data = empty()
        data.prs = [pr(1, merged=at(5), files=["changes/x/spec.md"])]
        self.assertEqual(measure(ind.FirstPassMerge(), data).n, 0)

    def test_plan_to_merge(self):
        data = empty()
        data.changes = [history(plan=[(at(10), "draft", "p"), (at(9), "accepted", "p"), (at(8), "implemented", "p")])]
        self.assertEqual(measure(ind.PlanToMerge(), data).value, 24.0)

    def test_plan_match(self):
        data = empty()
        data.changes = [history("c1", plan_files_=["src/a.py"]), history("c2", plan_files_=["src/a.py"])]
        data.prs = [
            pr(1, merged=at(3), files=["src/a.py", "changes/c1/plan.md"]),
            pr(2, merged=at(3), files=["src/a.py", "src/b.py", "changes/c2/plan.md"]),
        ]
        self.assertEqual(measure(ind.PlanMatch(), data).value, 0.5)

    def test_review_tallies_drive_repeat_and_policy_findings(self):
        data = empty()
        tally = {"important": 2, "findings": [{"repeat": True, "policy": "pii"}, {"repeat": False, "policy": None}]}
        data.prs = [pr(1, created=at(4), comments=[Comment("github-actions[bot]", at(4), f"x <!-- opensdlc:review {json.dumps(tally)} -->")])]
        data.agents_md_commits = [at(2)]
        self.assertEqual(measure(ind.RepeatFindings(), data).value, 1)
        self.assertIn("1 AGENTS.md corrections", measure(ind.RepeatFindings(), data).detail)
        self.assertEqual(measure(ind.PolicyFindings(), data).value, 1)

    def test_new_joiner_first_merge(self):
        data = empty()
        data.team = {"new": at(20)}
        data.prs = [pr(1, author="new", merged=at(15)), pr(2, author="new", merged=at(10))]
        self.assertEqual(measure(ind.NewJoinerFirstMerge(), data).value, 5)

    def test_concurrent_sessions_peak(self):
        data = empty()
        data.sessions = [Session("a", at(5), at(5, 3)), Session("a", at(5, 1), at(5, 2)), Session("a", at(5, 4), at(5, 5)), Session("b", at(3), at(3, 1))]
        self.assertEqual(measure(ind.ConcurrentSessions(), data).value, 1.5)

    def test_throughput_credits_the_merger_of_agent_prs(self):
        data = empty()
        data.prs = [pr(1, author="claude[bot]", merged=at(3), merged_by="dev", agent=True), pr(2, author="dev", merged=at(2))]
        result = measure(ind.Throughput(), data)
        self.assertEqual(result.n, 1)
        self.assertAlmostEqual(result.value, 2 / WINDOW.weeks)


class TestStage(unittest.TestCase):
    def test_first_pass_ci_uses_the_first_run_per_branch(self):
        data = empty()
        data.prs = [pr(1, created=at(5), branch="opensdlc/a/build", agent=True), pr(2, created=at(5), branch="opensdlc/b/build", agent=True)]
        data.runs = [
            Run(1, "CI", "pull_request", "opensdlc/a/build", "s1", at(5, 1), "failure"),
            Run(2, "CI", "pull_request", "opensdlc/a/build", "s2", at(5, 2), "success"),
            Run(3, "CI", "pull_request", "opensdlc/b/build", "s3", at(5, 1), "success"),
        ]
        self.assertEqual(measure(ind.FirstPassCi(), data).value, 0.5)

    def test_change_failure_rate(self):
        data = empty()
        data.prs = [pr(1, merged=at(5)), pr(2, merged=at(5))]
        data.incidents = [Incident("#9", at(4), caused_by="#2")]
        self.assertEqual(measure(ind.ChangeFailureRate(), data).value, 0.5)

    def test_eval_metrics(self):
        data = empty()
        data.eval_runs = [EvalRun(at(5), 0.8, "schedule", "failure"), EvalRun(at(4), 1.0, "pull_request", "success"),
                          EvalRun(at(3), 0.5, "pull_request", "failure")]
        data.incidents = [Incident("#7", at(20)), Incident("#8", at(2), found_in="production", kind=frozenset({"regression"}))]
        data.eval_cases = [EvalCase("e", "#7", at(17))]
        self.assertAlmostEqual(measure(ind.EvalPassRate(), data).value, 2.3 / 3)
        self.assertEqual(measure(ind.IncidentToEval(), data).value, 3)
        self.assertEqual(measure(ind.RegressionsCaught(), data).value, 0.5)


class DeployAndMaintain(unittest.TestCase):
    def test_review_indicators(self):
        data = empty()
        data.agent_logins = frozenset({"claude[bot]"})
        data.prs = [
            pr(1, created=at(5), merged=at(4), comments=[Comment("bot", at(5, 0.5), "x")], commits=[Commit("claude[bot]", at(4, 12))]),
            pr(2, created=at(5), merged=at(4), reviews=[Review("lead", "COMMENTED", at(5, 1))], commits=[Commit("dev", at(4, 12))]),
        ]
        self.assertEqual(measure(ind.TimeToFirstReview(), data).value, 45)
        self.assertEqual(measure(ind.AgentResolved(), data).value, 0.5)

    def test_caught_vs_escaped(self):
        data = empty()
        data.prs = [pr(1, created=at(4), comments=[Comment("b", at(4), '<!-- opensdlc:review {"important": 3, "findings": []} -->')])]
        data.incidents = [Incident("#1", at(2), found_in="production", kind=frozenset({"defect"}))]
        self.assertEqual(measure(ind.CaughtVsEscaped(), data).value, 0.75)

    def test_gate_wait_per_gate(self):
        data = empty()
        data.gate_waits = [GateWait("release", at(3), at(3, 0.5)), GateWait("release", at(2), at(2, 1.5)), GateWait("db", at(2), at(2, 0.25))]
        data.hook_blocks = [at(1)]
        result = measure(ind.GateWaitTime(), data)
        self.assertEqual(result.parts, {"release": 60.0, "db": 15.0})
        self.assertIn("1 hook blocks", result.detail)

    def test_failures_triaged(self):
        data = empty()
        data.runs = [Run(1, "CI", "pull_request", "b", "s1", at(3), "failure"), Run(2, "CI", "pull_request", "b", "s2", at(2), "failure"),
                     Run(3, "OpenSDLC CI triage", "workflow_run", "main", "s1", at(3, 1), "success")]
        self.assertEqual(measure(ind.FailuresTriaged(), data).value, 0.5)

    def test_dora(self):
        data = empty()
        data.deployments = [Deployment("a1", at(10), at(10, -4)), Deployment("b2", at(3), at(3, -2))]
        data.incidents = [Incident("#1", at(3, 1), at(3, 3), found_in="production", caused_by="b2")]
        parts = measure(ind.Dora(), data).parts
        self.assertAlmostEqual(parts["deploysPerWeek"], 2 / WINDOW.weeks)
        self.assertEqual((parts["leadTimeHours"], parts["changeFailureRate"], parts["timeToRestoreHours"]), (3.0, 0.5, 2.0))

    def test_breach_to_intent_and_findings_to_fixes(self):
        marker = '<!-- opensdlc:breach {"monitor": "ci", "tier": "3sigma", "detectedAt": "%s"} -->'
        data = empty()
        data.changes = [history("2026-10-flaky", plan=[(at(1), "implemented", "p")])]
        data.prs = [
            pr(1, created=at(5, 0.25), merged=at(4), body=marker % at(5).isoformat(), files=["changes/2026-10-flaky/intent.md"]),
            pr(2, created=at(3, 0.5), closed=at(2), body=marker % at(3).isoformat(), files=["changes/2026-10-other/intent.md"]),
        ]
        self.assertEqual(measure(ind.BreachToIntent(), data).value, 22.5)
        result = measure(ind.FindingsToFixes(), data)
        self.assertEqual(result.value, 0.5)
        self.assertIn("1 dismissed", result.detail)

    def test_repeat_incidents_look_back_before_the_window(self):
        data = empty()
        data.incidents = [Incident("#1", at(90), found_in="production", incident_class="cache"),
                          Incident("#2", at(5), found_in="production", incident_class="cache"),
                          Incident("#3", at(4), found_in="production", incident_class="auth"),
                          Incident("#4", at(3), found_in="production", incident_class="auth")]
        self.assertEqual(measure(ind.RepeatIncidents(), data).value, 2)

    def test_security(self):
        data = empty()
        data.security_repos = [SecurityRepo("a", True), SecurityRepo("b", False)]
        data.security_findings = [SecurityFinding("f1", at(6), "s1", 10), SecurityFinding("f2", at(5), "s1"), SecurityFinding("f3", at(2), "s2")]
        data.prs = [pr(10, created=at(5))]
        data.incidents = [Incident("#1", at(1), found_in="external", kind=frozenset({"security"}))]
        self.assertEqual(measure(ind.ScanCoverage(), data).value, 0.5)
        self.assertEqual(measure(ind.FindingToPatch(), data).value, 24)
        self.assertEqual(measure(ind.ScanVsProduction(), data).value, 0.75)
        self.assertEqual(measure(ind.FindingsPerScan(), data).value, 1.5)


class Report(unittest.TestCase):
    def test_report_trends_and_lists_what_to_configure(self):
        data = empty()
        data.prs = [pr(1, created=at(5), reviews=[Review("l", "COMMENTED", at(5, 1))]),
                    pr(2, created=at(40), reviews=[Review("l", "COMMENTED", at(40, 2))])]
        data.sessions = None
        result = build(data, END, 30)
        row = next(r for r in result["indicators"] if r["id"] == "review.time-to-first-review")
        self.assertEqual(row["display"], "60 min")
        self.assertIn("better", row["trend"])
        text = markdown(result)
        for stage in STAGES:
            self.assertIn(f"### {stage}", text)
        self.assertIn("metrics.otel.sessions", text)
        self.assertEqual(result["collected"], 34)


class Baseline(unittest.TestCase):
    def test_baseline_column_compares_with_the_window_before_adoption(self):
        data = empty()
        data.prs = [pr(1, created=at(5), reviews=[Review("l", "COMMENTED", at(5, 1))]),
                    pr(2, created=at(70), reviews=[Review("l", "COMMENTED", at(70, 3))])]
        result = build(data, END, 30, adopted=END - timedelta(days=60))
        row = next(r for r in result["indicators"] if r["id"] == "review.time-to-first-review")
        self.assertEqual(row["baselineDisplay"], "3.0 h")
        self.assertIn("better than baseline", row["vsBaseline"])
        self.assertIn("Baseline is the 30 days before adoption", markdown(result))

    def test_no_adoption_date_means_no_baseline_column(self):
        result = build(empty(), END, 30)
        self.assertIsNone(result["baseline"])
        self.assertNotIn("vs baseline", markdown(result))

    def test_ticket_proxies(self):
        data = empty()
        data.prs = [pr(7, created=at(8))]
        data.tickets = [Ticket(1, at(10), at(2), (7,)), Ticket(2, at(9), None, ())]
        rows = {r["id"]: r for r in build(data, END, 30)["proxies"]}
        self.assertEqual(rows["proxy.ticket-lead-time"]["current"]["value"], 8)
        self.assertEqual(rows["proxy.ticket-to-first-pr"]["current"]["value"], 2)

    def test_small_team_indicators(self):
        data = empty()
        data.agent_logins = frozenset({"github-actions[bot]"})
        data.prs = [
            pr(1, merged=at(4), agent=True, commits=[Commit("github-actions[bot]", at(5)), Commit("glenn", at(4, 1)), Commit("glenn", at(4, 2))]),
            pr(2, merged=at(4), agent=True, commits=[Commit("github-actions[bot]", at(5)), Commit("", at(5, 1))],
               reviews=[Review("glenn", "APPROVED", at(4))], labels=["ceremony"]),
            pr(3, merged=at(4), reviews=[Review("glenn", "APPROVED", at(4))]),
            pr(4, merged=at(4), reviews=[Review("glenn", "COMMENTED", at(4))], labels=["ceremony"]),
        ]
        rows = {r["id"]: r for r in build(data, END, 30)["smallTeam"]}
        self.assertEqual(rows["small-team.interventions"]["current"]["value"], 1)
        self.assertEqual(rows["small-team.interventions"]["current"]["detail"], "1 of 2 needed a person")
        self.assertEqual(rows["small-team.ceremony"]["current"]["value"], 0.5)
        self.assertIn("### Small teams", markdown(build(data, END, 30)))

    def test_proxies_say_what_they_need(self):
        result = build(empty(), END, 30)
        self.assertIn("metrics.baseline.issueLabel", markdown(result))


class Sources(unittest.TestCase):
    def test_plan_files_parses_bullets_and_backticks(self):
        text = "---\nkind: plan\n---\n## Files that change\n- `src/a.ts`: new\n* lib/b.py - edit\nsrc/c.go (delete)\n<placeholder>\n\n## Slices\n- `src/z.ts`\n"
        section = Document.parse(Path("plan.md"), text).section("Files that change")
        self.assertEqual(plan_files(section), ["src/a.ts", "lib/b.py", "src/c.go"])

    def test_git_source_reads_artifact_history(self):
        root = temp_project({})
        git_repo(root)
        c = change(root, intent="draft")
        commit(root, "intent draft")
        c = set_status(c, "intent", "accepted")
        commit(root, "accept")
        edit_body(c, "intent")
        commit(root, "edit")
        (root / "CLAUDE.md").write_text("x")
        commit(root, "claude")
        (root / "AGENTS.md").write_text("y")
        commit(root, "agents")
        data = Dataset()
        GitSource(root, {}, END - timedelta(days=365)).fill(data)
        history_ = data.changes[0]
        self.assertEqual([c.status for c in history_.commits("intent")], ["draft", "accepted", "accepted"])
        hashes = [c.hash for c in history_.commits("intent")]
        self.assertEqual(hashes[0], hashes[1])
        self.assertNotEqual(hashes[1], hashes[2])
        self.assertEqual(history_.started.isoformat(), "2026-10-01T09:00:00+00:00")
        self.assertEqual(len(data.agents_md_commits), 2)

    def test_github_source_normalizes_and_flags_agents(self):
        responses = {
            ("repo", "view"): {"nameWithOwner": "o/r"},
            ("pr", "list"): [{
                "number": 4, "author": {"login": "claude[bot]"}, "createdAt": "2026-10-20T00:00:00Z", "mergedAt": "2026-10-21T00:00:00Z",
                "closedAt": None, "mergedBy": {"login": "dev"}, "headRefName": "opensdlc/x/build", "body": "", "labels": [],
                "files": [{"path": "src/a.py"}], "commits": [{"authors": [{"login": "claude[bot]"}], "committedDate": "2026-10-20T01:00:00Z"}],
                "reviews": [{"author": {"login": "dev"}, "state": "APPROVED", "submittedAt": "2026-10-20T05:00:00Z"}],
                "comments": [{"author": {"login": "bot"}, "createdAt": "2026-10-20T00:10:00Z", "body": "hi"}],
            }],
            ("run", "list"): [{"databaseId": 1, "workflowName": "CI", "event": "pull_request", "headBranch": "opensdlc/x/build",
                               "headSha": "s", "createdAt": "2026-10-20T00:05:00Z", "conclusion": "success"}],
            ("api",): [],
        }

        def shell(args, cwd):
            key = tuple(args[1:3]) if tuple(args[1:3]) in responses else tuple(args[1:2])
            if args[:3] == ["gh", "run", "download"]:
                raise __import__("opensdlc.metrics.sources", fromlist=["SourceError"]).SourceError("no artifact")
            return json.dumps(responses[key])

        data = Dataset()
        GitHubSource(Path("."), {"agents": {"branchPrefixes": ["opensdlc/"]}}, END - timedelta(days=60), shell).fill(data)
        self.assertTrue(data.prs[0].agent)
        self.assertEqual(data.prs[0].merged_by, "dev")
        self.assertEqual(data.runs[0].conclusion, "success")
        self.assertIsNone(data.gate_waits)
        self.assertEqual(data.eval_runs, [])

    def test_failing_source_marks_its_fields_unavailable_with_the_reason(self):
        def shell(args, cwd):
            raise __import__("opensdlc.metrics.sources", fromlist=["SourceError"]).SourceError("gh: not authenticated")

        data = Dataset()
        GitHubSource(Path("."), {}, END, shell).fill(data)
        self.assertIsNone(data.prs)
        self.assertIn("not authenticated", data.unavailable["prs"])
        self.assertIn("not authenticated", measure(ind.FirstPassMerge(), data).detail)

    def test_incidents_from_labelled_issues(self):
        issues = [{"number": 12, "createdAt": "2026-10-01T00:00:00Z", "closedAt": "2026-10-01T04:00:00Z",
                   "labels": [{"name": "incident"}, {"name": "found-in:production"}, {"name": "class:cache"}, {"name": "regression"}],
                   "body": "Root cause.\nCaused-by: #40"}]
        data = Dataset()
        IncidentSource(Path("."), {"incidents": {"type": "github-issues"}}, END, lambda a, c: json.dumps(issues)).fill(data)
        incident = data.incidents[0]
        self.assertEqual((incident.id, incident.found_in, incident.incident_class, incident.caused_by), ("#12", "production", "cache", "#40"))
        self.assertEqual(incident.kind, frozenset({"incident", "regression"}))

    def test_unconfigured_sources_stay_unavailable(self):
        data = Dataset()
        IncidentSource(Path("."), {}, END).fill(data)
        SessionsSource(Path("."), {}, END).fill(data)
        self.assertIsNone(data.incidents)
        self.assertIsNone(data.sessions)

    def test_command_sources(self):
        data = Dataset()
        payload = json.dumps([{"user": "a", "start": "2026-10-20T00:00:00Z", "end": "2026-10-20T01:00:00Z"}])
        SessionsSource(Path("."), {"otel": {"sessions": {"run": ["x"]}}}, END, lambda a, c: payload).fill(data)
        self.assertEqual(data.sessions[0].user, "a")


class Command(unittest.TestCase):
    def test_metrics_command_runs_against_a_bare_repo(self):
        root = git_repo(temp_project({"metrics": {"windowDays": 7}}))
        self.assertEqual(main(["--root", str(root), "metrics", "--end", "2026-10-26T00:00:00Z"]), 0)
        report = json.loads((root / ".opensdlc" / "out" / "metrics.json").read_text())
        self.assertEqual(report["total"], 35)
        self.assertEqual(report["window"]["days"], 7)
        self.assertTrue((root / ".opensdlc" / "out" / "metrics.md").read_text().startswith("## OpenSDLC indicators"))


if __name__ == "__main__":
    unittest.main()
