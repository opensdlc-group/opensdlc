# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from ..approvals import run_gh
from ..config import out_path
from ..evals import ClaudeCli, Gate, Suite, report
from ..reviewing import GitHubReviews, PullRequestPublisher, Tally, key_counts, publish, rated_comments, tallies, tuning
from .base import Command, github_output, step_summary


class EvalCommand(Command):
    name, help = "eval", "Run the agent eval suite and gate on a drop against main's baseline"

    def configure(self, parser):
        parser.add_argument("--case")
        parser.add_argument("--baseline", help="evals.json from main's last run")
        parser.add_argument("--plugin-dir", type=Path, help="the OpenSDLC plugin to load, as CI checks it out")

    def run(self, args, root, config):
        settings = config.get("evals", {})
        gate = Gate(settings.get("maxDrop", 0.1), settings.get("caseDrop", 0.34), settings.get("floor"))
        agent = ClaudeCli(root / settings["settings"] if settings.get("settings") else None, args.plugin_dir)
        suite = Suite(root, agent, settings.get("timeout", 900), settings.get("repeats", 3))
        results = [suite.run_case(case) for case in suite.cases(args.case)]
        baseline = json.loads(Path(args.baseline).read_text()) if args.baseline and Path(args.baseline).is_file() else None
        data, markdown = report(results, gate, baseline)
        out_path(root, "evals.json").write_text(json.dumps(data, indent=2))
        step_summary(markdown)
        print(markdown)
        return 0 if data["gate"]["ok"] else 1


class ReviewHistoryCommand(Command):
    name, help = "review-history", "Count finding keys from earlier reviews so repeats can be flagged"

    def configure(self, parser):
        parser.add_argument("--pr", type=int)

    def run(self, args, root, config):
        days = config.get("review", {}).get("historyDays", 90)
        prs = GitHubReviews(run_gh).prs((date.today() - timedelta(days=days)).isoformat())
        counts = key_counts(prs, exclude=args.pr)
        out_path(root, "review-history.json").write_text(json.dumps({"days": days, "keys": dict(counts)}, indent=2))
        print(f"{len(counts)} finding keys seen in the last {days} days")
        return 0


class ReviewTuningCommand(Command):
    name, help = "review-tuning", "Rate the reviewer from reactions and suggest REVIEW.md changes"

    def configure(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def run(self, args, root, config):
        github = GitHubReviews(run_gh)
        prs = github.prs((date.today() - timedelta(days=args.days)).isoformat())
        reviewed = tallies(prs)
        repo = github.repo()
        reviewers = frozenset(config.get("metrics", {}).get("agents", {}).get("logins", []))
        rated = [r for number in reviewed for r in rated_comments(github.inline_comments(repo, number), reviewers)]
        data, markdown = tuning(rated, reviewed, config.get("review", {}).get("nitCap", 5))
        out_path(root, "review-tuning.json").write_text(json.dumps(data, indent=2))
        out_path(root, "review-tuning.md").write_text(markdown)
        step_summary(markdown)
        print(markdown)
        return 0


class ReviewPublishCommand(Command):
    name, help = "review-publish", "Post the reviewer's findings inline and its tally on the PR"

    def configure(self, parser):
        parser.add_argument("--pr", type=int, required=True)
        parser.add_argument("--head", required=True)
        parser.add_argument("--tally", required=True)

    def run(self, args, root, config):
        try:
            tally = Tally.of(json.loads(Path(args.tally).read_text()))
        except (OSError, ValueError) as error:
            print(f"The reviewer left no readable tally: {error}", file=sys.stderr)
            return 1
        target = PullRequestPublisher(run_gh, GitHubReviews(run_gh).repo(), args.pr, args.head)
        markdown = publish(tally, target, config.get("review", {}).get("nitCap", 5))
        github_output(important=str(tally.count("important")))
        step_summary(markdown)
        print(markdown)
        return 0


COMMANDS: list[Command] = [EvalCommand(), ReviewHistoryCommand(), ReviewTuningCommand(), ReviewPublishCommand()]
