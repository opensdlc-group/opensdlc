# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
import sys
from pathlib import Path

from .. import planmatch
from ..approvals import ApprovalRules, required_reviewers
from ..artifacts import KINDS, Change
from ..config import CHANGES_DIR, out_path
from ..gating import REPORT_FILE, Evidence, Verdict
from ..gitio import Git
from ..knowledge import Knowledge
from ..pipeline import accepted_intents, next_actions, patch_problems
from .base import Command, github_output, load_change, step_summary

PLUGIN_REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
PLUGIN_REF = re.compile(r"^[\w./-]+$")


class PluginCommand(Command):
    name, help = "plugin", "Print the OpenSDLC plugin repository and ref this repository pins, for CI to load"

    def run(self, args, root, config):
        pinned = config.get("plugin", {})
        repository, ref = pinned.get("repository", ""), pinned.get("ref", "")
        if not PLUGIN_REPOSITORY.match(repository) or not PLUGIN_REF.match(ref):
            raise SystemExit("Set plugin.repository (owner/name) and plugin.ref (a tag or commit) in .opensdlc/config.json")
        github_output(repository=repository, ref=ref, pin=f"{repository}@{ref}")
        print(f"{repository}@{ref}")
        return 0


class AdvanceCommand(Command):
    name, help = "advance", "List the stage runs a push makes due, as a GitHub matrix"

    def configure(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", required=True)

    def run(self, args, root, config):
        git = Git(root)
        changed = git.changed(args.base, args.head)
        try:
            actions = next_actions(root, changed, config)
        except ValueError as error:
            raise SystemExit(str(error)) from None
        links = accepted_intents(root, changed, lambda path: git.show(args.base, path))
        matrix = json.dumps({"include": [a.as_matrix_entry() for a in actions]})
        github_output(matrix=matrix, count=str(len(actions)), links=json.dumps(links), linkCount=str(len(links)))
        print(matrix)
        return 0


class PatchCheckCommand(Command):
    name, help = "patch-check", "Refuse a staged agent patch that leaves its scope, touches human-only paths or adds links"

    def configure(self, parser):
        parser.add_argument("--allow", default="", help="comma-separated globs the patch may touch; empty allows any path a human need not change")
        parser.add_argument("--change", required=True, help="the change id this run works on, or 'new' when it may create one change folder")

    def run(self, args, root, config):
        git = Git(root)
        entries = git.staged()
        existing = git.folders("HEAD", CHANGES_DIR.as_posix())
        problems = patch_problems(entries, [g for g in args.allow.split(",") if g], args.change, existing, config)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        print(f"{len(entries)} paths in the agent's patch, all allowed")
        return 0


class PlanMatchCommand(Command):
    name, help = "plan-match", "Fail when a PR changes files its change's plan does not list"

    def configure(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", default="HEAD")
        parser.add_argument("--body-file")

    def run(self, args, root, config):
        git = Git(root)
        changed = git.changed(args.base, args.head)
        body = Path(args.body_file).read_text() if args.body_file else ""
        result = planmatch.check(root, changed, body, config, lambda path: git.show(args.base, path))
        lines = [f"### Plan match: {'passed' if result.ok else 'failed'}", "", result.message]
        lines += [f"- `{path}`" for path in result.extras]
        markdown = "\n".join(lines)
        step_summary(markdown)
        print(markdown)
        return 0 if result.ok else 1


class ReviewersCommand(Command):
    name, help = "reviewers", "Print who must approve an artifact, for requesting their review"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")
        parser.add_argument("--kind", required=True, choices=list(KINDS))

    def run(self, args, root, config):
        change = load_change(root, args.change)
        artifact = change.get(args.kind)
        if artifact is None:
            raise SystemExit(f"{change.id} has no {args.kind}.md")
        rules = ApprovalRules(root, config, "HEAD", Knowledge(root, config))
        users, teams = required_reviewers(rules.for_artifact(artifact.path.relative_to(root).as_posix(), artifact))
        github_output(users=",".join(users), teams=",".join(teams))
        print(json.dumps({"users": users, "teams": teams}))
        return 0


class ReviewContextCommand(Command):
    name, help = "review-context", "List the knowledge a PR review must apply, from its changes and files"

    def configure(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", default="HEAD")
        parser.add_argument("--body-file")

    def run(self, args, root, config):
        changed = Git(root).changed(args.base, args.head)
        body = Path(args.body_file).read_text() if args.body_file else ""
        changes = [Change.load(root / CHANGES_DIR / i) for i in planmatch.referenced_changes(changed, body) if (root / CHANGES_DIR / i).is_dir()]
        manifest = Knowledge(root, config).review_manifest(changes, changed)
        out_path(root, "context-review.md").write_text(manifest)
        print(manifest)
        return 0


class GateCheckCommand(Command):
    name, help = "gate-check", "Decide whether a stage run escalates, from the confidence gate's verdict and the checks that need no judgement"

    def configure(self, parser):
        parser.add_argument("--stage", required=True, choices=["spec", "plan", "build"])
        parser.add_argument("--change", required=True, help="change id or changes/<id>")
        parser.add_argument("--out", type=Path, help="folder holding gate.json and verify.md; defaults to .opensdlc/out")

    def run(self, args, root, config):
        out = args.out or out_path(root, REPORT_FILE).parent
        evidence = Evidence(args.stage, out, load_change(root, args.change), tuple(Git(root).staged()), tuple(config.get("tests", [])))
        verdict = Verdict.judge(evidence)
        (out / REPORT_FILE).write_text(verdict.markdown())
        github_output(escalate=str(verdict.escalate).lower())
        print(json.dumps(verdict.as_json()))
        return 0


COMMANDS: list[Command] = [PluginCommand(), AdvanceCommand(), PatchCheckCommand(), PlanMatchCommand(), ReviewersCommand(), ReviewContextCommand(), GateCheckCommand()]
