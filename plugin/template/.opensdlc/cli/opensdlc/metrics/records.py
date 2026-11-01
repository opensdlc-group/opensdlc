# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from datetime import datetime, timezone


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def __contains__(self, moment: datetime | None) -> bool:
        return moment is not None and self.start <= moment < self.end

    @property
    def weeks(self) -> float:
        return (self.end - self.start).total_seconds() / 604800


@dataclass(frozen=True)
class ArtifactCommit:
    time: datetime
    status: str
    hash: str


@dataclass
class ChangeHistory:
    id: str
    source: str = ""
    started: datetime | None = None
    plan_files: list[str] = field(default_factory=list)
    artifacts: dict[str, list[ArtifactCommit]] = field(default_factory=dict)

    def commits(self, kind: str) -> list[ArtifactCommit]:
        return self.artifacts.get(kind, [])

    def first(self, kind: str) -> datetime | None:
        commits = self.commits(kind)
        return commits[0].time if commits else None

    def first_with_status(self, kind: str, *statuses: str) -> datetime | None:
        return next((c.time for c in self.commits(kind) if c.status in statuses), None)

    def content_edits_after(self, kind: str, moment: datetime | None) -> int:
        if moment is None:
            return 0
        edits, previous = 0, None
        for commit in self.commits(kind):
            if previous is not None and commit.hash != previous and commit.time > moment:
                edits += 1
            previous = commit.hash
        return edits


@dataclass(frozen=True)
class Commit:
    author: str
    time: datetime
    message: str = ""


@dataclass(frozen=True)
class Review:
    author: str
    state: str
    time: datetime


@dataclass(frozen=True)
class Comment:
    author: str
    time: datetime
    body: str


@dataclass
class PullRequest:
    number: int
    author: str
    created: datetime
    merged: datetime | None = None
    closed: datetime | None = None
    merged_by: str = ""
    branch: str = ""
    body: str = ""
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    commits: list[Commit] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    agent: bool = False

    @property
    def implementation(self) -> bool:
        return any(not f.startswith("changes/") for f in self.files)

    def feedback(self) -> list[datetime]:
        times = [r.time for r in self.reviews if r.author != self.author]
        times += [c.time for c in self.comments if c.author != self.author]
        return sorted(times)

    def first_feedback(self) -> datetime | None:
        return next(iter(self.feedback()), None)

    def rework_cycles(self) -> int:
        rounds = self.feedback()
        bounds = rounds[1:] + [datetime.max.replace(tzinfo=timezone.utc)]
        return sum(any(start < c.time < end for c in self.commits) for start, end in zip(rounds, bounds))

    def commits_after_feedback(self) -> list[Commit]:
        first = self.first_feedback()
        return [c for c in self.commits if first and c.time > first]


@dataclass(frozen=True)
class Run:
    id: int
    workflow: str
    event: str
    branch: str
    sha: str
    created: datetime
    conclusion: str


@dataclass(frozen=True)
class GateWait:
    gate: str
    created: datetime
    started: datetime


@dataclass(frozen=True)
class Deployment:
    sha: str
    time: datetime
    commit_time: datetime | None


@dataclass(frozen=True)
class Incident:
    id: str
    opened: datetime
    resolved: datetime | None = None
    found_in: str = ""
    kind: frozenset[str] = frozenset()
    incident_class: str = ""
    caused_by: str = ""


@dataclass(frozen=True)
class EvalRun:
    time: datetime
    pass_rate: float
    event: str
    conclusion: str


@dataclass(frozen=True)
class EvalCase:
    id: str
    incident: str
    added: datetime


@dataclass(frozen=True)
class Session:
    user: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class SecurityFinding:
    id: str
    reported: datetime
    scan: str = ""
    patch_pr: int | None = None


@dataclass(frozen=True)
class SecurityRepo:
    name: str
    scheduled: bool


@dataclass(frozen=True)
class Ticket:
    number: int
    opened: datetime
    closed: datetime | None
    prs: tuple[int, ...]
