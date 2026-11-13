# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import statistics
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from .dataset import Dataset, markers
from .records import PullRequest, Window, parse_time

HOUR = 3600


@dataclass(frozen=True)
class Measurement:
    status: str
    value: float | None = None
    n: int = 0
    detail: str = ""
    parts: dict = field(default_factory=dict)

    @classmethod
    def of(cls, value: float | None, n: int, detail: str = "", parts: dict | None = None) -> "Measurement":
        return cls("ok" if value is not None else "no-data", value, n, detail, parts or {})

    @classmethod
    def unavailable(cls, needs: str) -> "Measurement":
        return cls("unavailable", detail=needs)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def hours(delta: timedelta) -> float:
    return delta.total_seconds() / HOUR


def share(part: int, whole: int) -> float | None:
    return part / whole if whole else None


SOURCE_NEEDS = {
    "changes": "git history of changes/",
    "agents_md_commits": "git history of AGENTS.md and CLAUDE.md",
    "prs": "GitHub pull requests through the gh CLI",
    "runs": "GitHub Actions runs through the gh CLI",
    "gate_waits": "metrics.gates: the workflow and job that wait on release approval",
    "deployments": "GitHub deployments to metrics.deployEnvironment",
    "incidents": 'metrics.incidents: {"type": "github-issues"} or a command printing incidents',
    "eval_runs": "runs of the OpenSDLC evals workflow",
    "eval_cases": "evals/cases with an incident field",
    "sessions": "metrics.otel.sessions: a command printing [{user, start, end}] from your OpenTelemetry backend",
    "hook_blocks": "metrics.otel.hookBlocks: a command printing the times of claude_code.tool_decision events with source=hook, decision=reject",
    "security_findings": "metrics.security.findings: a command printing [{id, reported, scan, patchPr}] from Claude Security exports",
    "security_repos": "metrics.security.repositories: a command printing [{name, scheduled}]",
    "team": "metrics.team: join dates for team members",
    "tickets": "metrics.baseline.issueLabel: the label your tracker puts on feature tickets",
}


class Indicator(ABC):
    id: str
    stage: str
    play: str
    kind: str
    title: str
    unit: str
    better: str
    needs: tuple[str, ...] = ()
    note: str = ""

    def measure(self, data: Dataset, window: Window) -> Measurement:
        missing = [n for n in self.needs if getattr(data, n) is None]
        if missing:
            return Measurement.unavailable("; ".join(data.unavailable.get(n) or SOURCE_NEEDS[n] for n in missing))
        return self.compute(data, window)

    @abstractmethod
    def compute(self, data: Dataset, window: Window) -> Measurement: ...


def implementation_prs(data: Dataset, window: Window) -> list[PullRequest]:
    return [p for p in data.prs if p.merged in window and p.implementation]


def change_prs(data: Dataset, window: Window) -> list[tuple[PullRequest, str]]:
    found = []
    for pr in implementation_prs(data, window):
        ids = {f.split("/")[1] for f in pr.files if f.startswith("changes/") and f.endswith("/plan.md")}
        found += [(pr, i) for i in ids]
    return found


def production(data: Dataset, window: Window) -> list:
    return [i for i in data.incidents if i.opened in window and i.found_in == "production"]


class IntentCaptureTime(Indicator):
    id, stage, play, kind = "plan.capture-time", "Plan", "Capture as intent.md", "leading"
    title, unit, better, needs = "First conversation to committed intent.md", "hours", "down", ("changes",)

    def compute(self, data, window):
        times = [hours(c.first("intent") - c.started) for c in data.changes if c.started and c.first("intent") in window]
        return Measurement.of(median(times), len(times), "median; intents without a started time are skipped")


class IntentSurvival(Indicator):
    id, stage, play, kind = "plan.survival-rate", "Plan", "Capture as intent.md", "lagging"
    title, unit, better, needs = "Intents accepted into Design", "share", "up", ("changes", "prs")

    def compute(self, data, window):
        accepted = sum(c.first_with_status("intent", "accepted") in window for c in data.changes)
        rejected = sum(c.first_with_status("intent", "rejected") in window for c in data.changes)
        abandoned = sum(
            p.merged is None and p.closed in window and any(f.endswith("/intent.md") for f in p.files) and not p.implementation
            for p in data.prs
        )
        return Measurement.of(share(accepted, accepted + rejected + abandoned), accepted + rejected + abandoned,
                              f"{accepted} accepted, {rejected} rejected, {abandoned} closed unmerged")


class IntentEditsAfterSpec(Indicator):
    id, stage, play, kind = "plan.intent-edits-after-spec", "Plan", "Capture as intent.md", "lagging"
    title, unit, better, needs = "Intent edits after the first spec", "per change", "down", ("changes",)

    def compute(self, data, window):
        counts = [c.content_edits_after("intent", c.first("spec")) for c in data.changes if c.first("spec") in window]
        return Measurement.of(mean(counts), len(counts), "content edits only; status changes are ignored")


class IntentToSpec(Indicator):
    id, stage, play, kind = "design.intent-to-spec", "Design", "Requirements and design", "leading"
    title, unit, better, needs = "Accepted intent to spec.md", "hours", "down", ("changes",)

    def compute(self, data, window):
        times = []
        for c in data.changes:
            spec, intent = c.first("spec"), c.first_with_status("intent", "accepted") or c.first("intent")
            if spec in window and intent:
                times.append(hours(spec - intent))
        return Measurement.of(median(times), len(times), "median")


class SpecReworkAfterPlan(Indicator):
    id, stage, play, kind = "design.spec-rework-after-plan", "Design", "Requirements and design", "lagging"
    title, unit, better, needs = "Spec edits after the first plan", "per change", "down", ("changes",)

    def compute(self, data, window):
        counts = [c.content_edits_after("spec", c.first("plan")) for c in data.changes if c.first("plan") in window]
        return Measurement.of(mean(counts), len(counts))


class FirstPassMerge(Indicator):
    id, stage, play, kind = "build.first-pass-merge", "Build", "Plan mode", "leading"
    title, unit, better, needs = "Changes merged from the first implementation pass", "share", "up", ("prs",)

    def compute(self, data, window):
        prs = implementation_prs(data, window)
        return Measurement.of(share(sum(p.rework_cycles() == 0 for p in prs), len(prs)), len(prs))


class PlanToMerge(Indicator):
    id, stage, play, kind = "build.plan-to-merge", "Build", "Plan mode", "leading"
    title, unit, better, needs = "Plan accepted to implementation merged", "hours", "down", ("changes",)

    def compute(self, data, window):
        times = []
        for c in data.changes:
            done, accepted = c.first_with_status("plan", "implemented"), c.first_with_status("plan", "accepted")
            if done in window and accepted:
                times.append(hours(done - accepted))
        return Measurement.of(median(times), len(times), "median")


class ReworkCycles(Indicator):
    id, stage, play, kind = "build.rework-cycles", "Build", "Plan mode", "lagging"
    title, unit, better, needs = "Rework cycles per change", "per PR", "down", ("prs",)

    def compute(self, data, window):
        cycles = [p.rework_cycles() for p in implementation_prs(data, window)]
        return Measurement.of(mean(cycles), len(cycles), "a cycle is a round of feedback answered by new commits")


class PlanMatch(Indicator):
    id, stage, play, kind = "build.plan-match", "Build", "Plan mode", "lagging"
    title, unit, better, needs = "Merged diffs that match plan.md", "share", "up", ("prs", "changes")

    def compute(self, data, window):
        plans = {c.id: set(c.plan_files) for c in data.changes if c.plan_files}
        checked = [(pr, plans[i]) for pr, i in change_prs(data, window) if i in plans]
        matched = sum({f for f in pr.files if not f.startswith("changes/")} <= files for pr, files in checked)
        return Measurement.of(share(matched, len(checked)), len(checked), "files outside changes/ are all listed under Files that change")


class RepeatFindings(Indicator):
    id, stage, play, kind = "claudemd.repeat-findings", "Build", "CLAUDE.md", "leading"
    title, unit, better, needs = "Repeated mistakes AGENTS.md should have caught", "per reviewed PR", "down", ("prs", "agents_md_commits")

    def compute(self, data, window):
        tallies = [t for pr, t in data.review_tallies() if pr.created in window]
        repeats = sum(sum(bool(f.get("repeat")) for f in t.get("findings", [])) for t in tallies)
        edits = sum(t in window for t in data.agents_md_commits)
        return Measurement.of(share(repeats, len(tallies)), len(tallies), f"{edits} AGENTS.md corrections in the window")


class NewJoinerFirstMerge(Indicator):
    id, stage, play, kind = "claudemd.new-joiner-first-merge", "Build", "CLAUDE.md", "lagging"
    title, unit, better, needs = "New joiner's time to first merged PR", "days", "down", ("prs", "team")

    def compute(self, data, window):
        days = []
        for login, joined in data.team.items():
            merged = sorted(p.merged for p in data.prs if p.author == login and p.merged and p.merged >= joined)
            if merged and merged[0] in window:
                days.append(hours(merged[0] - joined) / 24)
        return Measurement.of(median(days), len(days), "median")


class PolicyToSkill(Indicator):
    id, stage, play, kind = "skills.policy-to-skill", "Build", "Skills as institutional knowledge", "leading"
    title, unit, better, needs = "Skill change opened to merged", "hours", "down", ("prs",)
    note = "Proxy for policy approval to skill merge until policy documents are tracked."

    def compute(self, data, window):
        times = [hours(p.merged - p.created) for p in data.prs
                 if p.merged in window and any(f.startswith(".claude/skills/") for f in p.files)]
        return Measurement.of(median(times), len(times), "median")


class PolicyFindings(Indicator):
    id, stage, play, kind = "skills.policy-findings", "Build", "Skills as institutional knowledge", "lagging"
    title, unit, better, needs = "Review findings that cite a policy", "per reviewed PR", "down", ("prs",)

    def compute(self, data, window):
        tallies = [t for pr, t in data.review_tallies() if pr.created in window]
        cited = sum(sum(bool(f.get("policy")) for f in t.get("findings", [])) for t in tallies)
        return Measurement.of(share(cited, len(tallies)), len(tallies))


class ConcurrentSessions(Indicator):
    id, stage, play, kind = "parallel.concurrent-sessions", "Build", "Parallel sessions and subagents", "leading"
    title, unit, better, needs = "Concurrent sessions per engineer", "sessions", "up", ("sessions",)

    def compute(self, data, window):
        peaks = defaultdict(int)
        by_user = defaultdict(list)
        for s in data.sessions:
            if s.start in window:
                by_user[s.user] += [(s.start, 1), (s.end, -1)]
        for user, events in by_user.items():
            live = 0
            for _, step in sorted(events, key=lambda e: (e[0], e[1])):
                live += step
                peaks[user] = max(peaks[user], live)
        return Measurement.of(median(list(peaks.values())), len(peaks), "median across engineers of their peak")


class Throughput(Indicator):
    id, stage, play, kind = "parallel.throughput", "Build", "Parallel sessions and subagents", "lagging"
    title, unit, better, needs = "Changes merged per engineer per week", "per week", "up", ("prs",)

    def compute(self, data, window):
        prs = implementation_prs(data, window)
        owners = Counter(p.merged_by if p.agent and p.merged_by else p.author for p in prs)
        rate = [n / window.weeks for n in owners.values()]
        rework = share(sum(p.rework_cycles() > 0 for p in prs), len(prs))
        detail = f"rework rate {rework:.0%}" if rework is not None else ""
        return Measurement.of(median(rate), len(owners), detail, {"reworkRate": rework})


class FirstPassCi(Indicator):
    id, stage, play, kind = "test.first-pass-ci", "Test", "Feedback loop", "leading"
    title, unit, better, needs = "Agent changes green on first CI run", "share", "up", ("prs", "runs")

    def compute(self, data, window):
        first = {}
        for run in sorted(data.runs, key=lambda r: r.created):
            if run.workflow == data.ci_workflow and run.event == "pull_request":
                first.setdefault(run.branch, run)
        agent = [p for p in data.prs if p.agent and p.created in window and p.branch in first]
        return Measurement.of(share(sum(first[p.branch].conclusion == "success" for p in agent), len(agent)), len(agent))


class ReviewTime(Indicator):
    id, stage, play, kind = "test.review-time", "Test", "Feedback loop", "lagging"
    title, unit, better, needs = "PR opened to approved", "hours", "down", ("prs",)

    def compute(self, data, window):
        times = []
        for p in implementation_prs(data, window):
            approved = min((r.time for r in p.reviews if r.state == "APPROVED"), default=p.merged)
            times.append(hours(approved - p.created))
        return Measurement.of(median(times), len(times), "median; merge time when there is no approval")


class ChangeFailureRate(Indicator):
    id, stage, play, kind = "test.change-failure-rate", "Test", "Feedback loop", "lagging"
    title, unit, better, needs = "Merged changes that caused an incident", "share", "down", ("prs", "incidents")

    def compute(self, data, window):
        prs = implementation_prs(data, window)
        causes = {i.caused_by for i in data.incidents}
        failed = sum(f"#{p.number}" in causes for p in prs)
        return Measurement.of(share(failed, len(prs)), len(prs), "incidents name their cause as `Caused-by: #<PR>`")


class EvalPassRate(Indicator):
    id, stage, play, kind = "evals.pass-rate", "Test", "Continuous evals", "leading"
    title, unit, better, needs = "Eval pass rate", "share", "up", ("eval_runs",)

    def compute(self, data, window):
        runs = sorted((r for r in data.eval_runs if r.time in window), key=lambda r: r.time)
        latest = f"latest {runs[-1].pass_rate:.0%}" if runs else ""
        return Measurement.of(mean([r.pass_rate for r in runs]), len(runs), latest)


class IncidentToEval(Indicator):
    id, stage, play, kind = "evals.incident-to-eval", "Test", "Continuous evals", "leading"
    title, unit, better, needs = "Incident opened to permanent eval", "days", "down", ("eval_cases", "incidents")

    def compute(self, data, window):
        opened = {i.id: i.opened for i in data.incidents}
        days = [hours(c.added - opened[c.incident]) / 24 for c in data.eval_cases if c.added in window and c.incident in opened]
        return Measurement.of(median(days), len(days), "median")


class RegressionsCaught(Indicator):
    id, stage, play, kind = "evals.regressions-caught", "Test", "Continuous evals", "lagging"
    title, unit, better, needs = "Regressions caught in CI rather than production", "share", "up", ("eval_runs", "incidents")

    def compute(self, data, window):
        ci = sum(r.time in window and r.event == "pull_request" and r.conclusion == "failure" for r in data.eval_runs)
        prod = sum("regression" in i.kind for i in production(data, window))
        return Measurement.of(share(ci, ci + prod), ci + prod, f"{ci} caught by evals, {prod} found in production")


class TimeToFirstReview(Indicator):
    id, stage, play, kind = "review.time-to-first-review", "Deploy", "AI in the PR review loop", "leading"
    title, unit, better, needs = "PR opened to first review", "minutes", "down", ("prs",)

    def compute(self, data, window):
        times = [hours(p.first_feedback() - p.created) * 60 for p in data.prs if p.created in window and p.first_feedback()]
        return Measurement.of(median(times), len(times), "median")


class AgentResolved(Indicator):
    id, stage, play, kind = "review.agent-resolved", "Deploy", "AI in the PR review loop", "leading"
    title, unit, better, needs = "Review comments resolved without a human touching the branch", "share", "up", ("prs",)

    def compute(self, data, window):
        reworked = [p for p in data.prs if p.merged in window and p.commits_after_feedback()]
        resolved = sum(all(c.author in data.agent_logins for c in p.commits_after_feedback()) for p in reworked)
        return Measurement.of(share(resolved, len(reworked)), len(reworked))


class CaughtVsEscaped(Indicator):
    id, stage, play, kind = "review.caught-vs-escaped", "Deploy", "AI in the PR review loop", "lagging"
    title, unit, better, needs = "Defects caught before merge rather than in production", "share", "up", ("prs", "incidents")

    def compute(self, data, window):
        caught = sum(int(t.get("important", 0)) for pr, t in data.review_tallies() if pr.created in window)
        escaped = sum(bool({"defect", "security", "regression"} & i.kind) for i in production(data, window))
        return Measurement.of(share(caught, caught + escaped), caught + escaped, f"{caught} important findings, {escaped} escaped")


class GateWaitTime(Indicator):
    id, stage, play, kind = "gates.wait", "Deploy", "Hooks as approval gates", "leading"
    title, unit, better, needs = "Time waiting on approval gates", "minutes", "down", ("gate_waits",)

    def compute(self, data, window):
        by_gate = defaultdict(list)
        for w in data.gate_waits:
            if w.created in window:
                by_gate[w.gate].append(hours(w.started - w.created) * 60)
        parts = {gate: median(values) for gate, values in by_gate.items()}
        everything = [v for values in by_gate.values() for v in values]
        blocks = f"; {sum(t in window for t in data.hook_blocks)} hook blocks" if data.hook_blocks is not None else ""
        return Measurement.of(median(everything), len(everything), "median per gate in parts" + blocks, parts)


class GateViolations(Indicator):
    id, stage, play, kind = "gates.violations", "Deploy", "Hooks as approval gates", "lagging"
    title, unit, better, needs = "Gate violations reaching production", "count", "down", ("incidents",)

    def compute(self, data, window):
        found = [i for i in production(data, window) if "gate-violation" in i.kind]
        return Measurement.of(float(len(found)), len(found))


class FailuresTriaged(Indicator):
    id, stage, play, kind = "cicd.failures-triaged", "Deploy", "CI/CD integration", "leading"
    title, unit, better, needs = "CI failures triaged by Claude", "share", "up", ("runs",)

    def compute(self, data, window):
        failed = {r.sha for r in data.runs if r.created in window and r.workflow == data.ci_workflow
                  and r.event == "pull_request" and r.conclusion == "failure"}
        triaged = {r.sha for r in data.runs if r.workflow == data.triage_workflow and r.conclusion == "success"}
        return Measurement.of(share(len(failed & triaged), len(failed)), len(failed))


class Dora(Indicator):
    id, stage, play, kind = "cicd.dora", "Deploy", "CI/CD integration", "lagging"
    title, unit, better, needs = "DORA: deploys per week", "per week", "up", ("deployments", "incidents")

    def compute(self, data, window):
        deploys = [d for d in data.deployments if d.time in window]
        lead = median([hours(d.time - d.commit_time) for d in deploys if d.commit_time])
        failed = sum(any(i.caused_by == d.sha for i in data.incidents) for d in deploys)
        restore = median([hours(i.resolved - i.opened) for i in production(data, window) if i.resolved])
        parts = {
            "deploysPerWeek": len(deploys) / window.weeks,
            "leadTimeHours": lead,
            "changeFailureRate": share(failed, len(deploys)),
            "timeToRestoreHours": restore,
        }
        return Measurement.of(parts["deploysPerWeek"] if deploys else None, len(deploys), "lead time, failure rate and restore time in parts", parts)


class BreachToIntent(Indicator):
    id, stage, play, kind = "maintain.breach-to-intent", "Maintain", "Closing the loop", "leading"
    title, unit, better, needs = "Band breach to intent.md in the triage queue", "minutes", "down", ("prs",)

    def compute(self, data, window):
        times = []
        for p in data.prs:
            for breach in markers(p.body, "breach"):
                detected = parse_time(breach.get("detectedAt"))
                if detected and p.created in window:
                    times.append(hours(p.created - detected) * 60)
        return Measurement.of(median(times), len(times), "median")


class FindingsToFixes(Indicator):
    id, stage, play, kind = "maintain.findings-to-fixes", "Maintain", "Closing the loop", "lagging"
    title, unit, better, needs = "Monitor findings that became merged fixes", "share", "up", ("prs", "changes")

    def compute(self, data, window):
        breaches = [p for p in data.prs if markers(p.body, "breach") and p.created in window]
        implemented = {c.id for c in data.changes if c.first_with_status("plan", "implemented")}
        fixed = sum(
            p.merged is not None and (p.implementation or any(f.split("/")[1] in implemented for f in p.files if f.startswith("changes/")))
            for p in breaches
        )
        dismissed = sum(p.merged is None and p.closed is not None for p in breaches)
        return Measurement.of(share(fixed, len(breaches)), len(breaches), f"{fixed} fixed, {dismissed} dismissed")


class RepeatIncidents(Indicator):
    id, stage, play, kind = "maintain.repeat-incidents", "Maintain", "Closing the loop", "lagging"
    title, unit, better, needs = "Repeat incidents of the same class", "count", "down", ("incidents",)

    def compute(self, data, window):
        earlier = {i.incident_class for i in data.incidents if i.opened < window.start and i.incident_class}
        seen, repeats = set(earlier), 0
        for i in sorted(production(data, window), key=lambda i: i.opened):
            if i.incident_class:
                repeats += i.incident_class in seen
                seen.add(i.incident_class)
        return Measurement.of(float(repeats), len(production(data, window)))


class ScanCoverage(Indicator):
    id, stage, play, kind = "security.scan-coverage", "Maintain", "Recurring codebase scans", "leading"
    title, unit, better, needs = "Repositories on a scan schedule", "share", "up", ("security_repos",)

    def compute(self, data, window):
        repos = data.security_repos
        return Measurement.of(share(sum(r.scheduled for r in repos), len(repos)), len(repos))


class FindingToPatch(Indicator):
    id, stage, play, kind = "security.finding-to-patch", "Maintain", "Recurring codebase scans", "leading"
    title, unit, better, needs = "Finding reported to patch in the review gate", "hours", "down", ("security_findings", "prs")

    def compute(self, data, window):
        times = []
        for f in data.security_findings:
            pr = data.pr_by_number(f.patch_pr) if f.patch_pr else None
            if pr and pr.created in window:
                times.append(hours(pr.created - f.reported))
        return Measurement.of(median(times), len(times), "median")


class ScanVsProduction(Indicator):
    id, stage, play, kind = "security.scan-vs-production", "Maintain", "Recurring codebase scans", "lagging"
    title, unit, better, needs = "Vulnerabilities found by scans rather than production", "share", "up", ("security_findings", "incidents")

    def compute(self, data, window):
        scanned = sum(f.reported in window for f in data.security_findings)
        outside = sum("security" in i.kind for i in data.incidents if i.opened in window and i.found_in in ("production", "external"))
        return Measurement.of(share(scanned, scanned + outside), scanned + outside, f"{scanned} by scans, {outside} in production or reported externally")


class FindingsPerScan(Indicator):
    id, stage, play, kind = "security.findings-per-scan", "Maintain", "Recurring codebase scans", "lagging"
    title, unit, better, needs = "Findings per scan", "per scan", "down", ("security_findings",)

    def compute(self, data, window):
        per_scan = Counter(f.scan for f in data.security_findings if f.reported in window and f.scan)
        return Measurement.of(mean([float(n) for n in per_scan.values()]), len(per_scan))


INDICATORS: list[Indicator] = [
    IntentCaptureTime(), IntentSurvival(), IntentEditsAfterSpec(),
    IntentToSpec(), SpecReworkAfterPlan(),
    FirstPassMerge(), PlanToMerge(), ReworkCycles(), PlanMatch(),
    RepeatFindings(), NewJoinerFirstMerge(),
    PolicyToSkill(), PolicyFindings(),
    ConcurrentSessions(), Throughput(),
    FirstPassCi(), ReviewTime(), ChangeFailureRate(),
    EvalPassRate(), IncidentToEval(), RegressionsCaught(),
    TimeToFirstReview(), AgentResolved(), CaughtVsEscaped(),
    GateWaitTime(), GateViolations(),
    FailuresTriaged(), Dora(),
    BreachToIntent(), FindingsToFixes(), RepeatIncidents(),
    ScanCoverage(), FindingToPatch(), ScanVsProduction(), FindingsPerScan(),
]


class TicketLeadTime(Indicator):
    id, stage, play, kind = "proxy.ticket-lead-time", "Plan", "Baseline proxy", "lagging"
    title, unit, better, needs = "Ticket opened to closed", "days", "down", ("tickets",)
    note = "Tracker proxy for the whole loop, comparable before and after adoption."

    def compute(self, data, window):
        days = [hours(t.closed - t.opened) / 24 for t in data.tickets if t.closed in window]
        return Measurement.of(median(days), len(days), "median")


class TicketToFirstPr(Indicator):
    id, stage, play, kind = "proxy.ticket-to-first-pr", "Design", "Baseline proxy", "leading"
    title, unit, better, needs = "Ticket opened to first pull request", "days", "down", ("tickets", "prs")
    note = "Tracker proxy for intent-to-spec and plan time, comparable before and after adoption."

    def compute(self, data, window):
        days = []
        for ticket in data.tickets:
            opened = [p.created for n in ticket.prs if (p := data.pr_by_number(n))]
            if opened and min(opened) in window:
                days.append(hours(min(opened) - ticket.opened) / 24)
        return Measurement.of(median(days), len(days), "median")


class Interventions(Indicator):
    id, stage, play, kind = "small-team.interventions", "Build", "Small teams", "lagging"
    title, unit, better, needs = "Human commits on agent pull requests", "per PR", "down", ("prs",)
    note = "Counts commits by a GitHub login outside metrics.agents.logins on merged agent pull requests."

    def compute(self, data, window):
        prs = [p for p in data.prs if p.agent and p.merged in window]
        counts = [sum(bool(c.author) and c.author not in data.agent_logins for c in p.commits) for p in prs]
        return Measurement.of(mean(counts), len(counts), f"{sum(map(bool, counts))} of {len(counts)} needed a person")


class Ceremony(Indicator):
    id, stage, play, kind = "small-team.ceremony", "Deploy", "Small teams", "leading"
    title, unit, better, needs = "Approvals labelled as ceremony", "share", "down", ("prs",)
    note = "Label a pull request `ceremony` when approving it taught you nothing."

    def compute(self, data, window):
        approved = [p for p in data.prs if p.merged in window and any(r.state == "APPROVED" for r in p.reviews)]
        return Measurement.of(share(sum("ceremony" in p.labels for p in approved), len(approved)), len(approved))


@dataclass(frozen=True)
class Supplement:
    key: str
    title: str
    summary: str
    indicators: list[Indicator]


SUPPLEMENTS: list[Supplement] = [
    Supplement("proxies", "Baseline proxies", "Tracker measures that mean the same before and after adoption.",
               [TicketLeadTime(), TicketToFirstPr()]),
    Supplement("smallTeam", "Small teams", "Where a team of one or two still steps in, and which approvals it could drop.",
               [Interventions(), Ceremony()]),
]
