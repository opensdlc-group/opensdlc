# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Change
from .gitio import StagedEntry
from .globs import matches
from .knowledge import plan_files

GATE_FILE = "gate.json"
VERIFY_FILE = "verify.md"
REPORT_FILE = "gate-report.md"
ENDING = re.compile(r"\b(resolved|carried|escalated)\b", re.I)
REWRITES = {"M": "edits", "D": "deletes", "T": "edits"}


@dataclass(frozen=True)
class Evidence:
    stage: str
    out: Path
    change: Change
    staged: tuple[StagedEntry, ...]
    tests: tuple[str, ...]


class Rule(ABC):
    stages: frozenset[str]

    @abstractmethod
    def reasons(self, evidence: Evidence) -> list[str]: ...


class GateVerdict(Rule):
    stages = frozenset({"spec", "plan", "build"})

    def reasons(self, evidence: Evidence) -> list[str]:
        path = evidence.out / GATE_FILE
        if not path.is_file() or path.is_symlink():
            return ["The confidence gate gave no verdict."]
        try:
            raw = json.loads(path.read_text())
        except ValueError as error:
            return [f"The confidence gate's verdict is not JSON: {error}."]
        verdict, reasons = (raw.get("verdict"), raw.get("reasons")) if isinstance(raw, dict) else (None, None)
        if verdict not in ("continue", "escalate") or not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
            return ['The confidence gate\'s verdict needs "verdict": "continue" or "escalate" and "reasons" as a list of strings.']
        if verdict == "continue":
            return []
        return [r.strip() for r in reasons if r.strip()] or ["The confidence gate escalated without saying why."]


class Verification(Rule):
    stages = frozenset({"build"})

    def reasons(self, evidence: Evidence) -> list[str]:
        path = evidence.out / VERIFY_FILE
        if not path.is_file() or path.is_symlink():
            return ["Nobody verified the build."]
        first = next((line.strip() for line in path.read_text().splitlines() if line.strip()), "")
        return [] if first == "PASS" else [f"Verification did not pass: {first[:200] or 'the report is empty'}."]


class ConcernEndings(Rule):
    stages = frozenset({"spec"})

    def reasons(self, evidence: Evidence) -> list[str]:
        spec = evidence.change.get("spec")
        if spec is None:
            return ["The spec stage left no spec.md."]
        return [f"A concern says neither resolved, carried nor escalated: {bullet[:160]}"
                for bullet in self.bullets(spec.section("Concerns")) if not ENDING.search(bullet)]

    @staticmethod
    def bullets(section: str) -> list[str]:
        found: list[str] = []
        for line in section.splitlines():
            if line.startswith("- "):
                found.append(line[2:].strip())
            elif found and line.strip():
                found[-1] += f" {line.strip()}"
        return found


class PlannedTestEdits(Rule):
    stages = frozenset({"build"})

    def reasons(self, evidence: Evidence) -> list[str]:
        plan = evidence.change.get("plan")
        listed = plan_files(plan.section("Files that change")) if plan else []
        return [f"The build {REWRITES[entry.status]} {entry.path}, an existing test the plan does not list."
                for entry in evidence.staged
                if entry.status in REWRITES and matches(entry.path, list(evidence.tests)) and not matches(entry.path, listed)]


RULES: tuple[Rule, ...] = (GateVerdict(), Verification(), ConcernEndings(), PlannedTestEdits())


@dataclass(frozen=True)
class Verdict:
    escalate: bool
    reasons: tuple[str, ...]

    @classmethod
    def judge(cls, evidence: Evidence) -> "Verdict":
        reasons = [reason for rule in RULES if evidence.stage in rule.stages for reason in rule.reasons(evidence)]
        return cls(bool(reasons), tuple(reasons))

    def markdown(self) -> str:
        if not self.escalate:
            return "The confidence gate found no reason to stop.\n"
        return "The confidence gate escalated:\n\n" + "".join(f"- {r}\n" for r in self.reasons)

    def as_json(self) -> dict:
        return {"escalate": self.escalate, "reasons": list(self.reasons)}
