# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
from dataclasses import dataclass
from pathlib import Path

ZERO_SHA = "0" * 40
LINK_MODES = {"120000", "160000"}


@dataclass(frozen=True)
class StagedEntry:
    path: str
    modes: tuple[str, ...]
    status: str

    @property
    def link(self) -> bool:
        return bool(LINK_MODES & set(self.modes))


class Git:
    def __init__(self, root: Path):
        self.root = root

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=check)

    def changed(self, base: str, head: str) -> list[str]:
        if base == ZERO_SHA:
            listed = self.run("ls-tree", "-r", "-z", "--name-only", head).stdout
        else:
            listed = self.run("diff", "--name-only", "-z", "--no-renames", f"{base}...{head}").stdout
        return [path for path in listed.split("\0") if path]

    def show(self, ref: str, path: str) -> str | None:
        result = self.run("show", f"{ref}:{path}", check=False)
        return result.stdout if result.returncode == 0 else None

    def folders(self, ref: str, path: str) -> set[str]:
        listed = self.run("ls-tree", "-d", "-z", "--name-only", ref, f"{path}/").stdout
        return {Path(entry).name for entry in listed.split("\0") if entry}

    def staged(self) -> list[StagedEntry]:
        fields = self.run("diff", "--cached", "--raw", "-z", "--no-renames").stdout.split("\0")
        entries = []
        for meta, path in zip(fields[::2], fields[1::2]):
            parts = meta[1:].split()
            entries.append(StagedEntry(path, tuple(parts[:2]), parts[4]))
        return entries
