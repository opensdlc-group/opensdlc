# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from collections.abc import Callable

from opensdlc_hooks.context import Context
from opensdlc_hooks.formatter import format_target
from opensdlc_hooks.guards import REGISTRY
from opensdlc_hooks.verify import record_edit, record_run, stop_reason, stop_warning


def emit(payload: dict) -> int:
    print(json.dumps(payload))
    return 0


def guard(name: str) -> Callable[[Context], int]:
    def run(ctx: Context) -> int:
        decision = next((d for d in (g.check(ctx) for g in REGISTRY[name]) if d), None)
        if not decision:
            return 0
        return emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision.verdict,
            "permissionDecisionReason": decision.reason,
        }})
    return run


def edited(ctx: Context) -> int:
    record_edit(ctx)
    failure = format_target(ctx)
    if failure:
        print(failure, file=sys.stderr)
        return 2
    return 0


def ran(ctx: Context) -> int:
    record_run(ctx)
    return 0


def stop(ctx: Context) -> int:
    reason = stop_reason(ctx)
    if reason:
        return emit({"decision": "block", "reason": reason})
    warning = stop_warning(ctx)
    return emit({"systemMessage": warning}) if warning else 0


HANDLERS: dict[str, Callable[[Context], int]] = {
    "files": guard("files"),
    "bash": guard("bash"),
    "tools": guard("tools"),
    "edited": edited,
    "ran": ran,
    "stop": stop,
}


if __name__ == "__main__":
    sys.exit(HANDLERS[sys.argv[1]](Context.load(sys.stdin.read())))
