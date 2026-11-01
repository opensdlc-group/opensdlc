# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

from .context import Context, SessionState
from .paths import matches
from .shell import runs

DEFAULT_IGNORE = ["changes/**", "knowledge/**", "docs/**", "**/*.md", ".opensdlc/**"]


def commands(ctx: Context) -> list[str]:
    return ctx.config.get("verify", {}).get("commands", [])


def record_edit(ctx: Context) -> None:
    if not commands(ctx) or matches(ctx.target, ctx.config.get("verify", {}).get("ignore", DEFAULT_IGNORE)):
        return
    state = SessionState.load(ctx)
    state.pending = list(commands(ctx))
    state.edited = sorted({*state.edited, ctx.target})
    state.blocks = 0
    state.save()


def record_run(ctx: Context) -> None:
    state = SessionState.load(ctx)
    if not state.pending:
        return
    state.pending = [c for c in state.pending if not runs(ctx.command, c)]
    if not state.pending:
        state.edited = []
    state.save()


def stop_reason(ctx: Context) -> str | None:
    state = SessionState.load(ctx)
    if not state.pending:
        return None
    if state.blocks >= ctx.config.get("verify", {}).get("maxBlocks", 3):
        return None
    state.blocks += 1
    state.save()
    files = ", ".join(state.edited[:5]) + (" and more" if len(state.edited) > 5 else "")
    return (
        f"Code changed since verification last passed ({files}). "
        f"Run {' and '.join(f'`{c}`' for c in state.pending)} and fix any failures before finishing. "
        "Only a command that exits 0 on its own counts: no `||`, `;` or pipes."
    )


def stop_warning(ctx: Context) -> str | None:
    state = SessionState.load(ctx)
    if state.pending and state.blocks >= ctx.config.get("verify", {}).get("maxBlocks", 3):
        return f"Finished without passing {', '.join(state.pending)}. Treat this work as unverified."
    return None
