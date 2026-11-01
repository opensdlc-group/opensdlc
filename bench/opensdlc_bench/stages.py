# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field

from opensdlc.artifacts import Change
from opensdlc.globs import matches
from opensdlc.knowledge import Knowledge
from opensdlc.pipeline import STAGES, role_model
from opensdlc.reviewing import Tally

from .agent import Agent, AgentRun
from .model import Target, Ticket
from .workspace import Workspace

INTAKE_TOOLS = "Read,Glob,Grep,Skill,Edit(changes/**),Edit(.opensdlc/out/escalate.md)"
REVIEW_TOOLS = "Read,Edit(.opensdlc/out/**),Glob,Grep,Agent,Skill,Bash(git diff *),Bash(git log *),Bash(git show *),Bash(git merge-base *),Bash(git rev-parse *)"
TURNS = {"intake": 30, "spec": 80, "plan": 80, "build": 80, "review": 60, "fix": 80, "gate": 60}
GATE_TOOLS = {stage.name: stage.gate_tools for stage in STAGES}
INTENT_PATH = re.compile(r"^changes/([a-z0-9][a-z0-9-]*)/intent\.md$")


@dataclass
class Settings:
    max_turns: int | None = None
    fix_rounds: int = 1

    def turns(self, stage: str) -> int:
        return min(TURNS[stage], self.max_turns) if self.max_turns else TURNS[stage]


@dataclass
class StageRecord:
    stage: str
    status: str = "ok"
    runs: list[AgentRun] = field(default_factory=list)
    notes: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def block(self, problem: str) -> "StageRecord":
        self.status = "blocked"
        self.problems.append(problem)
        return self


@dataclass
class Context:
    workspace: Workspace
    agent: Agent
    target: Target
    ticket: Ticket
    number: int
    settings: Settings
    review_keys: Counter
    change: str | None = None
    base: str = ""
    findings: list[str] = field(default_factory=list)

    def config(self) -> dict:
        return json.loads((self.workspace.root / ".opensdlc" / "config.json").read_text())

    def tools(self, stage: str) -> str:
        return self.config()["stages"][stage]["allowedTools"]

    def model(self, role: str) -> str:
        return role_model(self.config(), role)


class Stage(ABC):
    name: str

    @abstractmethod
    def run(self, ctx: Context) -> StageRecord: ...

    def call(self, ctx: Context, record: StageRecord, prompt: str, tools: str, role: str = "") -> str | None:
        escalation = ctx.workspace.out("escalate.md")
        escalation.unlink(missing_ok=True)
        run = ctx.agent.run(prompt, ctx.workspace.root, tools, ctx.settings.turns(role or self.name), ctx.model(role or self.name))
        record.runs.append(run)
        if not run.ok:
            record.problems.append(f"agent run ended with {run.error}")
        if not escalation.is_file():
            return None
        if not role:
            record.notes.setdefault("raisedBy", "author")
        return escalation.read_text()

    def propose(self, ctx: Context, record: StageRecord, prompt: str, tools: str, change: str, allow: str) -> tuple[bool, str | None]:
        workspace = ctx.workspace
        pristine = workspace.snapshot()
        escalated = self.call(ctx, record, prompt, tools)
        patch = workspace.capture(pristine)
        workspace.reset()
        applied = workspace.apply(patch, change, allow)
        if not applied.ok:
            record.problems.append(f"patch refused: {applied.output[-500:]}")
        return applied.ok, escalated

    def judge(self, ctx: Context, record: StageRecord) -> str | None:
        workspace = ctx.workspace
        for name in ("gate.json", "verify.md", "gate-report.md"):
            workspace.out(name).unlink(missing_ok=True)
        tools = GATE_TOOLS[self.name](ctx.config())
        self.call(ctx, record, f"/opensdlc:gate changes/{ctx.change} {self.name} (headless)", tools, "gate")
        workspace.restore()
        checked = workspace.opensdlc("gate-check", "--stage", self.name, "--change", ctx.change)
        verdict = json.loads(checked.output) if checked.ok else {"escalate": True, "reasons": [checked.output[-300:]]}
        record.notes["gate"] = "escalate" if verdict["escalate"] else "continue"
        if not verdict["escalate"]:
            return None
        record.notes["gateEscalations"] = record.notes.get("gateEscalations", 0) + 1
        record.notes.setdefault("raisedBy", "gate")
        return "\n".join(f"- {r}" for r in verdict["reasons"])

    def settle(self, ctx: Context, record: StageRecord, tools: str) -> bool:
        checked = ctx.workspace.opensdlc("check")
        if checked.ok:
            return True
        record.notes["checkRepairs"] = record.notes.get("checkRepairs", 0) + 1
        prompt = (f"`python3 -m opensdlc check` fails on changes/{ctx.change}. Fix every error it reports and nothing else. You are running "
                  f"headless: don't ask, don't wait, don't commit.\n\n{checked.output[-3000:]}")
        ok, _ = self.propose(ctx, record, prompt, tools, ctx.change, f"changes/{ctx.change}/**")
        checked = ctx.workspace.opensdlc("check")
        if not checked.ok:
            record.problems.append(f"check still fails: {checked.output[-500:]}")
        return ok and checked.ok


class IntakeStage(Stage):
    name = "intake"

    def run(self, ctx: Context) -> StageRecord:
        record = StageRecord(self.name)
        brief = ctx.target.brief(ctx.ticket, ctx.number)
        ctx.workspace.out("ticket.md").write_text(brief)
        prompt = "/opensdlc:intent --ticket .opensdlc/out/ticket.md"
        ok, escalated = self.propose(ctx, record, prompt, INTAKE_TOOLS, "new", "changes/**")
        if ok and escalated and ctx.ticket.answers:
            record.notes["escalations"] = 1
            ctx.workspace.reset()
            ctx.workspace.out("ticket.md").write_text(f"{brief}\n## Answers from the product owner\n\n{ctx.ticket.answers}")
            ok, escalated = self.propose(ctx, record, prompt, INTAKE_TOOLS, "new", "changes/**")
        if not ok:
            return record.block("intake patch refused")
        found = [m.group(1) for p in ctx.workspace.staged_changes() if (m := INTENT_PATH.match(p))]
        if not found:
            return record.block("no intent.md was written")
        ctx.change = found[0]
        if escalated:
            record.status = "escalated"
        ctx.workspace.opensdlc("accept", ctx.change, "--kind", "intent")
        if not self.settle(ctx, record, INTAKE_TOOLS):
            return record.block("intent fails opensdlc check")
        ctx.workspace.commit(f"Intent: {ctx.ticket.title}")
        return record


class DraftStage(Stage):
    def __init__(self, kind: str):
        self.name = kind

    def run(self, ctx: Context) -> StageRecord:
        record = StageRecord(self.name)
        workspace, change, tools = ctx.workspace, ctx.change, ctx.tools(self.name)
        workspace.opensdlc("context", change, "--stage", self.name)
        mode = "revise" if (workspace.root / "changes" / change / f"{self.name}.md").is_file() else "write"
        ok, escalated = self.propose(ctx, record, f"/opensdlc:{self.name} changes/{change} ({mode}, headless)", tools, change, f"changes/{change}/**")
        escalated = escalated or (self.judge(ctx, record) if ok else None)
        if ok and escalated and ctx.ticket.answers:
            record.notes["escalations"] = 1
            workspace.commit(f"Draft {self.name} for {change}")
            workspace.out("answers.md").write_text(f"## Raised\n\n{escalated.strip()}\n\n## The product owner's answers\n\n{ctx.ticket.answers}")
            prompt = (f"/opensdlc:{self.name} changes/{change} (revise, headless). It was escalated: .opensdlc/out/answers.md has what was raised "
                      f"and the product owner's answers.")
            ok, escalated = self.propose(ctx, record, prompt, tools, change, f"changes/{change}/**")
            escalated = escalated or (self.judge(ctx, record) if ok else None)
        if not ok:
            return record.block(f"{self.name} patch refused")
        if not (workspace.root / "changes" / change / f"{self.name}.md").is_file():
            return record.block(f"no {self.name}.md was written")
        if escalated:
            record.status = "escalated"
        workspace.opensdlc("pin", change)
        workspace.opensdlc("accept", change, "--kind", self.name)
        if not self.settle(ctx, record, tools):
            return record.block(f"{self.name} fails opensdlc check")
        workspace.commit(f"Accept {self.name} for {change}")
        self.accepted(ctx, record)
        return record

    def accepted(self, ctx: Context, record: StageRecord) -> None:
        pass


class SpecStage(DraftStage):
    def __init__(self):
        super().__init__("spec")

    def accepted(self, ctx: Context, record: StageRecord) -> None:
        root = ctx.workspace.root
        owners, _ = Knowledge(root, ctx.config()).concern_owners(Change.load(root / "changes" / ctx.change))
        record.notes["citedPolicies"] = sorted(owners)


class CodeStage(Stage):
    def verify(self, ctx: Context, record: StageRecord) -> None:
        workspace = ctx.workspace
        record.notes["ci"] = {command: outcome.ok for command, outcome in workspace.ci().items()}
        body = workspace.out("pr-body.md")
        body.write_text(f"Change: {ctx.change}\n")
        record.notes["planMatch"] = workspace.opensdlc("plan-match", "--base", ctx.base, "--head", "HEAD", "--body-file", str(body)).ok
        record.notes["check"] = workspace.opensdlc("check").ok
        record.notes["existingTestsChanged"] = self.rewritten_tests(ctx)

    def rewritten_tests(self, ctx: Context) -> list[str]:
        tests = ctx.config().get("tests", [])
        existing = set(ctx.workspace.git("ls-tree", "-r", "-z", "--name-only", ctx.base).split("\0"))
        counts = ctx.workspace.git("diff", "--numstat", "--no-renames", ctx.base, "HEAD").splitlines()
        return [path for _, removed, path in (line.split("\t", 2) for line in counts)
                if path in existing and matches(path, tests) and removed not in ("0", "-")]


class BuildStage(CodeStage):
    name = "build"

    def run(self, ctx: Context) -> StageRecord:
        record = StageRecord(self.name)
        ctx.base = ctx.workspace.head()
        ctx.workspace.opensdlc("context", ctx.change, "--stage", self.name)
        ok, escalated = self.propose(ctx, record, f"/opensdlc:build changes/{ctx.change} (write, headless)", ctx.tools(self.name), ctx.change, "")
        if not ok:
            return record.block("build patch refused")
        escalated = escalated or self.judge(ctx, record)
        if not escalated:
            ctx.workspace.opensdlc("implement", ctx.change)
        if not ctx.workspace.commit(f"Build {ctx.change}"):
            return record.block("the build changed nothing")
        if escalated:
            record.status = "escalated"
        self.verify(ctx, record)
        return record


class FixStage(CodeStage):
    name = "fix"

    def run(self, ctx: Context) -> StageRecord:
        record = StageRecord(self.name)
        findings = "\n".join(f"- {f}" for f in ctx.findings)
        prompt = (f"Review of changes/{ctx.change} raised these Important findings. Fix each one in the code, update plan.md if the fix "
                  f"departs from it, and leave `make build`, `make test` and `make lint` passing. You are running headless: don't ask, "
                  f"don't wait, don't commit.\n\n{findings}")
        ok, _ = self.propose(ctx, record, prompt, ctx.tools("build"), ctx.change, "")
        if not ok:
            return record.block("fix patch refused")
        ctx.workspace.commit(f"Address review findings on {ctx.change}")
        self.verify(ctx, record)
        return record


class ReviewStage(Stage):
    name = "review"

    def run(self, ctx: Context) -> StageRecord:
        record = StageRecord(self.name)
        workspace = ctx.workspace
        workspace.out("pr.diff").write_text(workspace.git("diff", ctx.base, "HEAD"))
        workspace.out("pr.json").write_text(json.dumps({"title": ctx.ticket.title, "body": f"Change: {ctx.change}", "files": workspace.changed_since(ctx.base)}))
        body = workspace.out("pr-body.md")
        body.write_text(f"Change: {ctx.change}\n")
        workspace.opensdlc("review-context", "--base", ctx.base, "--head", "HEAD", "--body-file", str(body))
        workspace.out("review-history.json").write_text(json.dumps({"days": 90, "keys": dict(ctx.review_keys)}))
        tally_path = workspace.out("review.json")
        tally_path.unlink(missing_ok=True)
        self.call(ctx, record, "/opensdlc:review .opensdlc/out/pr.diff (headless)", REVIEW_TOOLS)
        workspace.reset()
        if not tally_path.is_file():
            return record.block("the reviewer wrote no tally")
        try:
            tally = Tally.of(json.loads(tally_path.read_text()))
        except ValueError as error:
            return record.block(f"unreadable tally: {error}")
        important = [f for f in tally.findings if f.severity == "important"]
        record.notes.update({
            "important": len(important),
            "nit": tally.count("nit"),
            "repeats": sum(f.repeat for f in tally.findings),
            "keys": sorted({f.key for f in tally.findings}),
            "policyFindings": sum(bool(f.policy) for f in tally.findings),
            "agentsMdOutdated": tally.agents_md_outdated,
        })
        ctx.findings = [f"{f.tag} `{f.file}{f':{f.line}' if f.line else ''}` {f.summary}" for f in important]
        return record


DRAFTING: list[Stage] = [IntakeStage(), SpecStage(), DraftStage("plan"), BuildStage()]
