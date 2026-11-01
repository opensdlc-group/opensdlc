# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .artifacts import KINDS, READY, Artifact, Change
from .config import CHANGES_DIR
from .document import Document
from .gitio import Git
from .knowledge import Knowledge

Shell = Callable[[list[str]], str]


def gh(args: list[str], token: str | None) -> str:
    env = {**os.environ, "GH_TOKEN": token} if token else None
    result = subprocess.run(["gh", *args], capture_output=True, text=True, env=env, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {(result.stderr or result.stdout).strip()[:300]}")
    return result.stdout


def run_gh(args: list[str]) -> str:
    return gh(args, None)


def run_org_gh(args: list[str]) -> str:
    return gh(args, os.environ.get("OPENSDLC_ORG_TOKEN"))


@dataclass(frozen=True)
class Requirement:
    subject: str
    group: str
    entries: tuple[str, ...]
    reason: str


class Directory:
    def __init__(self, shell: Shell = run_org_gh):
        self.shell = shell
        self.cache: dict[str, frozenset[str]] = {}

    def members(self, entry: str) -> frozenset[str]:
        name = entry.lstrip("@")
        if "/" not in name:
            return frozenset({name.lower()})
        if name not in self.cache:
            org, team = name.split("/", 1)
            try:
                logins = self.shell(["api", f"orgs/{org}/teams/{team}/members", "--paginate", "--jq", ".[].login"]).split()
            except RuntimeError as error:
                raise RuntimeError(f"Cannot read members of {entry}: {error}. Set OPENSDLC_ORG_TOKEN to a token that can read team membership, or list logins in approvals.groups.") from error
            self.cache[name] = frozenset(login.lower() for login in logins)
        return self.cache[name]

    def resolve(self, entries: tuple[str, ...]) -> frozenset[str]:
        return frozenset().union(*(self.members(e) for e in entries)) if entries else frozenset()


class ApprovalRules:
    def __init__(self, root: Path, config: dict, base: str, knowledge: Knowledge):
        self.root = root
        self.config = config
        self.base = base
        self.git = Git(root)
        self.knowledge = knowledge
        self.groups = config.get("approvals", {}).get("groups", {})
        self.rules = config.get("approvals", {}).get("rules", {})

    def group(self, name: str, subject: str, reason: str) -> Requirement:
        return Requirement(subject, name, tuple(self.groups.get(name, [])), reason)

    def proposed(self, path: str) -> Artifact | None:
        kind = KINDS.get(Path(path).stem)
        file = self.root / path
        if kind is None or not file.is_file():
            return None
        head = Artifact.read(kind, file)
        if head.status not in READY:
            return None
        before = self.git.show(self.base, path)
        if before is None:
            return head
        base = Artifact.parse(kind, file, before)
        return head if base.status not in READY or base.hash != head.hash else None

    def for_artifact(self, path: str, artifact: Artifact) -> list[Requirement]:
        rule = self.rules.get(artifact.kind.name, {})
        names = list(rule.get("require", []))
        if artifact.risk == "high":
            names += rule.get("high", [])
        found = [self.group(n, path, f"{artifact.kind.name} with risk {artifact.risk or 'n/a'}") for n in names]
        if artifact.kind.name == "spec":
            owners, _ = self.knowledge.concern_owners(Change.load((self.root / path).parent))
            found += [Requirement(path, f"owner of {policy}", (owner,), f"Concerns cite {policy}") for policy, owner in owners.items()]
        return found

    def for_knowledge(self, path: str) -> list[Requirement]:
        before = self.git.show(self.base, path)
        file = self.root / path
        current = Document.read(file) if file.is_file() else None
        document = Document.parse(file, before) if before is not None else current
        if document is None or not document.meta.get("kind") or not document.meta.get("owner"):
            return []
        return [Requirement(path, "document owner", (document.meta["owner"],), "knowledge documents change with their owner's approval")]

    def requirements(self, changed: list[str]) -> list[Requirement]:
        sources = tuple(self.config.get("knowledge", {}).get("sources", ["knowledge/"]))
        found = []
        for path in changed:
            if path.startswith(f"{CHANGES_DIR}/") and path.endswith(".md"):
                artifact = self.proposed(path)
                if artifact:
                    found += self.for_artifact(path, artifact)
            elif path.startswith(sources) and path.endswith(".md"):
                found += self.for_knowledge(path)
        return found


@dataclass(frozen=True)
class Verdict:
    requirement: Requirement
    approvers: tuple[str, ...]

    @property
    def met(self) -> bool:
        return bool(self.approvers)


def person(actor: dict | None) -> str | None:
    actor = actor or {}
    login = actor.get("login", "").lower()
    return None if not login or actor.get("is_bot") or login.endswith("[bot]") else login


def approvers(pr: dict, excluded: frozenset[str]) -> frozenset[str]:
    agents = {login.lower().removesuffix("[bot]") for login in excluded}
    latest = {}
    for review in sorted(pr.get("reviews", []), key=lambda r: r.get("submittedAt") or ""):
        login = person(review.get("author"))
        if login and review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            current = (review.get("commit") or {}).get("oid") == pr.get("headRefOid")
            latest[login] = review["state"] if current else "STALE"
    author = (pr.get("author") or {}).get("login", "").lower().removesuffix("[bot]")
    return frozenset(login for login, state in latest.items() if state == "APPROVED" and login != author and login not in agents)


def evaluate(requirements: list[Requirement], approved: frozenset[str], directory: Directory) -> list[Verdict]:
    return [Verdict(r, tuple(sorted(approved & directory.resolve(r.entries)))) for r in requirements]


def report(verdicts: list[Verdict]) -> str:
    if not verdicts:
        return "### OpenSDLC approvals\n\nNothing in this PR needs acceptance approval."
    lines = ["### OpenSDLC approvals", "", "| | Subject | Needs | Why | Approved by |", "| :- | :- | :- | :- | :- |"]
    for v in verdicts:
        lines.append(f"| {'✅' if v.met else '❌'} | `{v.requirement.subject}` | {v.requirement.group} ({', '.join(v.requirement.entries) or 'no members configured'}) | {v.requirement.reason} | {', '.join(v.approvers) or '–'} |")
    return "\n".join(lines)


def required_reviewers(requirements: list[Requirement]) -> tuple[list[str], list[str]]:
    users, teams = set(), set()
    for requirement in requirements:
        for entry in requirement.entries:
            name = entry.lstrip("@")
            (teams if "/" in name else users).add(name.split("/", 1)[1] if "/" in name else name)
    return sorted(users), sorted(teams)


def pull_request(number: int, shell: Shell = run_gh) -> dict:
    return json.loads(shell(["pr", "view", str(number), "--json", "author,reviews,baseRefOid,headRefOid"]))
