# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import SCENARIOS


@dataclass(frozen=True)
class Check:
    ticket: str
    name: str
    steps: tuple[dict, ...]
    excluded: frozenset[str]

    @property
    def key(self) -> str:
        return f"{self.ticket}: {self.name}"

    def applies_to(self, target: str) -> bool:
        return target not in self.excluded


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str
    answers: str
    checks: tuple[Check, ...]
    must_escalate: bool = False

    @property
    def title(self) -> str:
        return self.text.splitlines()[0].lstrip("# ").strip()

    @property
    def body(self) -> str:
        return self.text.split("\n", 1)[1].strip()


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    tickets: tuple[Ticket, ...]
    root: Path

    @staticmethod
    def names() -> list[str]:
        return sorted(p.name for p in SCENARIOS.iterdir() if (p / "scenario.json").is_file())

    @classmethod
    def load(cls, name: str) -> "Scenario":
        root = SCENARIOS / name
        meta = json.loads((root / "scenario.json").read_text())
        escalate = set(meta.get("escalate", []))
        return cls(meta["name"], meta.get("description", ""), tuple(cls.ticket(root, t, t in escalate) for t in meta["tickets"]), root)

    def target_names(self) -> list[str]:
        return sorted(p.name for p in (self.root / "targets").iterdir() if (p / "target.json").is_file())

    def target(self, name: str) -> "Target":
        return Target.load(self.root / "targets" / name)

    def targets(self, names: list[str]) -> list["Target"]:
        return [self.target(n) for n in (self.target_names() if not names or "all" in names else names)]

    @staticmethod
    def ticket(root: Path, id_: str, must_escalate: bool) -> Ticket:
        raw = json.loads((root / "acceptance" / f"{id_}.json").read_text())
        checks = tuple(Check(id_, c["name"], tuple(c["steps"]), frozenset(c.get("except", []))) for c in raw["checks"])
        answers = root / "answers" / f"{id_}.md"
        return Ticket(id_, (root / "tickets" / f"{id_}.md").read_text(), answers.read_text() if answers.is_file() else "", checks, must_escalate)

    def select(self, ids: list[str] | None) -> tuple[Ticket, ...]:
        return tuple(t for t in self.tickets if not ids or any(t.id.startswith(i) for i in ids))


@dataclass(frozen=True)
class Target:
    name: str
    description: str
    stack: str
    setup: tuple[str, ...]
    adapter: dict
    root: Path
    build_tools: str

    @classmethod
    def load(cls, root: Path) -> "Target":
        meta = json.loads((root / "target.json").read_text())
        return cls(meta["name"], meta.get("description", ""), meta["stack"], tuple(meta.get("setup", [])), meta["adapter"], root, meta.get("buildTools", ""))

    @property
    def shared(self) -> Path:
        return self.root.parent.parent / "repository"

    @property
    def skeleton(self) -> Path:
        return self.root / "skeleton"

    @property
    def reference(self) -> Path:
        return self.root / "reference"

    def interface(self, ticket: Ticket) -> str:
        path = self.root / "interface" / f"{ticket.id}.md"
        return path.read_text() if path.is_file() else ""

    def brief(self, ticket: Ticket, number: int) -> str:
        interface = "" if ticket.must_escalate else self.interface(ticket).strip()
        return f"# Ticket #{number}: {ticket.title}\n\n{ticket.body}\n" + (f"\n## Interface\n\n{interface}\n" if interface else "")
