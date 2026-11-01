# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .paths import relative

CONFIG_PATH = ".opensdlc/config.json"
LOCK_DIR = ".opensdlc/locks"
TEST_LOCK = f"{LOCK_DIR}/tests.json"
STATE_DIR = ".opensdlc/state"


@dataclass(frozen=True)
class Context:
    event: dict
    root: Path
    config: dict = field(default_factory=dict)

    @classmethod
    def load(cls, raw: str) -> "Context":
        event = json.loads(raw or "{}")
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
        config_file = root / CONFIG_PATH
        config = json.loads(config_file.read_text()) if config_file.is_file() else {}
        return cls(event=event, root=root, config=config)

    @property
    def tool(self) -> str:
        return self.event.get("tool_name", "")

    @property
    def tool_input(self) -> dict:
        return self.event.get("tool_input") or {}

    @property
    def session(self) -> str:
        return self.event.get("session_id", "")

    @property
    def target(self) -> str:
        path = self.tool_input.get("file_path") or self.tool_input.get("notebook_path") or ""
        return self.relative(path) if path else ""

    def relative(self, path: str) -> str:
        return relative(path, self.root)

    @property
    def written_text(self) -> str:
        data = self.tool_input
        parts = [data.get("content"), data.get("new_string"), data.get("new_source")]
        parts += [edit.get("new_string") for edit in data.get("edits") or []]
        return "\n".join(p for p in parts if p)

    @property
    def command(self) -> str:
        return self.tool_input.get("command", "")

    def test_lock_active(self) -> bool:
        lock = self.root / TEST_LOCK
        if not lock.is_file():
            return False
        try:
            return json.loads(lock.read_text()).get("session") == self.session
        except json.JSONDecodeError:
            return True


@dataclass
class SessionState:
    path: Path
    pending: list[str] = field(default_factory=list)
    edited: list[str] = field(default_factory=list)
    blocks: int = 0

    @classmethod
    def load(cls, ctx: Context) -> "SessionState":
        path = ctx.root / STATE_DIR / f"{ctx.session or 'unknown'}.json"
        if not path.is_file():
            return cls(path=path)
        data = json.loads(path.read_text())
        return cls(path=path, pending=data.get("pending", []), edited=data.get("edited", []), blocks=data.get("blocks", 0))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"pending": self.pending, "edited": self.edited, "blocks": self.blocks}))
