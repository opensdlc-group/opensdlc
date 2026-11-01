# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
import subprocess
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from ..artifacts import KINDS, Artifact
from ..document import FRONTMATTER, content_hash
from ..knowledge import plan_files
from ..config import CHANGES_DIR
from .dataset import Dataset
from .records import (
    ArtifactCommit, ChangeHistory, Comment, Commit, Deployment, EvalCase, EvalRun, GateWait, Incident,
    PullRequest, Review, Run, SecurityFinding, SecurityRepo, Session, Ticket, parse_time,
)

Shell = Callable[[list[str], Path], str]
CAUSED_BY = re.compile(r"Caused-by:\s*(#\d+|[0-9a-f]{7,40})", re.I)


class SourceError(Exception):
    pass


def run_shell(args: list[str], cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise SourceError(f"{' '.join(args[:3])}: {(result.stderr or result.stdout).strip()[:300]}")
    return result.stdout


def optional_time(value: str) -> datetime | None:
    try:
        return parse_time(value) if value and not value.startswith("<") else None
    except ValueError:
        return None


class Source(ABC):
    fields: tuple[str, ...]

    def __init__(self, root: Path, config: dict, since: datetime, shell: Shell = run_shell):
        self.root = root
        self.config = config
        self.since = since
        self.shell = shell

    def fill(self, data: Dataset) -> None:
        try:
            self.load(data)
        except (SourceError, json.JSONDecodeError, KeyError, ValueError, subprocess.TimeoutExpired) as error:
            for name in self.fields:
                setattr(data, name, None)
                data.unavailable[name] = f"{self.describe()} failed: {error}"

    def describe(self) -> str:
        return type(self).__name__

    @abstractmethod
    def load(self, data: Dataset) -> None: ...


class GitSource(Source):
    fields = ("changes", "agents_md_commits", "eval_cases")

    def git(self, *args: str) -> str:
        return self.shell(["git", *args], self.root)

    def history(self, path: str) -> list[ArtifactCommit]:
        commits = []
        for line in reversed(self.git("log", "--format=%H%x09%cI", "--", path).splitlines()):
            sha, when = line.split("\t")
            try:
                text = self.git("show", f"{sha}:{path}")
            except SourceError:
                continue
            match = FRONTMATTER.match(text)
            status = re.search(r"^status:\s*(\S+)", match.group(1), re.M) if match else None
            commits.append(ArtifactCommit(parse_time(when), status.group(1) if status else "", content_hash(text)))
        return commits

    def load(self, data: Dataset) -> None:
        changes = []
        for folder in sorted(p for p in (self.root / CHANGES_DIR).glob("*") if p.is_dir()):
            history = ChangeHistory(id=folder.name)
            for kind in KINDS.values():
                file = folder / kind.filename
                if file.is_file():
                    history.artifacts[kind.name] = self.history(f"{CHANGES_DIR}/{folder.name}/{kind.filename}")
                    artifact = Artifact.read(kind, file)
                    if kind.name == "intent":
                        history.source = artifact.meta.get("source", "")
                        history.started = optional_time(artifact.meta.get("started", ""))
                    if kind.name == "plan":
                        history.plan_files = plan_files(artifact.section("Files that change"))
            changes.append(history)
        data.changes = changes
        data.agents_md_commits = [parse_time(t) for t in self.git("log", "--format=%cI", "--", "AGENTS.md", "CLAUDE.md").split()]
        cases = []
        for case_file in sorted((self.root / "evals" / "cases").glob("*.json")):
            case = json.loads(case_file.read_text())
            added = self.git("log", "--diff-filter=A", "--format=%cI", "--", case_file.relative_to(self.root).as_posix()).split()
            if case.get("incident") and added:
                cases.append(EvalCase(case["id"], str(case["incident"]), parse_time(added[-1])))
        data.eval_cases = cases


class GitHubSource(Source):
    fields = ("prs", "runs", "gate_waits", "deployments", "eval_runs")
    PR_FIELDS = "number,author,createdAt,mergedAt,closedAt,mergedBy,headRefName,body,labels,files,commits,reviews,comments"

    def gh(self, *args: str):
        return json.loads(self.shell(["gh", *args], self.root) or "null")

    @property
    def day(self) -> str:
        return self.since.date().isoformat()

    def agent(self, pr: dict) -> bool:
        agents = self.config.get("agents", {})
        return (
            (pr.get("author") or {}).get("login") in agents.get("logins", [])
            or any(pr["headRefName"].startswith(p) for p in agents.get("branchPrefixes", []))
            or any(label["name"] in agents.get("labels", []) for label in pr.get("labels", []))
        )

    def pull_request(self, raw: dict) -> PullRequest:
        login = lambda value: (value or {}).get("login", "")
        return PullRequest(
            number=raw["number"],
            author=login(raw.get("author")),
            created=parse_time(raw["createdAt"]),
            merged=parse_time(raw.get("mergedAt")),
            closed=parse_time(raw.get("closedAt")),
            merged_by=login(raw.get("mergedBy")),
            branch=raw["headRefName"],
            body=raw.get("body") or "",
            labels=[label["name"] for label in raw.get("labels", [])],
            files=[f["path"] for f in raw.get("files", [])],
            commits=[Commit(login((c.get("authors") or [{}])[0]), parse_time(c["committedDate"]), c.get("messageHeadline", ""))
                     for c in raw.get("commits", [])],
            reviews=[Review(login(r.get("author")), r["state"], parse_time(r["submittedAt"])) for r in raw.get("reviews", []) if r.get("submittedAt")],
            comments=[Comment(login(c.get("author")), parse_time(c["createdAt"]), c.get("body", "")) for c in raw.get("comments", [])],
            agent=self.agent(raw),
        )

    def runs(self, *workflow: str) -> list[dict]:
        args = ["run", "list", "--limit", "1000", "--created", f">={self.day}",
                "--json", "databaseId,workflowName,event,headBranch,headSha,createdAt,conclusion"]
        return self.gh(*args, *(["--workflow", workflow[0]] if workflow else []))

    def gate_waits(self, repo: str) -> list[GateWait]:
        waits = []
        for gate in self.config.get("gates", []):
            for run in self.runs(gate["workflow"]):
                jobs = self.gh("api", f"repos/{repo}/actions/runs/{run['databaseId']}/jobs")["jobs"]
                for job in jobs:
                    if job["name"] == gate["job"] and job.get("started_at"):
                        waits.append(GateWait(gate["name"], parse_time(job["created_at"]), parse_time(job["started_at"])))
        return waits

    def commit_time(self, sha: str) -> datetime | None:
        try:
            return parse_time(self.shell(["git", "show", "-s", "--format=%cI", sha], self.root).strip())
        except SourceError:
            return None

    def deployments(self, repo: str) -> list[Deployment]:
        environment = self.config.get("deployEnvironment", "production")
        found = []
        for deployment in self.gh("api", f"repos/{repo}/deployments?environment={environment}&per_page=100"):
            created = parse_time(deployment["created_at"])
            if created < self.since:
                continue
            statuses = self.gh("api", f"repos/{repo}/deployments/{deployment['id']}/statuses?per_page=1")
            if statuses and statuses[0]["state"] == "success":
                found.append(Deployment(deployment["sha"], created, self.commit_time(deployment["sha"])))
        return found

    def eval_runs(self, workflow: str) -> list[EvalRun]:
        found = []
        for run in self.runs(workflow):
            with tempfile.TemporaryDirectory() as folder:
                try:
                    self.shell(["gh", "run", "download", str(run["databaseId"]), "-n", "opensdlc-evals", "-D", folder], self.root)
                except SourceError:
                    continue
                report = next(Path(folder).rglob("evals.json"), None)
                if report:
                    found.append(EvalRun(parse_time(run["createdAt"]), json.loads(report.read_text())["passRate"], run["event"], run["conclusion"]))
        return found

    def load(self, data: Dataset) -> None:
        repo = self.gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
        raw = self.gh("pr", "list", "--state", "all", "--limit", "1000", "--search", f"updated:>={self.day}", "--json", self.PR_FIELDS)
        data.prs = [self.pull_request(p) for p in raw]
        data.runs = [Run(r["databaseId"], r["workflowName"], r["event"], r["headBranch"], r["headSha"], parse_time(r["createdAt"]), r["conclusion"] or "")
                     for r in self.runs()]
        data.gate_waits = self.gate_waits(repo) if self.config.get("gates") else None
        data.deployments = self.deployments(repo)
        data.eval_runs = self.eval_runs(data.evals_workflow)


class IncidentSource(Source):
    fields = ("incidents",)

    def from_issues(self) -> list[Incident]:
        spec = self.config["incidents"]
        raw = json.loads(self.shell(["gh", "issue", "list", "--label", spec.get("label", "incident"), "--state", "all", "--limit", "1000",
                                     "--json", "number,createdAt,closedAt,labels,body"], self.root))
        incidents = []
        for issue in raw:
            labels = [label["name"] for label in issue.get("labels", [])]
            prefixed = {name.split(":", 1)[0]: name.split(":", 1)[1] for name in labels if ":" in name}
            cause = CAUSED_BY.search(issue.get("body") or "")
            incidents.append(Incident(
                id=f"#{issue['number']}",
                opened=parse_time(issue["createdAt"]),
                resolved=parse_time(issue.get("closedAt")),
                found_in=prefixed.get("found-in", ""),
                kind=frozenset(name for name in labels if ":" not in name),
                incident_class=prefixed.get("class", ""),
                caused_by=cause.group(1) if cause else "",
            ))
        return incidents

    def from_command(self) -> list[Incident]:
        raw = json.loads(self.shell(self.config["incidents"]["run"], self.root))
        return [Incident(str(i["id"]), parse_time(i["opened"]), parse_time(i.get("resolved")), i.get("foundIn", ""),
                         frozenset(i.get("kind", [])), i.get("class", ""), i.get("causedBy", "")) for i in raw]

    def load(self, data: Dataset) -> None:
        kind = self.config.get("incidents", {}).get("type")
        if kind:
            data.incidents = self.from_issues() if kind == "github-issues" else self.from_command()


class CommandSource(Source):
    key: tuple[str, str]
    field: str

    @property
    def fields(self) -> tuple[str, ...]:
        return (self.field,)

    def describe(self) -> str:
        return f"metrics.{'.'.join(self.key)}"

    @abstractmethod
    def parse(self, raw: list) -> list: ...

    def load(self, data: Dataset) -> None:
        spec = self.config.get(self.key[0], {}).get(self.key[1])
        if spec:
            setattr(data, self.field, self.parse(json.loads(self.shell(spec["run"], self.root))))


class SessionsSource(CommandSource):
    key, field = ("otel", "sessions"), "sessions"

    def parse(self, raw):
        return [Session(s["user"], parse_time(s["start"]), parse_time(s["end"])) for s in raw]


class HookBlocksSource(CommandSource):
    key, field = ("otel", "hookBlocks"), "hook_blocks"

    def parse(self, raw):
        return [parse_time(t) for t in raw]


class SecurityFindingsSource(CommandSource):
    key, field = ("security", "findings"), "security_findings"

    def parse(self, raw):
        return [SecurityFinding(str(f["id"]), parse_time(f["reported"]), f.get("scan", ""), f.get("patchPr")) for f in raw]


class SecurityReposSource(CommandSource):
    key, field = ("security", "repositories"), "security_repos"

    def parse(self, raw):
        return [SecurityRepo(r["name"], bool(r["scheduled"])) for r in raw]


class TicketSource(Source):
    fields = ("tickets",)

    def load(self, data: Dataset) -> None:
        label = self.config.get("baseline", {}).get("issueLabel")
        if not label:
            return
        raw = json.loads(self.shell(["gh", "issue", "list", "--label", label, "--state", "all", "--limit", "1000",
                                     "--search", f"created:>={self.since.date().isoformat()}",
                                     "--json", "number,createdAt,closedAt,closedByPullRequestsReferences"], self.root))
        data.tickets = [Ticket(i["number"], parse_time(i["createdAt"]), parse_time(i.get("closedAt")),
                               tuple(pr["number"] for pr in i.get("closedByPullRequestsReferences") or []))
                        for i in raw]


SOURCES: list[type[Source]] = [
    GitSource, GitHubSource, IncidentSource, SessionsSource, HookBlocksSource, SecurityFindingsSource, SecurityReposSource, TicketSource,
]


def collect(root: Path, config: dict, since: datetime, shell: Shell = run_shell) -> Dataset:
    metrics = config.get("metrics", {})
    data = Dataset(
        ci_workflow=metrics.get("ciWorkflow", "CI"),
        agent_logins=frozenset(metrics.get("agents", {}).get("logins", [])),
        team={login: parse_time(day) for login, day in metrics["team"].items()} if metrics.get("team") else None,
    )
    history_since = since - timedelta(days=180)
    for source in SOURCES:
        start = history_since if source is IncidentSource else since
        source(root, metrics, start, shell).fill(data)
    return data
