# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .document import Document, content_hash, split_list

PLACEHOLDER = re.compile(r"^\s*<[^>\n]+>\s*$", re.M)
PIN = re.compile(r"^(?P<file>[^\s@]+\.md)@(?P<hash>[0-9a-f]{12})$")
RISKS = ("low", "standard", "high")
READY = ("accepted", "implemented")
CHANGE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class Finding:
    level: str
    message: str

    @classmethod
    def error(cls, message: str) -> "Finding":
        return cls("error", message)

    @classmethod
    def warning(cls, message: str) -> "Finding":
        return cls("warning", message)


@dataclass(frozen=True)
class ArtifactKind:
    name: str
    statuses: tuple[str, ...]
    fields: tuple[str, ...]
    sections: tuple[str, ...]
    after: str | None = None

    @property
    def filename(self) -> str:
        return f"{self.name}.md"

    @property
    def has_context(self) -> bool:
        return "context" in self.fields

    @property
    def has_risk(self) -> bool:
        return "risk" in self.fields


KINDS: dict[str, ArtifactKind] = {
    kind.name: kind
    for kind in (
        ArtifactKind(
            name="intent",
            statuses=("draft", "accepted", "rejected"),
            fields=("author", "source"),
            sections=("Problem", "Proposed outcome", "Affected users and systems", "Constraints", "Out of scope", "Open questions"),
        ),
        ArtifactKind(
            name="spec",
            statuses=("draft", "accepted", "rejected"),
            fields=("intent", "context", "risk"),
            sections=(
                "Problem Statement", "Solution", "User Stories", "Implementation Decisions", "Testing Decisions",
                "Acceptance Criteria", "Out of Scope", "Concerns", "Carried-forward Questions",
            ),
            after="intent",
        ),
        ArtifactKind(
            name="plan",
            statuses=("draft", "accepted", "implemented", "rejected"),
            fields=("spec", "context", "risk"),
            sections=("Files that change", "Slices", "Risks", "Alternatives considered", "Proof"),
            after="spec",
        ),
    )
}


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    document: Document

    @classmethod
    def read(cls, kind: ArtifactKind, path: Path) -> "Artifact":
        return cls(kind, Document.read(path))

    @classmethod
    def parse(cls, kind: ArtifactKind, path: Path, text: str) -> "Artifact":
        return cls(kind, Document.parse(path, text))

    @property
    def path(self) -> Path:
        return self.document.path

    @property
    def text(self) -> str:
        return self.document.text

    @property
    def meta(self) -> dict[str, str]:
        return self.document.meta

    @property
    def body(self) -> str:
        return self.document.body

    @property
    def status(self) -> str:
        return self.meta.get("status", "")

    @property
    def ready(self) -> bool:
        return self.status in READY

    @property
    def risk(self) -> str:
        return self.meta.get("risk", "")

    @property
    def hash(self) -> str:
        return self.document.hash

    @property
    def pin(self) -> str | None:
        match = PIN.match(self.meta.get(self.kind.after or "", ""))
        return match.group("hash") if match else None

    @property
    def context(self) -> dict[str, str] | None:
        value = self.meta.get("context", "")
        if not value or value.startswith("<"):
            return None
        pins = {}
        for item in split_list(value):
            match = PIN.match(item)
            if match:
                pins[match.group("file")] = match.group("hash")
        return pins

    def section(self, name: str) -> str:
        return self.document.section(name)

    def with_meta(self, **values: str) -> str:
        return self.document.with_meta(**values)

    def problems(self) -> list[Finding]:
        if not self.meta:
            return [Finding.error(f"{self.path}: missing frontmatter")]
        found = []
        if self.meta.get("kind") != self.kind.name:
            found.append(f"{self.path}: kind must be '{self.kind.name}'")
        if self.status not in self.kind.statuses:
            found.append(f"{self.path}: status must be one of {', '.join(self.kind.statuses)}")
        for name in self.kind.fields:
            if not self.meta.get(name):
                found.append(f"{self.path}: frontmatter field '{name}' is empty")
        for name, value in self.meta.items():
            if value.startswith("<") and name != "context":
                found.append(f"{self.path}: frontmatter field '{name}' still holds a template placeholder")
        for section in self.kind.sections:
            if section not in self.document.headings:
                found.append(f"{self.path}: missing section '## {section}'")
        if PLACEHOLDER.search(self.body):
            found.append(f"{self.path}: template placeholder left in body")
        if self.kind.has_risk and self.risk not in RISKS:
            found.append(f"{self.path}: risk must be one of {', '.join(RISKS)}")
        return [Finding.error(m) for m in found]


ContextFor = Callable[["Change", str], list[str]]


@dataclass
class Change:
    path: Path
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Change":
        change = cls(path=path)
        for kind in KINDS.values():
            file = path / kind.filename
            if file.is_file():
                change.artifacts[kind.name] = Artifact.read(kind, file)
        return change

    @property
    def id(self) -> str:
        return self.path.name

    @property
    def root(self) -> Path:
        return self.path.parent.parent

    def get(self, kind: str) -> Artifact | None:
        return self.artifacts.get(kind)

    def upstream(self, artifact: Artifact) -> Artifact | None:
        return self.get(artifact.kind.after) if artifact.kind.after else None

    def doc_hash(self, path: str) -> str | None:
        file = self.root / path
        return content_hash(file.read_text()) if file.is_file() else None

    def context_drift(self, artifact: Artifact) -> list[str]:
        return [
            f"{path} {'was removed' if self.doc_hash(path) is None else f'changed (pinned @{pinned}, now @{self.doc_hash(path)})'}"
            for path, pinned in (artifact.context or {}).items()
            if self.doc_hash(path) != pinned
        ]

    def stale(self, artifact: Artifact) -> bool:
        upstream = self.upstream(artifact)
        return bool(upstream and artifact.pin != upstream.hash) or bool(self.context_drift(artifact))

    def downstream(self, kind: str) -> list[str]:
        chain, current = [], kind
        while current:
            chain.append(current)
            current = next((k.name for k in KINDS.values() if k.after == current), None)
        return chain

    def rewrite(self, artifact: Artifact, **values: str) -> None:
        artifact.path.write_text(artifact.with_meta(**values))
        self.artifacts[artifact.kind.name] = Artifact.read(artifact.kind, artifact.path)

    def pin(self, reaccept: bool = False, context_for: ContextFor | None = None) -> list[str]:
        pinned = []
        for kind in KINDS.values():
            artifact = self.get(kind.name)
            upstream = self.upstream(artifact) if artifact else None
            if not upstream or artifact.status == "rejected" or (artifact.ready and not reaccept):
                continue
            values = {kind.after: f"{upstream.kind.filename}@{upstream.hash}"}
            if kind.has_context and context_for is not None:
                docs = context_for(self, kind.name)
                values["context"] = ", ".join(f"{d}@{self.doc_hash(d)}" for d in docs) or "none"
            if any(artifact.meta.get(k) != v for k, v in values.items()):
                self.rewrite(artifact, **values)
                pinned.append(f"{artifact.path.name} → {', '.join(values.values())}")
        return pinned

    def reopen(self, kind: str) -> list[str]:
        reopened = []
        for name in self.downstream(kind):
            artifact = self.get(name)
            if artifact and artifact.ready:
                self.rewrite(artifact, status="draft")
                reopened.append(artifact.path.name)
        return reopened

    def accept(self, kind: str) -> str:
        artifact = self.get(kind)
        if artifact is None:
            raise ValueError(f"{self.id} has no {kind}.md")
        self.rewrite(artifact, status="accepted")
        return artifact.path.name

    @property
    def implemented(self) -> bool:
        plan = self.get("plan")
        return plan is not None and plan.status == "implemented"

    def implement(self) -> str:
        plan = self.get("plan")
        if plan is None or plan.status != "accepted":
            raise ValueError(f"{self.id} has no accepted plan.md to mark implemented")
        self.rewrite(plan, status="implemented")
        return plan.path.name

    def problems(self) -> list[Finding]:
        found = [] if CHANGE_ID.match(self.id) else [Finding.error(f"{self.path}: change ids use lowercase letters, digits and hyphens only")]
        for artifact in self.artifacts.values():
            found += artifact.problems()
            if artifact.kind.after:
                found += self._chain_problems(artifact)
            if artifact.kind.has_context:
                found += self._context_problems(artifact)
        return found

    def _context_problems(self, artifact: Artifact) -> list[Finding]:
        if artifact.context is None:
            message = f"{artifact.path}: context is not pinned; run `python3 -m opensdlc pin {self.id}`"
            return [Finding.error(message) if artifact.ready else Finding.warning(message)]
        drift = self.context_drift(artifact)
        if not drift or self.implemented:
            return []
        if artifact.ready:
            return [Finding.error(
                f"{artifact.path}: is {artifact.status} against knowledge that has since moved: {'; '.join(drift)}. "
                f"Reopen it with `python3 -m opensdlc reopen {self.id} --from {artifact.kind.name}`, "
                f"or re-pin with `python3 -m opensdlc pin {self.id} --reaccept` if it still holds."
            )]
        return [Finding.warning(f"{artifact.path}: draft is behind its knowledge: {'; '.join(drift)}")]

    def _chain_problems(self, artifact: Artifact) -> list[Finding]:
        upstream = self.upstream(artifact)
        name = artifact.kind.after
        if upstream is None:
            return [Finding.error(f"{artifact.path}: needs {name}.md in the same folder")]
        found = []
        if artifact.ready and upstream.status != "accepted":
            found.append(Finding.error(f"{artifact.path}: cannot be {artifact.status} while {name}.md is {upstream.status or 'unset'}"))
        if artifact.pin is None:
            message = f"{artifact.path}: '{name}' is not pinned; run `python3 -m opensdlc pin {self.id}`"
            found.append(Finding.error(message) if artifact.ready else Finding.warning(message))
        elif artifact.pin != upstream.hash:
            if artifact.ready:
                found.append(Finding.error(
                    f"{artifact.path}: is {artifact.status} against {name}.md@{artifact.pin}, but {name}.md is now @{upstream.hash}. "
                    f"Reopen it with `python3 -m opensdlc reopen {self.id} --from {artifact.kind.name}`, "
                    f"or re-pin with `python3 -m opensdlc pin {self.id} --reaccept` if it still holds."
                ))
            else:
                found.append(Finding.warning(f"{artifact.path}: draft is behind {name}.md (pinned @{artifact.pin}, now @{upstream.hash})"))
        return found
