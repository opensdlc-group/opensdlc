# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .agent import AgentUnavailable, ClaudeCode
from .model import Scenario
from .paths import RESULTS
from .pipeline import BenchRun, RunRecord
from .report import compare_markdown, load, run_markdown, suite_markdown, summary
from .stages import Settings
from .verify import verify_reference


def python3_at_least(*version: int) -> bool:
    try:
        found = subprocess.run(["python3", "-c", f"import sys; sys.exit(sys.version_info < {version})"], capture_output=True)
    except FileNotFoundError:
        return False
    return found.returncode == 0


@dataclass(frozen=True)
class Requirement:
    met: Callable[[], bool]
    message: str


BUILD_REQUIREMENTS = (
    Requirement(lambda: os.name != "nt",
                "The bench runs every agent in Claude Code's sandbox and drives the targets with make and shell scripts, so `{command}` "
                "needs Linux, macOS or WSL2. On Windows, run it inside a WSL2 distribution."),
    Requirement(lambda: python3_at_least(3, 12),
                "`{command}` runs the targets and the OpenSDLC CLI with `python3`, which must be Python 3.12 or later. "
                "Ubuntu 22.04 ships 3.10; bench/README.md says how to get 3.12."),
)


class Command(ABC):
    name: str
    help: str
    builds = False

    def configure(self, parser: argparse.ArgumentParser) -> None:
        pass

    @abstractmethod
    def run(self, args: argparse.Namespace) -> int: ...


class ListCommand(Command):
    name, help = "list", "List scenarios and targets"

    def run(self, args):
        for name in Scenario.names():
            scenario = Scenario.load(name)
            print(f"scenario {name}: {scenario.description}")
            for ticket in scenario.tickets:
                print(f"  ticket {ticket.id}: {ticket.title} ({len(ticket.checks)} checks)")
            for target in scenario.targets([]):
                print(f"  target {target.name}: {target.description}, {target.stack}")
        return 0


class VerifyCommand(Command):
    name, help = "verify", "Prove each target's reference implementation passes CI and every acceptance check"
    builds = True

    def configure(self, parser):
        parser.add_argument("--scenario", default="todo")
        parser.add_argument("--target", action="append", default=[])

    def run(self, args):
        scenario, failed = Scenario.load(args.scenario), 0
        for target in scenario.targets(args.target):
            result = verify_reference(scenario, target)
            passed = sum(c.passed for c in result.checks)
            applicable = sum(c.status != "skip" for c in result.checks)
            ci = ", ".join(f"{k} {'ok' if v else 'FAILED'}" for k, v in result.ci.items())
            print(f"{target.name}: {passed}/{applicable} checks; {ci}")
            for check in result.checks:
                if check.status == "fail":
                    print(f"  FAIL {check.key}: {check.detail}")
            failed += not result.ok
        return 1 if failed else 0


class RunCommand(Command):
    name, help = "run", "Build a scenario through OpenSDLC with Claude Code, then score it with the acceptance checks"
    builds = True

    def configure(self, parser):
        parser.add_argument("--scenario", default="todo")
        parser.add_argument("--target", action="append", required=True, help="a target name, repeatable, or 'all'")
        parser.add_argument("--tickets", help="comma-separated ticket id prefixes, e.g. 01,02")
        parser.add_argument("--repeats", type=int, default=1)
        parser.add_argument("--model")
        parser.add_argument("--max-turns", type=int)
        parser.add_argument("--fix-rounds", type=int, default=1)
        parser.add_argument("--max-cost", type=float, help="start no new stage once a run has spent this many dollars")
        parser.add_argument("--out", type=Path)
        parser.add_argument("--keep", action="store_true", help="keep each run's workspace for inspection")

    def run(self, args):
        scenario = Scenario.load(args.scenario)
        tickets = scenario.select(args.tickets.split(",") if args.tickets else None)
        out = args.out or RESULTS / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{scenario.name}"
        settings, agent = Settings(args.max_turns, args.fix_rounds), ClaudeCode(args.model)
        status = 0
        for target in scenario.targets(args.target):
            for number in range(1, args.repeats + 1):
                bench = BenchRun(scenario, target, tickets, agent, settings, args.model or "", args.max_cost, args.keep)
                try:
                    bench.execute()
                except AgentUnavailable:
                    status = 1
                self.save(bench.record, agent, out / target.name, number, len(tickets))
                if status:
                    print("Stopped: no further runs can reach the agent.", file=sys.stderr)
                    break
            if status:
                break
        (out / "summary.md").write_text(suite_markdown(load(out)))
        print(out / "summary.md")
        return status

    def save(self, record: RunRecord, agent: ClaudeCode, folder: Path, number: int, tickets: int) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.keep_sessions_with_problems(record, agent, folder / f"run-{number}-sessions")
        data = json.loads(json.dumps(record.as_json(), default=str))
        (folder / f"run-{number}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        (folder / f"run-{number}.md").write_text(run_markdown(data))
        s = summary(data)
        print(f"{record.target} run {number}: acceptance {s['acceptance']:.0%}, {s['ticketsCompleted']}/{tickets} tickets, "
              f"${s['cost']:.2f}, {s['minutes']:.1f} min{f'; {record.error}' if record.error else ''}", flush=True)

    @staticmethod
    def keep_sessions_with_problems(record: RunRecord, agent: ClaudeCode, folder: Path) -> None:
        for ticket in record.tickets:
            for stage in ticket.stages:
                for run in stage.runs:
                    transcript = agent.transcript(run.session) if stage.problems or not run.ok else None
                    if transcript:
                        folder.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(transcript, folder / f"{ticket.ticket}-{stage.stage}-{run.session}.jsonl")


class ReportCommand(Command):
    name, help = "report", "Summarize a results folder"

    def configure(self, parser):
        parser.add_argument("results", type=Path)

    def run(self, args):
        print(suite_markdown(load(args.results)))
        return 0


class CompareCommand(Command):
    name, help = "compare", "Compare two results folders, such as before and after a skill change"

    def configure(self, parser):
        parser.add_argument("before", type=Path)
        parser.add_argument("after", type=Path)

    def run(self, args):
        print(compare_markdown(load(args.before), load(args.after)))
        return 0


COMMANDS: list[Command] = [ListCommand(), VerifyCommand(), RunCommand(), ReportCommand(), CompareCommand()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Build software through OpenSDLC repeatably and measure it.")
    commands = parser.add_subparsers(dest="command", required=True)
    registry = {}
    for command in COMMANDS:
        command.configure(commands.add_parser(command.name, help=command.help))
        registry[command.name] = command
    args = parser.parse_args(argv)
    command = registry[args.command]
    requirements = BUILD_REQUIREMENTS if command.builds else ()
    unmet = next((r for r in requirements if not r.met()), None)
    if unmet:
        print(unmet.message.format(command=command.name), file=sys.stderr)
        return 2
    return command.run(args)

