# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

from ..artifacts import KINDS, Change
from ..config import CHANGES_DIR, out_path
from ..knowledge import STAGES, Knowledge
from .base import Command, load_change, print_findings


class CheckCommand(Command):
    name, help = "check", "Validate the artifacts in changes/ and the knowledge base"

    def run(self, args, root, config):
        knowledge = Knowledge(root, config)
        folders = sorted(p for p in (root / CHANGES_DIR).glob("*") if p.is_dir())
        changes = [Change.load(folder) for folder in folders]
        findings = [f for change in changes for f in change.problems() + knowledge.change_problems(change)]
        findings += knowledge.problems()
        errors = print_findings(findings)
        print(f"{len(changes)} changes and {len(knowledge.docs)} knowledge documents checked, {errors} errors, {len(findings) - errors} warnings")
        return 1 if errors else 0


class PinCommand(Command):
    name, help = "pin", "Pin draft artifacts to their upstream artifact and the knowledge that applies"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")
        parser.add_argument("--reaccept", action="store_true", help="also re-pin accepted artifacts; the PR is the re-acceptance record")

    def run(self, args, root, config):
        change = load_change(root, args.change)
        for line in change.pin(args.reaccept, Knowledge(root, config).context_for) or ["already pinned"]:
            print(line)
        return 0


class ReopenCommand(Command):
    name, help = "reopen", "Return an artifact and everything downstream of it to draft"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")
        parser.add_argument("--from", dest="kind", required=True, choices=list(KINDS))

    def run(self, args, root, config):
        for name in load_change(root, args.change).reopen(args.kind) or ["nothing to reopen"]:
            print(name)
        return 0


class AcceptCommand(Command):
    name, help = "accept", "Propose acceptance: set an artifact to accepted so its PR's approvals decide"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")
        parser.add_argument("--kind", required=True, choices=list(KINDS))

    def run(self, args, root, config):
        change = load_change(root, args.change)
        change.pin(False, Knowledge(root, config).context_for)
        print(f"{change.accept(args.kind)} proposed for acceptance; merging the approved PR accepts it")
        return 0


class ImplementCommand(Command):
    name, help = "implement", "Mark a change's accepted plan implemented once its build is ready to merge"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")

    def run(self, args, root, config):
        try:
            print(f"{load_change(root, args.change).implement()} marked implemented")
        except ValueError as error:
            raise SystemExit(str(error))
        return 0


class ContextCommand(Command):
    name, help = "context", "List the knowledge a stage must read for a change, and why"

    def configure(self, parser):
        parser.add_argument("change", help="change id or changes/<id>")
        parser.add_argument("--stage", required=True, choices=STAGES)
        parser.add_argument("--files", default="", help="comma-separated extra paths, such as a PR's changed files")

    def run(self, args, root, config):
        change = load_change(root, args.change)
        files = [f for f in args.files.split(",") if f]
        manifest = Knowledge(root, config).manifest(change, args.stage, files)
        out_path(root, f"context-{change.id}-{args.stage}.md").write_text(manifest)
        print(manifest)
        return 0


class SkillsCommand(Command):
    name, help = "skills", "Regenerate policy skills from knowledge/policies"

    def run(self, args, root, config):
        for path in Knowledge(root, config).generate_skills() or ["all policy skills are current"]:
            print(path)
        return 0


COMMANDS: list[Command] = [CheckCommand(), PinCommand(), ReopenCommand(), AcceptCommand(), ImplementCommand(), ContextCommand(), SkillsCommand()]
