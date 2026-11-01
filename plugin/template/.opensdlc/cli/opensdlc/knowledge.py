# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .artifacts import Change, Finding
from .document import Document
from .globs import matches

STAGES = ("intent", "spec", "plan", "build", "review")
REQUIRED = {
    "policy": ("owner", "review-by", "description"),
    "architecture": ("owner", "review-by"),
    "domain": ("owner", "review-by"),
    "decision": (),
}
GENERATED = re.compile(r"<!-- opensdlc:generated from (?P<source>\S+)@[0-9a-f]{12}\.")
CONCERN_POLICY = re.compile(r"\(policy:\s*([^),;]+)")
FILE_LINE = re.compile(r"^\s*(?:[-*]\s+)?`?([^\s`]+)`?")


def reference(text: str) -> str:
    return re.sub(r"\s+", "-", text.strip().lower())


def plan_files(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        token = FILE_LINE.match(line)
        if token and ("/" in token.group(1) or "." in token.group(1)) and not token.group(1).startswith("<"):
            found.append(token.group(1).rstrip(":,"))
    return found


@dataclass(frozen=True)
class KnowledgeDoc:
    document: Document
    relpath: str

    @property
    def kind(self) -> str:
        return self.document.meta.get("kind", "")

    @property
    def name(self) -> str:
        return self.document.meta.get("name") or Path(self.relpath).stem

    @property
    def title(self) -> str:
        heading = re.search(r"^# (.+)$", self.document.body, re.M)
        return heading.group(1).strip() if heading else self.name

    @property
    def owner(self) -> str:
        return self.document.meta.get("owner", "")

    @property
    def stages(self) -> list[str]:
        return self.document.listed("stages") or list(STAGES)

    @property
    def review_by(self) -> date | None:
        try:
            return date.fromisoformat(self.document.meta.get("review-by", ""))
        except ValueError:
            return None

    @property
    def skill(self) -> str:
        return self.document.meta.get("skill", "")

    def reasons(self, signals: "Signals") -> list[str]:
        meta = self.document.meta
        found = []
        if meta.get("always", "").lower() == "true":
            found.append("always applies")
        found += [f"system {s}" for s in self.document.listed("systems") if re.search(rf"\b{re.escape(s.lower())}\b", signals.text)]
        found += [f"tag {t}" for t in self.document.listed("tags") if t.lower() in signals.tags]
        globs = self.document.listed("paths")
        found += [f"path {f}" for f in signals.files if globs and matches(f, globs)]
        return found

    def problems(self, today: date, warn: int, grace: int) -> list[Finding]:
        where = self.relpath
        found = [Finding.error(f"{where}: missing '{f}'") for f in REQUIRED.get(self.kind, ()) if not self.document.meta.get(f)]
        if self.kind not in REQUIRED:
            return [Finding.error(f"{where}: kind must be one of {', '.join(REQUIRED)}")]
        due = self.review_by
        if "review-by" in REQUIRED[self.kind] and self.document.meta.get("review-by") and due is None:
            found.append(Finding.error(f"{where}: review-by must be a date (YYYY-MM-DD)"))
        elif due and today > due + timedelta(days=grace):
            found.append(Finding.error(f"{where}: review was due {due}; {self.owner or 'its owner'} must review it and move review-by"))
        elif due and today >= due - timedelta(days=warn):
            found.append(Finding.warning(f"{where}: review due {due} ({self.owner or 'no owner'})"))
        if self.skill and self.kind != "policy":
            found.append(Finding.error(f"{where}: only policies generate skills"))
        return found


@dataclass(frozen=True)
class Signals:
    text: str
    tags: frozenset[str]
    files: tuple[str, ...]

    @classmethod
    def from_change(cls, change: Change, stage: str, extra_files: list[str] | None = None) -> "Signals":
        intent, spec, plan = change.get("intent"), change.get("spec"), change.get("plan")
        parts = []
        if intent:
            parts += [intent.section("Affected users and systems"), intent.section("Problem"), intent.section("Constraints")]
        if spec and stage != "intent":
            parts += [spec.section("Solution"), spec.section("Implementation Decisions")]
        files = list(extra_files or [])
        if plan and stage in ("plan", "build", "review"):
            files += plan_files(plan.section("Files that change"))
        tags = {t.lower() for t in (intent.document.listed("tags") if intent else [])}
        return cls(" ".join(parts).lower(), frozenset(tags), tuple(files))


@dataclass(frozen=True)
class Selection:
    path: str
    reasons: list[str]
    pinned: bool


@dataclass
class Knowledge:
    root: Path
    config: dict
    today: date = field(default_factory=date.today)

    @property
    def settings(self) -> dict:
        return self.config.get("knowledge", {})

    @property
    def docs(self) -> list[KnowledgeDoc]:
        found = []
        for source in self.settings.get("sources", ["knowledge/"]):
            for file in sorted((self.root / source).rglob("*.md")):
                document = Document.read(file)
                if document.meta.get("kind"):
                    found.append(KnowledgeDoc(document, file.relative_to(self.root).as_posix()))
        return found

    def select(self, change: Change, stage: str, extra_files: list[str] | None = None) -> list[Selection]:
        return self.select_signals(Signals.from_change(change, stage, extra_files), stage)

    def select_signals(self, signals: "Signals", stage: str) -> list[Selection]:
        chosen = [Selection(path, ["read for every stage"], False) for path in self.settings.get("always", []) if (self.root / path).is_file()]
        for doc in self.docs:
            if stage in doc.stages:
                reasons = doc.reasons(signals)
                if reasons:
                    chosen.append(Selection(doc.relpath, reasons, True))
        return chosen

    def context_for(self, change: Change, kind: str) -> list[str]:
        return [s.path for s in self.select(change, kind) if s.pinned]

    def by_reference(self) -> dict[str, KnowledgeDoc]:
        return {reference(alias): doc for doc in self.docs for alias in (doc.title, doc.skill, doc.name) if alias}

    def concern_owners(self, change: Change) -> tuple[dict[str, str], list[str]]:
        spec = change.get("spec")
        if not spec:
            return {}, []
        known = self.by_reference()
        cited = list(dict.fromkeys(reference(c) for c in CONCERN_POLICY.findall(spec.section("Concerns"))))
        return {known[c].name: known[c].owner for c in cited if c in known}, [c for c in cited if c not in known]

    def skill_path(self, doc: KnowledgeDoc) -> Path:
        return self.root / self.settings.get("skillsDir", ".claude/skills") / doc.skill / "SKILL.md"

    def skill_text(self, doc: KnowledgeDoc) -> str:
        body = re.sub(r"\A\s*# .+\n", "", doc.document.body).strip()
        description = doc.document.meta.get("description", "").rstrip(".")
        return (
            f"---\nname: {doc.skill}\n"
            f"description: {description}. Applies the {doc.title} policy owned by {doc.owner}.\n---\n"
            f"<!-- opensdlc:generated from {doc.relpath}@{doc.document.hash}. Edit the policy, then run `python3 -m opensdlc skills`. -->\n"
            f"# {doc.title}\n\n{body}\n"
        )

    def policies_with_skills(self) -> list[KnowledgeDoc]:
        return [d for d in self.docs if d.kind == "policy" and d.skill]

    def generate_skills(self) -> list[str]:
        written = []
        for doc in self.policies_with_skills():
            path = self.skill_path(doc)
            text = self.skill_text(doc)
            if not path.is_file() or path.read_text() != text:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                written.append(path.relative_to(self.root).as_posix())
        return written

    def skill_problems(self) -> list[Finding]:
        found = []
        expected = {self.skill_path(d): d for d in self.policies_with_skills()}
        for path, doc in expected.items():
            if not path.is_file() or path.read_text() != self.skill_text(doc):
                found.append(Finding.error(f"{path.relative_to(self.root)}: out of date with {doc.relpath}; run `python3 -m opensdlc skills`"))
        skills_dir = self.root / self.settings.get("skillsDir", ".claude/skills")
        for path in sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []:
            if path not in expected and GENERATED.search(path.read_text()):
                found.append(Finding.error(f"{path.relative_to(self.root)}: generated from a policy that no longer declares it; delete it"))
        return found

    def problems(self) -> list[Finding]:
        warn, grace = self.settings.get("reviewWarnDays", 14), self.settings.get("graceDays", 14)
        found = [f for doc in self.docs for f in doc.problems(self.today, warn, grace)]
        names = [d.name for d in self.docs]
        found += [Finding.error(f"knowledge: two documents are named '{n}'") for n in sorted({n for n in names if names.count(n) > 1})]
        return found + self.skill_problems()

    def change_problems(self, change: Change) -> list[Finding]:
        _, unknown = self.concern_owners(change)
        return [Finding.error(f"{change.id}/spec.md: Concerns cite unknown policy '{name}'") for name in unknown]

    def manifest(self, change: Change, stage: str, extra_files: list[str] | None = None) -> str:
        return self.render(f"{change.id} at {stage}", self.select(change, stage, extra_files))

    def review_manifest(self, changes: list[Change], files: list[str]) -> str:
        chosen: dict[str, Selection] = {}
        signals = [Signals.from_change(c, "review", files) for c in changes] or [Signals("", frozenset(), tuple(files))]
        for signal in signals:
            for selection in self.select_signals(signal, "review"):
                known = chosen.get(selection.path)
                reasons = sorted({*(known.reasons if known else []), *selection.reasons})
                chosen[selection.path] = Selection(selection.path, reasons, selection.pinned)
        return self.render(f"review of {', '.join(c.id for c in changes) or 'this PR'}", list(chosen.values()))

    def render(self, subject: str, chosen: list[Selection]) -> str:
        lines = [f"# Context for {subject}", "", "Read every document below before writing. Pinned documents are recorded in the artifact's `context`.", ""]
        lines += [f"- `{s.path}`{' (pinned)' if s.pinned else ''}: {', '.join(s.reasons)}" for s in chosen]
        if not any(s.pinned for s in chosen):
            lines += ["", "No knowledge documents apply. If one should, its `systems`, `tags` or `paths` need updating."]
        return "\n".join(lines) + "\n"
