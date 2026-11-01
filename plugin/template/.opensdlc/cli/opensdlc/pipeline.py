# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .artifacts import CHANGE_ID, KINDS, Artifact, Change
from .config import CHANGES_DIR
from .gitio import StagedEntry
from .globs import matches
from .toolset import toolset

READ_WRITE = "Read,Write,Edit,Glob,Grep,Skill,Agent"
READ_ONLY = "Read,Glob,Grep,Skill"
ISSUE_REF = re.compile(r"^#(\d+)$")
MODEL = re.compile(r"^[A-Za-z0-9][\w.\[\]-]*$")


def role_tools(config: dict, role: str, default: str) -> str:
    return config.get("stages", {}).get(role, {}).get("allowedTools", default)


def role_model(config: dict, role: str) -> str:
    model = config.get("stages", {}).get(role, {}).get("model", "")
    if model and not (isinstance(model, str) and MODEL.match(model)):
        raise ValueError(f"stages.{role}.model in .opensdlc/config.json is not a model name: {model!r}")
    return model


@dataclass(frozen=True)
class Action:
    change: Change
    stage: "Stage"
    allowed_tools: str
    gate_tools: str
    model: str
    gate_model: str

    def as_matrix_entry(self) -> dict:
        intent = self.change.get("intent")
        ref = ISSUE_REF.match(intent.meta.get("ref", "")) if intent else None
        return {
            "id": self.change.id,
            "mode": self.stage.mode(self.change),
            "change": (CHANGES_DIR / self.change.id).as_posix(),
            "stage": self.stage.name,
            "skill": f"opensdlc:{self.stage.name}",
            "allowedTools": self.allowed_tools,
            "tools": toolset(self.allowed_tools),
            "gateAllowedTools": self.gate_tools,
            "gateTools": toolset(self.gate_tools),
            "model": self.model,
            "gateModel": self.gate_model,
            "branch": f"opensdlc/{self.change.id}/{self.stage.name}",
            "title": f"{self.stage.title}: {self.change.id}",
            "scope": ",".join(self.stage.scope(self.change)),
            "issue": ref.group(1) if ref else "",
        }


class Stage(ABC):
    name: str
    title: str
    source: str

    def tools(self, config: dict) -> str:
        return role_tools(config, self.name, READ_WRITE)

    def gate_tools(self, config: dict) -> str:
        return role_tools(config, "gate", READ_ONLY)

    def mode(self, change: Change) -> str:
        return "write"

    def scope(self, change: Change) -> list[str]:
        return []

    @abstractmethod
    def due(self, change: Change, config: dict) -> bool: ...


class DraftingStage(Stage):
    def mode(self, change: Change) -> str:
        return "revise" if change.get(self.name) else "write"

    def scope(self, change: Change) -> list[str]:
        return [f"{CHANGES_DIR}/{change.id}/**"]

    def due(self, change: Change, config: dict) -> bool:
        source = change.get(self.source)
        target = change.get(self.name)
        if not source or source.status != "accepted":
            return False
        return target is None or (target.status == "draft" and change.stale(target))


class SpecStage(DraftingStage):
    name, title, source = "spec", "Spec", "intent"


class PlanStage(DraftingStage):
    name, title, source = "plan", "Draft plan", "spec"


class BuildStage(Stage):
    name, title, source = "build", "Build", "plan"

    def due(self, change: Change, config: dict) -> bool:
        plan = change.get("plan")
        auto = config.get("stages", {}).get("build", {}).get("autoRisk", [])
        return bool(plan and plan.status == "accepted" and not change.stale(plan) and plan.meta.get("risk") in auto)

    def gate_tools(self, config: dict) -> str:
        return f"{super().gate_tools(config)},{role_tools(config, 'verify', READ_ONLY)}"


STAGES: list[Stage] = [SpecStage(), PlanStage(), BuildStage()]


def touched_changes(root: Path, paths: list[str]) -> list[Change]:
    ids = sorted({Path(p).parts[1] for p in paths if Path(p).parts[:1] == (CHANGES_DIR.name,) and len(Path(p).parts) > 2})
    return [Change.load(root / CHANGES_DIR / i) for i in ids if (root / CHANGES_DIR / i).is_dir()]


def next_actions(root: Path, paths: list[str], config: dict) -> list[Action]:
    changed = set(paths)
    actions = []
    for change in touched_changes(root, paths):
        for stage in STAGES:
            touched = {f"{CHANGES_DIR}/{change.id}/{name}.md" for name in (stage.source, stage.name)} & changed
            if touched and stage.due(change, config):
                actions.append(Action(change, stage, stage.tools(config), stage.gate_tools(config), role_model(config, stage.name),
                                      role_model(config, "gate")))
    return actions


def forbidden_paths(paths: list[str], config: dict) -> list[str]:
    patterns = [p.lower() for p in config.get("pipeline", {}).get("forbiddenPaths", [])]
    return [p for p in paths if matches(p.lower(), patterns)]


def change_folder(path: str) -> str | None:
    parts = Path(path).parts
    if not parts or parts[0].lower() != CHANGES_DIR.name:
        return None
    return parts[1] if len(parts) > 2 else ""


def change_problems(entries: list[StagedEntry], change: str, existing: set[str]) -> list[str]:
    inside = [(e, folder) for e in entries if (folder := change_folder(e.path)) is not None]
    if change != "new":
        return [f"{e.path}: outside this run's change, {CHANGES_DIR}/{change}/" for e, folder in inside if folder != change]
    folders = sorted({folder for _, folder in inside})
    if len(folders) > 1:
        return [f"this run may create one change folder, not {len(folders)}: {', '.join(folders)}"]
    problems = [f"{e.path}: this run may only add files to a new change folder" for e, _ in inside if e.status != "A"]
    return problems + [f"{CHANGES_DIR}/{f}: already exists or is not a valid change id" for f in folders if f in existing or not CHANGE_ID.match(f)]


def patch_problems(entries: list[StagedEntry], scope: list[str], change: str, existing: set[str], config: dict) -> list[str]:
    forbidden = set(forbidden_paths([e.path for e in entries], config))
    problems = []
    for entry in entries:
        if entry.path in forbidden:
            problems.append(f"{entry.path}: only a human may change this path")
        elif scope and not matches(entry.path, scope):
            problems.append(f"{entry.path}: outside this run's scope ({', '.join(scope)})")
        if entry.link:
            problems.append(f"{entry.path}: an agent may not add symlinks or submodules")
    return problems + change_problems(entries, change, existing)


def accepted_intents(root: Path, changed: list[str], before: Callable[[str], str | None]) -> list[dict]:
    found = []
    for path in changed:
        if not (path.startswith(f"{CHANGES_DIR}/") and path.endswith("/intent.md")) or not (root / path).is_file():
            continue
        intent = Artifact.read(KINDS["intent"], root / path)
        previous = before(path)
        was = Artifact.parse(KINDS["intent"], root / path, previous).status if previous else ""
        ref = ISSUE_REF.match(intent.meta.get("ref", ""))
        if intent.status == "accepted" and was != "accepted" and ref:
            found.append({"issue": int(ref.group(1)), "change": Path(path).parts[1]})
    return found
