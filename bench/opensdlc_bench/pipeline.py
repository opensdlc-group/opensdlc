# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .acceptance import CheckResult, run_checks
from .adapters import adapter_for
from .agent import Agent, AgentUnavailable
from .model import Scenario, Target, Ticket
from .paths import REPO
from .stages import DRAFTING, Context, FixStage, ReviewStage, Settings, Stage, StageRecord
from .workspace import Workspace, WorkspaceError


@dataclass
class TicketRecord:
    ticket: str
    title: str
    change: str | None
    stages: list[StageRecord]
    acceptance: list[CheckResult]
    must_escalate: bool = False


@dataclass
class RunRecord:
    scenario: str
    target: str
    stack: str
    model: str
    opensdlc: str
    started: str
    seconds: float = 0.0
    workspace: str = ""
    error: str = ""
    stopped: str = ""
    tickets: list[TicketRecord] = field(default_factory=list)

    def cost(self) -> float:
        return sum(r.cost for t in self.tickets for s in t.stages for r in s.runs)

    def as_json(self) -> dict:
        return asdict(self)


def opensdlc_version() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()
    sha = git("rev-parse", "--short", "HEAD") or "unknown"
    return f"{sha}{'+dirty' if git('status', '--porcelain', '--', 'plugin') else ''}"


class BenchRun:
    def __init__(self, scenario: Scenario, target: Target, tickets: tuple[Ticket, ...], agent: Agent, settings: Settings,
                 model: str = "", max_cost: float | None = None, keep: bool = False):
        self.scenario = scenario
        self.target = target
        self.tickets = tickets
        self.agent = agent
        self.settings = settings
        self.max_cost = max_cost
        self.keep = keep
        self.record = RunRecord(scenario.name, target.name, target.stack, model or "default", opensdlc_version(),
                                datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def execute(self) -> RunRecord:
        started = time.monotonic()
        parent = Path(tempfile.mkdtemp(prefix=f"opensdlc-bench-{self.target.name}-"))
        try:
            workspace = Workspace.create(self.target, parent)
            self.record.workspace = str(workspace.root)
            broken = [command for command, outcome in workspace.ci().items() if not outcome.ok]
            if broken:
                self.record.error = f"the skeleton fails {', '.join(broken)} before any work"
            else:
                self.tickets_on(workspace)
        except WorkspaceError as error:
            self.record.error = str(error)
        except AgentUnavailable as error:
            self.record.error = f"the agent stopped answering: {error}"
            raise
        finally:
            self.record.seconds = round(time.monotonic() - started, 1)
            if not self.keep:
                shutil.rmtree(parent, ignore_errors=True)
                self.record.workspace = ""
        return self.record

    def tickets_on(self, workspace: Workspace) -> None:
        keys: Counter = Counter()
        for number, ticket in enumerate(self.tickets, 1):
            ctx = Context(workspace, self.agent, self.target, ticket, number, self.settings, keys)
            record = TicketRecord(ticket.id, ticket.title, None, [], [], ticket.must_escalate)
            self.record.tickets.append(record)
            self.stages(ctx, record.stages)
            record.change = ctx.change
            self.sign_off(ctx, record.stages)
            checks = [c for t in self.tickets[:number] for c in t.checks]
            record.acceptance = run_checks(adapter_for(self.target.adapter, self.target.root, workspace.root), self.target.name, checks)
            reviews = [s for s in record.stages if s.stage == "review" and "keys" in s.notes]
            if reviews:
                keys.update(reviews[-1].notes["keys"])
            if self.record.stopped:
                return

    def sign_off(self, ctx: Context, records: list[StageRecord]) -> None:
        if not any(r.stage == "build" and r.status != "blocked" for r in records):
            return
        workspace = ctx.workspace
        workspace.opensdlc("implement", ctx.change)
        contract = workspace.root / "knowledge" / "architecture" / "interface.md"
        contract.write_text(f"{contract.read_text().rstrip()}\n\n## {ctx.ticket.title}\n\n{self.target.interface(ctx.ticket).strip()}\n")
        workspace.commit(f"Product owner: sign off {ctx.change} and add it to the interface")

    def stages(self, ctx: Context, records: list[StageRecord]) -> None:
        for stage in DRAFTING:
            if not self.step(stage, ctx, records) or records[-1].status == "blocked":
                return
        if not self.step(ReviewStage(), ctx, records):
            return
        for _ in range(self.settings.fix_rounds):
            if not records[-1].notes.get("important"):
                return
            if not self.step(FixStage(), ctx, records) or records[-1].status == "blocked":
                return
            if not self.step(ReviewStage(), ctx, records):
                return

    def step(self, stage: Stage, ctx: Context, records: list[StageRecord]) -> bool:
        if self.max_cost is not None and self.record.cost() >= self.max_cost:
            self.record.stopped = (f"stopped before the {stage.name} stage of {ctx.ticket.id}: "
                                   f"${self.record.cost():.2f} spent, the cap is ${self.max_cost:.2f}")
            return False
        records.append(stage.run(ctx))
        return True
