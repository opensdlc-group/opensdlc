# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .artifacts import KINDS, READY, Artifact, Change
from .config import CHANGES_DIR
from .globs import matches
from .knowledge import plan_files

CHANGE_LINE = re.compile(r"^(?i:change):\s*(?:changes/)?([a-z0-9][a-z0-9-]*)/?\s*$", re.M)


@dataclass(frozen=True)
class PlanMatch:
    ok: bool
    message: str
    extras: tuple[str, ...] = ()


def referenced_changes(changed: list[str], body: str) -> list[str]:
    ids = {Path(p).parts[1] for p in changed if p.startswith(f"{CHANGES_DIR}/") and p.endswith("/plan.md")}
    ids |= set(CHANGE_LINE.findall(body or ""))
    return sorted(ids)


def accepted_at_base(root: Path, change: str, before: Callable[[str], str | None]) -> bool:
    path = f"{CHANGES_DIR}/{change}/plan.md"
    text = before(path)
    return text is not None and Artifact.parse(KINDS["plan"], root / path, text).status in READY


def check(root: Path, changed: list[str], body: str, config: dict, before: Callable[[str], str | None]) -> PlanMatch:
    settings = config.get("planMatch", {})
    ignored = settings.get("ignore", [])
    implementation = [p for p in changed if not p.startswith(f"{CHANGES_DIR}/") and not matches(p, ignored)]
    if not implementation:
        return PlanMatch(True, "No implementation files changed.")
    ids = referenced_changes(changed, body)
    if not ids:
        if settings.get("required"):
            return PlanMatch(False, "This PR changes code but references no change. Add `Change: <id>` to the description, or include the plan.")
        return PlanMatch(True, "No change referenced; plan match not required for this repo.")
    missing = [i for i in ids if not (root / CHANGES_DIR / i / "plan.md").is_file() or not accepted_at_base(root, i, before)]
    if missing:
        return PlanMatch(False, f"Referenced changes have no plan accepted on the base branch: {', '.join(missing)}.")
    listed = [f for i in ids for f in plan_files(Change.load(root / CHANGES_DIR / i).get("plan").section("Files that change"))]
    extras = tuple(p for p in implementation if not matches(p, listed))
    if extras:
        return PlanMatch(False, f"Files changed that no plan lists under Files that change ({', '.join(ids)}). Update the plan in this PR or drop the change.", extras)
    return PlanMatch(True, f"Every changed file is in the plan for {', '.join(ids)}.")
