# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugin"
TEMPLATE = PLUGIN / "template"
CLI = TEMPLATE / ".opensdlc" / "cli"
HOOK = PLUGIN / "scripts" / "hook.py"
BENCH = REPO / "bench"

SCRATCH = Path(tempfile.mkdtemp(prefix="opensdlc-tests-"))

sys.path.insert(0, str(CLI))
sys.path.insert(0, str(BENCH))
atexit.register(shutil.rmtree, SCRATCH, ignore_errors=True)


def temp_project(config: dict | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="project-", dir=SCRATCH))
    if config is not None:
        (root / ".opensdlc").mkdir()
        (root / ".opensdlc" / "config.json").write_text(json.dumps(config))
    return root


def git(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True, env=env).stdout.strip()


def git_repo(root: Path) -> Path:
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


def run_hook(root: Path, mode: str, event: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    payload = {"session_id": "s1", "cwd": str(root), "hook_event_name": "PreToolUse", **event}
    return subprocess.run(
        [sys.executable, str(HOOK), mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root), **(env or {})},
    )


def decision(result: subprocess.CompletedProcess) -> str | None:
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
