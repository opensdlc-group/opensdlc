# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import os
from abc import ABC, abstractmethod
from pathlib import Path

from ..artifacts import Change, Finding
from ..config import CHANGES_DIR


def github_output(**values: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as handle:
            handle.writelines(f"{key}={value}\n" for key, value in values.items())


def step_summary(markdown: str) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a") as handle:
            handle.write(markdown + "\n")


def load_change(root: Path, ref: str) -> Change:
    folder = root / CHANGES_DIR / Path(ref).name
    if not folder.is_dir():
        raise SystemExit(f"No change folder at {folder}")
    return Change.load(folder)


def print_findings(findings: list[Finding]) -> int:
    annotate = bool(os.environ.get("GITHUB_ACTIONS"))
    for finding in findings:
        print(f"::{finding.level}::{finding.message}" if annotate else f"{finding.level}: {finding.message}")
    return sum(f.level == "error" for f in findings)


class Command(ABC):
    name: str
    help: str

    def configure(self, parser: argparse.ArgumentParser) -> None:
        pass

    @abstractmethod
    def run(self, args: argparse.Namespace, root: Path, config: dict) -> int: ...
