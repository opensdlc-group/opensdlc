# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .acceptance import CheckResult, run_checks
from .adapters import adapter_for
from .model import Scenario, Target
from .workspace import Workspace


@dataclass(frozen=True)
class Verification:
    target: str
    ci: dict[str, bool]
    checks: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(self.ci.values()) and all(c.status != "fail" for c in self.checks)


def verify_reference(scenario: Scenario, target: Target) -> Verification:
    with tempfile.TemporaryDirectory(prefix=f"opensdlc-bench-verify-{target.name}-") as parent:
        workspace = Workspace.create(target, Path(parent), overlay=target.reference)
        ci = {command: outcome.ok for command, outcome in workspace.ci().items()}
        checks = [c for t in scenario.tickets for c in t.checks]
        return Verification(target.name, ci, run_checks(adapter_for(target.adapter, target.root, workspace.root), target.name, checks))
