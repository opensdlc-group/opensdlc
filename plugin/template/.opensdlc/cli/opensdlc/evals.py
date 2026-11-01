# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .globs import matches
from .toolset import toolset

CASES_DIR = Path("evals/cases")
SECRET_ENV = frozenset({
    "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "OPENSDLC_ORG_TOKEN",
    "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL",
})


@dataclass(frozen=True)
class Run:
    worktree: Path
    base: str
    output: str


@dataclass(frozen=True)
class Outcome:
    check: str
    passed: bool
    detail: str = ""


class Check(ABC):
    def __init__(self, spec: dict):
        self.spec = spec

    @property
    def label(self) -> str:
        return f"{self.spec['type']} {self.spec.get('run') or self.spec.get('file') or self.spec.get('paths') or self.spec.get('pattern', '')}"

    @abstractmethod
    def evaluate(self, run: Run) -> Outcome: ...


class CommandCheck(Check):
    def evaluate(self, run: Run) -> Outcome:
        env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
        result = subprocess.run(self.spec["run"], shell=True, cwd=run.worktree, env=env, capture_output=True, text=True, timeout=self.spec.get("timeout", 600))
        return Outcome(self.label, result.returncode == 0, (result.stdout + result.stderr)[-2000:])


class UnchangedCheck(Check):
    def evaluate(self, run: Run) -> Outcome:
        git = ["git", "-C", str(run.worktree)]
        changed = subprocess.run([*git, "diff", "--name-only", run.base], capture_output=True, text=True, check=True).stdout.split()
        changed += subprocess.run([*git, "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, check=True).stdout.split()
        touched = [p for p in changed if matches(p, self.spec["paths"])]
        return Outcome(self.label, not touched, ", ".join(touched))


class FileMatchCheck(Check):
    expect: bool

    def evaluate(self, run: Run) -> Outcome:
        file = run.worktree / self.spec["file"]
        found = file.is_file() and re.search(self.spec["pattern"], file.read_text(), re.M) is not None
        return Outcome(self.label, found == self.expect)


class ContainsCheck(FileMatchCheck):
    expect = True


class AbsentCheck(FileMatchCheck):
    expect = False


class OutputCheck(Check):
    def evaluate(self, run: Run) -> Outcome:
        return Outcome(self.label, re.search(self.spec["pattern"], run.output, re.M) is not None)


CHECKS: dict[str, type[Check]] = {
    "command": CommandCheck,
    "unchanged": UnchangedCheck,
    "contains": ContainsCheck,
    "absent": AbsentCheck,
    "output": OutputCheck,
}


@dataclass
class Attempt:
    passed: bool
    outcomes: list[Outcome] = field(default_factory=list)
    error: str = ""


@dataclass
class CaseResult:
    id: str
    attempts: list[Attempt]

    @property
    def passes(self) -> int:
        return sum(a.passed for a in self.attempts)

    @property
    def rate(self) -> float:
        return self.passes / len(self.attempts) if self.attempts else 0.0

    def failures(self) -> list[str]:
        failed = [a.error for a in self.attempts if a.error]
        failed += [f"{o.check}: {' '.join(o.detail.split())[-160:]}" if o.detail else o.check for a in self.attempts for o in a.outcomes if not o.passed]
        return sorted(set(failed))


class Agent(ABC):
    @abstractmethod
    def run(self, case: dict, worktree: Path, timeout: int) -> str: ...


class ClaudeCli(Agent):
    def __init__(self, settings: Path | None = None, plugin: Path | None = None):
        self.settings = settings
        self.plugin = plugin

    def run(self, case: dict, worktree: Path, timeout: int) -> str:
        allowed = case.get("allowedTools", "Read,Edit,Glob,Grep")
        cmd = [
            "claude", "-p", case["prompt"],
            "--allowedTools", allowed,
            "--tools", toolset(allowed),
            "--max-turns", str(case.get("maxTurns", 40)),
            "--output-format", "json",
        ]
        if self.settings and self.settings.is_file():
            cmd += ["--settings", str(self.settings)]
        if self.plugin:
            cmd += ["--plugin-dir", str(self.plugin)]
        result = subprocess.run(cmd, cwd=worktree, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] or result.stdout[-2000:])
        return json.loads(result.stdout).get("result", "")


class Suite:
    def __init__(self, root: Path, agent: Agent, timeout: int, repeats: int = 1):
        self.root = root
        self.agent = agent
        self.timeout = timeout
        self.repeats = repeats

    def cases(self, only: str | None) -> list[dict]:
        files = sorted((self.root / CASES_DIR).glob("*.json"))
        cases = [json.loads(f.read_text()) for f in files]
        return [c for c in cases if only in (None, c["id"])]

    def attempt(self, case: dict) -> Attempt:
        base = case.get("ref", "HEAD")
        worktree = Path(tempfile.mkdtemp(prefix=f"opensdlc-eval-{case['id']}-"))
        subprocess.run(["git", "-C", str(self.root), "worktree", "add", "--detach", str(worktree), base], capture_output=True, check=True)
        try:
            output = self.agent.run(case, worktree, self.timeout)
            run = Run(worktree=worktree, base=base, output=output)
            outcomes = [CHECKS[spec["type"]](spec).evaluate(run) for spec in case["checks"]]
            return Attempt(all(o.passed for o in outcomes), outcomes)
        except (RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            return Attempt(False, error=str(error))
        finally:
            subprocess.run(["git", "-C", str(self.root), "worktree", "remove", "--force", str(worktree)], capture_output=True)
            shutil.rmtree(worktree, ignore_errors=True)

    def run_case(self, case: dict) -> CaseResult:
        return CaseResult(case["id"], [self.attempt(case) for _ in range(case.get("repeats", self.repeats))])


@dataclass(frozen=True)
class Gate:
    max_drop: float = 0.1
    case_drop: float = 0.34
    floor: float | None = None

    def reasons(self, rate: float, cases: dict[str, float], baseline: dict | None) -> list[str]:
        found = []
        if self.floor is not None and rate < self.floor:
            found.append(f"pass rate {rate:.0%} is below the floor of {self.floor:.0%}")
        if baseline:
            before = baseline.get("passRate", 0.0)
            if before - rate > self.max_drop:
                found.append(f"pass rate fell from {before:.0%} to {rate:.0%}")
            previous = {c["id"]: c["rate"] for c in baseline.get("cases", []) if "rate" in c}
            for case_id, now in cases.items():
                if case_id in previous and previous[case_id] - now >= self.case_drop:
                    found.append(f"`{case_id}` fell from {previous[case_id]:.0%} to {now:.0%}")
        return found


def report(results: list[CaseResult], gate: Gate, baseline: dict | None) -> tuple[dict, str]:
    rate = sum(r.rate for r in results) / len(results) if results else 1.0
    previous = {c["id"]: c.get("rate") for c in (baseline or {}).get("cases", [])}
    reasons = gate.reasons(rate, {r.id: r.rate for r in results}, baseline)
    against = f" against main's {baseline['passRate']:.0%}" if baseline else ", no baseline from main yet"
    lines = [f"## Agent evals: {rate:.0%} passed{against}", ""]
    lines += [f"**Gate failed:** {'; '.join(reasons)}.", ""] if reasons else ["Gate passed.", ""]
    for r in results:
        was = f" (main {previous[r.id]:.0%})" if previous.get(r.id) is not None else ""
        lines.append(f"- {'✅' if r.rate == 1 else '⚠️' if r.rate else '❌'} `{r.id}`: {r.passes}/{len(r.attempts)}{was}")
        lines += [f"  - {f[:200]}" for f in r.failures()]
    data = {
        "passRate": rate,
        "baselinePassRate": baseline.get("passRate") if baseline else None,
        "gate": {"ok": not reasons, "reasons": reasons},
        "cases": [{"id": r.id, "rate": r.rate, "passes": r.passes, "runs": len(r.attempts), "failures": r.failures()} for r in results],
    }
    return data, "\n".join(lines)
