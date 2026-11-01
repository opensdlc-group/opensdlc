# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from .records import (
    ChangeHistory, Deployment, EvalCase, EvalRun, GateWait, Incident, PullRequest, Run,
    SecurityFinding, SecurityRepo, Session, Ticket,
)

MARKER = re.compile(r"<!--\s*opensdlc:(?P<kind>[\w-]+)\s+(?P<json>\{.*?\})\s*-->", re.S)


def markers(text: str, kind: str) -> list[dict]:
    found = []
    for match in MARKER.finditer(text or ""):
        if match.group("kind") == kind:
            try:
                found.append(json.loads(match.group("json")))
            except json.JSONDecodeError:
                continue
    return found


@dataclass
class Dataset:
    changes: list[ChangeHistory] | None = None
    agents_md_commits: list[datetime] | None = None
    prs: list[PullRequest] | None = None
    runs: list[Run] | None = None
    gate_waits: list[GateWait] | None = None
    deployments: list[Deployment] | None = None
    incidents: list[Incident] | None = None
    eval_runs: list[EvalRun] | None = None
    eval_cases: list[EvalCase] | None = None
    sessions: list[Session] | None = None
    hook_blocks: list[datetime] | None = None
    security_findings: list[SecurityFinding] | None = None
    security_repos: list[SecurityRepo] | None = None
    team: dict[str, datetime] | None = None
    tickets: list[Ticket] | None = None
    ci_workflow: str = "CI"
    triage_workflow: str = "OpenSDLC CI triage"
    evals_workflow: str = "OpenSDLC evals"
    agent_logins: frozenset[str] = frozenset()
    unavailable: dict[str, str] = field(default_factory=dict)

    def review_tallies(self) -> list[tuple[PullRequest, dict]]:
        tallies = []
        for pr in self.prs or []:
            for comment in reversed(pr.comments):
                found = markers(comment.body, "review")
                if found:
                    tallies.append((pr, found[-1]))
                    break
        return tallies

    def pr_by_number(self, number: int) -> PullRequest | None:
        return next((p for p in self.prs or [] if p.number == number), None)
