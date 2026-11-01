# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

from ..approvals import ApprovalRules, Directory, approvers, evaluate, pull_request, report
from ..gitio import Git
from ..knowledge import Knowledge
from .base import Command, step_summary


class ApprovalsCommand(Command):
    name, help = "approvals", "Fail unless every artifact this PR accepts has its required approvals"

    def configure(self, parser):
        parser.add_argument("--pr", type=int, required=True)
        parser.add_argument("--base", required=True)

    def run(self, args, root, config):
        rules = ApprovalRules(root, config, args.base, Knowledge(root, config))
        requirements = rules.requirements(Git(root).changed(args.base, "HEAD"))
        excluded = frozenset(login.lower() for login in config.get("metrics", {}).get("agents", {}).get("logins", []))
        approved = approvers(pull_request(args.pr), excluded) if requirements else frozenset()
        verdicts = evaluate(requirements, approved, Directory())
        markdown = report(verdicts)
        step_summary(markdown)
        print(markdown)
        return 0 if all(v.met for v in verdicts) else 1


COMMANDS: list[Command] = [ApprovalsCommand()]
