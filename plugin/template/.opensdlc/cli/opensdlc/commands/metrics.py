# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
from datetime import datetime, timedelta, timezone

from ..config import out_path
from ..metrics import report as indicators
from ..metrics.records import parse_time
from ..metrics.sources import collect
from .base import Command, step_summary


class MetricsCommand(Command):
    name, help = "metrics", "Collect the playbook's leading and lagging indicators"

    def configure(self, parser):
        parser.add_argument("--days", type=int)
        parser.add_argument("--end", help="ISO 8601 end of the window; defaults to now")

    def run(self, args, root, config):
        settings = config.get("metrics", {})
        days = args.days or settings.get("windowDays", 30)
        end = parse_time(args.end) if args.end else datetime.now(timezone.utc)
        adopted = parse_time(settings.get("adoptedAt"))
        since = min(end - timedelta(days=2 * days), (adopted or end) - timedelta(days=days))
        result = indicators.build(collect(root, config, since), end, days, adopted)
        markdown = indicators.markdown(result)
        out_path(root, "metrics.json").write_text(json.dumps(result, indent=2, default=str))
        out_path(root, "metrics.md").write_text(markdown)
        step_summary(markdown)
        print(markdown)
        return 0


COMMANDS: list[Command] = [MetricsCommand()]
