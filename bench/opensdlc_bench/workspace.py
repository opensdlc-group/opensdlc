# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .model import Target
from .paths import TEMPLATE

IGNORED = shutil.ignore_patterns("__pycache__", "out", "state", "locks", "node_modules", "dist")
CI = ("make build", "make test", "make lint")
TEMPLATE_EXAMPLES = ("knowledge/policies/secure-api.md", ".claude/skills/secure-api-review")
SANDBOX_PLACEHOLDERS = (".bash_profile", ".bashrc", ".claude.json", ".gitconfig", ".gitmodules", ".idea", ".mcp.json", ".profile",
                        ".ripgreprc", ".vscode", ".zprofile", ".zshrc", "CLAUDE.local.md")
SCRIPTED_GROUPS = {"product-owners": ["po"], "tech-leads": ["lead"], "engineers": ["eng"]}


def restore_scripts(source: Path, root: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file() and path.read_bytes()[:2] == b"#!":
            copied = root / path.relative_to(source)
            copied.chmod(copied.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class WorkspaceError(Exception):
    pass


@dataclass(frozen=True)
class Outcome:
    ok: bool
    output: str


class Workspace:
    def __init__(self, root: Path):
        self.root = root

    @classmethod
    def create(cls, target: Target, parent: Path, overlay: Path | None = None) -> "Workspace":
        root = parent / "repo"
        shutil.copytree(TEMPLATE, root, ignore=IGNORED)
        for example in TEMPLATE_EXAMPLES:
            if (root / example).is_dir():
                shutil.rmtree(root / example)
            else:
                (root / example).unlink()
        for source in (target.shared, target.skeleton, overlay):
            if source and source.is_dir():
                shutil.copytree(source, root, dirs_exist_ok=True, ignore=IGNORED)
                restore_scripts(source, root)
        workspace = cls(root)
        workspace.configure(target)
        skills = workspace.opensdlc("skills")
        if not skills.ok:
            raise WorkspaceError(f"opensdlc skills failed: {skills.output[-500:]}")
        for command in target.setup:
            outcome = workspace.sh(command, timeout=600)
            if not outcome.ok:
                raise WorkspaceError(f"setup `{command}` failed: {outcome.output[-500:]}")
        workspace.git("init", "-q", "-b", "main")
        with (root / ".git" / "info" / "exclude").open("a") as exclude:
            exclude.write("\n".join(SANDBOX_PLACEHOLDERS) + "\n")
        workspace.commit("Adopt OpenSDLC")
        return workspace

    def configure(self, target: Target) -> None:
        path = self.root / ".opensdlc" / "config.json"
        config = json.loads(path.read_text())
        config["approvals"]["groups"] = SCRIPTED_GROUPS
        if target.build_tools:
            for role in ("build", "verify"):
                stage = config["stages"][role]
                stage["allowedTools"] = f"{stage['allowedTools']},{target.build_tools}"
        path.write_text(json.dumps(config, indent=2) + "\n")

    def git(self, *args: str, env: dict | None = None) -> str:
        result = subprocess.run(["git", "-C", str(self.root), "-c", "user.name=OpenSDLC bench", "-c", "user.email=bench@opensdlc.invalid", *args],
                                capture_output=True, text=True, env={**os.environ, **(env or {})})
        if result.returncode != 0:
            raise WorkspaceError(f"git {' '.join(args[:3])}: {(result.stderr or result.stdout).strip()[:500]}")
        return result.stdout

    def sh(self, command: str, timeout: int = 900) -> Outcome:
        try:
            result = subprocess.run(command, shell=True, cwd=self.root, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return Outcome(False, f"`{command}` timed out after {timeout}s")
        return Outcome(result.returncode == 0, (result.stdout + result.stderr).strip())

    def opensdlc(self, *args: str, env: dict | None = None) -> Outcome:
        result = subprocess.run(["python3", "-P", "-m", "opensdlc", *args], cwd=self.root, capture_output=True, text=True,
                                env={**os.environ, "PYTHONPATH": ".opensdlc/cli", **(env or {})})
        return Outcome(result.returncode == 0, (result.stdout + result.stderr).strip())

    def ci(self) -> dict[str, Outcome]:
        return {command: self.sh(command) for command in CI}

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def out(self, name: str) -> Path:
        path = self.root / ".opensdlc" / "out" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def commit(self, message: str) -> bool:
        self.git("add", "-A")
        if not self.git("status", "--porcelain").strip():
            return False
        self.git("commit", "-q", "-m", message)
        return True

    def snapshot(self) -> Path:
        pristine = Path(tempfile.mkdtemp(prefix="opensdlc-bench-git-")) / "pristine.git"
        shutil.copytree(self.root / ".git", pristine, symlinks=True)
        return pristine

    def capture(self, pristine: Path) -> str:
        env = {"GIT_DIR": str(pristine), "GIT_WORK_TREE": str(self.root)}
        self.git("add", "-A", env=env)
        patch = self.git("diff", "--cached", "--binary", env=env)
        shutil.rmtree(pristine.parent, ignore_errors=True)
        return patch

    def reset(self) -> None:
        self.git("reset", "-q", "--hard", "HEAD")
        self.git("clean", "-q", "-fd")

    def restore(self) -> None:
        self.git("checkout", "-q", "--", ".")
        self.git("clean", "-q", "-fd")

    def apply(self, patch: str, change: str, allow: str = "") -> Outcome:
        if not patch.strip():
            return Outcome(True, "empty patch")
        scratch = Path(tempfile.mkdtemp(prefix="opensdlc-bench-patch-"))
        (scratch / "agent.patch").write_text(patch)
        index = {"GIT_INDEX_FILE": str(scratch / "agent.index")}
        try:
            self.git("read-tree", "HEAD", env=index)
            self.git("apply", "--cached", str(scratch / "agent.patch"), env=index)
            checked = self.opensdlc("patch-check", "--allow", allow, "--change", change, env=index)
            if not checked.ok:
                return checked
            self.git("apply", "--index", str(scratch / "agent.patch"))
            return checked
        except WorkspaceError as error:
            return Outcome(False, str(error))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def staged_changes(self) -> list[str]:
        return [p for p in self.git("diff", "--cached", "--name-only", "-z").split("\0") if p]

    def changed_since(self, base: str) -> list[str]:
        return [p for p in self.git("diff", "--name-only", "-z", base, "HEAD").split("\0") if p]
