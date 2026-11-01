# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys

from ..config import out_path
from ..monitor import run_monitor
from .base import Command, github_output

ACTIONABLE = ("diagnose", "propose")


class MonitorCommand(Command):
    name, help = "monitor", "Evaluate control bands and list breaches that need Claude"

    def configure(self, parser):
        parser.add_argument("--name")

    def run(self, args, root, config):
        actionable = []
        for monitor in config.get("monitors", []):
            if args.name in (None, monitor["name"]):
                result = run_monitor(monitor)
                out_path(root, f"monitor-{monitor['name']}.json").write_text(json.dumps(result, indent=2))
                print(f"{result['monitor']}: tier={result['tier']} action={result['action']} rules={','.join(result['rules']) or '-'} {result['note']}".rstrip())
                if result["action"] in ACTIONABLE:
                    actionable.append(result)
        github_output(matrix=json.dumps({"include": actionable}), count=str(len(actionable)))
        return 0


class RunbookCommand(Command):
    name, help = "runbook", "Print the inputs of a runbook Claude requested, if the breached tier pre-approves it"

    def configure(self, parser):
        parser.add_argument("--monitor", required=True)
        parser.add_argument("--tier", required=True)
        parser.add_argument("--request", default=".opensdlc/out/runbook.json")

    def run(self, args, root, config):
        request = root / args.request
        if not request.is_file():
            return 0
        try:
            wanted = str(json.loads(request.read_text())["runbook"])
        except (ValueError, KeyError, TypeError) as error:
            print(f"Unreadable runbook request: {error}", file=sys.stderr)
            return 1
        monitor = next((m for m in config.get("monitors", []) if m["name"] == args.monitor), {})
        tier = monitor.get("tiers", {}).get(args.tier, {})
        allowed = {r["name"]: r.get("inputs", {}) for r in tier.get("runbooks", [])} if tier.get("action") == "propose" else {}
        if wanted not in allowed:
            print(f"Runbook '{wanted}' is not pre-approved for {args.monitor} at {args.tier}: {sorted(allowed)}", file=sys.stderr)
            return 1
        github_output(runbook=wanted, inputs=json.dumps(allowed[wanted]))
        print(wanted)
        return 0


COMMANDS: list[Command] = [MonitorCommand(), RunbookCommand()]
