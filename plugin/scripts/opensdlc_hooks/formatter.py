# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import subprocess

from .context import Context
from .paths import matches


def format_target(ctx: Context) -> str | None:
    for rule in ctx.config.get("format", []):
        if matches(ctx.target, rule["paths"]):
            result = subprocess.run(
                [*rule["run"], ctx.target],
                cwd=ctx.root,
                capture_output=True,
                text=True,
                timeout=rule.get("timeout", 30),
            )
            if result.returncode != 0:
                return f"{' '.join(rule['run'])} failed on {ctx.target}:\n{result.stdout}{result.stderr}".strip()
            return None
    return None
