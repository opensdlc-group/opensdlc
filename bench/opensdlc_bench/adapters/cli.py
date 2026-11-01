# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Adapter, AdapterError, Session, fill, provided


def argv(parts: list, args: dict) -> list[str]:
    found = []
    for part in parts:
        if isinstance(part, list):
            found += [fill(p, args) for p in part] if all(provided(p, args) for p in part) else []
        else:
            found.append(fill(part, args))
    return found


class CliSession(Session):
    def __init__(self, adapter: "CliAdapter"):
        self.adapter = adapter
        self.folder = Path(tempfile.mkdtemp(prefix="opensdlc-bench-state-"))
        self.state = self.folder / "state"

    def call(self, op: str, args: dict) -> object:
        spec = self.adapter.spec
        command = [*spec["command"], *argv(self.adapter.operation(op), args)]
        env = {**os.environ, **({spec["stateFile"]: str(self.state)} if "stateFile" in spec else {})}
        try:
            result = subprocess.run(command, cwd=self.adapter.workspace, env=env, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdapterError(f"{' '.join(command)}: {error}") from error
        errors = spec.get("exitCodes", {})
        if str(result.returncode) in errors:
            return {"error": errors[str(result.returncode)]}
        if result.returncode != 0:
            raise AdapterError(f"exit {result.returncode}: {(result.stderr or result.stdout).strip()[-300:]}")
        try:
            return json.loads(result.stdout) if result.stdout.strip() else None
        except ValueError as error:
            raise AdapterError(f"stdout is not JSON: {result.stdout[:200]}") from error

    def close(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


class CliAdapter(Adapter):
    def session(self) -> Session:
        return CliSession(self)
