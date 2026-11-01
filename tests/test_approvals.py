# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import unittest
from pathlib import Path

from support import git, git_repo, temp_project
from test_artifacts import change, set_status
from test_knowledge import policy

from opensdlc import planmatch
from opensdlc.approvals import ApprovalRules, Directory, approvers, evaluate, report, required_reviewers
from opensdlc.artifacts import Change
from opensdlc.gitio import Git
from opensdlc.knowledge import Knowledge

CONFIG = {
    "approvals": {
        "groups": {"product-owners": ["@org/po"], "tech-leads": ["@org/leads"], "engineers": ["alice", "bob"]},
        "rules": {"intent": {"require": ["product-owners"]}, "spec": {"require": ["product-owners"], "high": ["tech-leads"]},
                  "plan": {"require": ["engineers"], "high": ["tech-leads"]}},
    },
    "knowledge": {"sources": ["knowledge/"]},
}
TEAMS = {"org/po": "pat\npriya", "org/leads": "lee", "org/security": "sam"}


def fake_gh(args):
    team = args[1].removeprefix("orgs/").replace("/teams/", "/").removesuffix("/members")
    if team not in TEAMS:
        raise RuntimeError("HTTP 404")
    return TEAMS[team]


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


HEAD_OID = "c0ffee"


def review(login, state, at="2026-10-20T00:00:00Z", oid=HEAD_OID):
    return {"author": {"login": login}, "state": state, "submittedAt": at, "commit": {"oid": oid}}


class Requirements(unittest.TestCase):
    def setUp(self):
        self.root = git_repo(temp_project(CONFIG))
        policy(self.root)
        self.change = change(self.root, intent="accepted", spec="draft")
        self.base = commit(self.root, "draft spec")

    def requirements(self):
        rules = ApprovalRules(self.root, CONFIG, self.base, Knowledge(self.root, CONFIG))
        return rules.requirements(Git(self.root).changed(self.base, "HEAD"))

    def test_nothing_needs_approval_until_something_is_proposed_for_acceptance(self):
        spec = self.change.get("spec")
        spec.path.write_text(spec.text + "\nMore detail.\n")
        commit(self.root, "edit draft")
        self.assertEqual(self.requirements(), [])

    def test_accepting_a_high_risk_spec_needs_product_owner_tech_lead_and_policy_owner(self):
        spec = self.change.get("spec")
        text = spec.with_meta(status="accepted", risk="high").replace("## Concerns\nReal content.", "## Concerns\n- **Auth** (policy: secure-api-review): gap.")
        spec.path.write_text(text)
        commit(self.root, "propose spec")
        found = {(r.group, r.entries) for r in self.requirements()}
        self.assertEqual(found, {("product-owners", ("@org/po",)), ("tech-leads", ("@org/leads",)), ("owner of secure-api", ("@org/security",))})

    def test_reaccepting_changed_content_needs_approval_but_implemented_does_not(self):
        set_status(self.change, "spec", "accepted")
        plan_change = change(self.root, intent="accepted", spec="accepted", plan="accepted")
        base = commit(self.root, "accepted")
        plan = plan_change.get("plan")
        plan.path.write_text(plan.with_meta(status="implemented"))
        commit(self.root, "implemented")
        rules = ApprovalRules(self.root, CONFIG, base, Knowledge(self.root, CONFIG))
        self.assertEqual(rules.requirements(Git(self.root).changed(base, "HEAD")), [])
        spec = Change.load(plan_change.path).get("spec")
        spec.path.write_text(spec.text + "\nChanged after acceptance.\n")
        commit(self.root, "reaccept")
        groups = [r.group for r in rules.requirements(Git(self.root).changed(base, "HEAD"))]
        self.assertEqual(groups, ["product-owners"])

    def test_rewriting_a_plan_while_marking_it_implemented_needs_approval(self):
        set_status(self.change, "spec", "accepted")
        plan_change = change(self.root, intent="accepted", spec="accepted", plan="accepted")
        base = commit(self.root, "accepted")
        plan = plan_change.get("plan")
        plan.path.write_text(plan.with_meta(status="implemented").replace("## Files that change\nReal content.", "## Files that change\n- `**`: everything"))
        commit(self.root, "implemented with a wider plan")
        rules = ApprovalRules(self.root, CONFIG, base, Knowledge(self.root, CONFIG))
        self.assertEqual([r.group for r in rules.requirements(Git(self.root).changed(base, "HEAD"))], ["engineers"])

    def test_moving_a_knowledge_document_out_still_needs_its_owner(self):
        (self.root / "docs").mkdir()
        git(self.root, "mv", "knowledge/policies/secure-api.md", "docs/secure-api.md")
        commit(self.root, "move")
        self.assertEqual([(r.subject, r.entries) for r in self.requirements()], [("knowledge/policies/secure-api.md", ("@org/security",))])

    def test_paths_with_spaces_and_unicode_are_read_whole(self):
        folder = self.root / "changes" / "café plan"
        folder.mkdir()
        (folder / "plan.md").write_text("x")
        commit(self.root, "odd path")
        self.assertIn("changes/café plan/plan.md", Git(self.root).changed(self.base, "HEAD"))

    def test_knowledge_changes_need_the_existing_owner(self):
        policy(self.root, owner="@org/someone-else", description="Loosened")
        commit(self.root, "policy change")
        found = self.requirements()
        self.assertEqual([(r.subject, r.entries) for r in found], [("knowledge/policies/secure-api.md", ("@org/security",))])

    def test_reviewers_for_requesting_review(self):
        spec = self.change.get("spec")
        spec.path.write_text(spec.with_meta(risk="high"))
        rules = ApprovalRules(self.root, CONFIG, "HEAD", Knowledge(self.root, CONFIG))
        users, teams = required_reviewers(rules.for_artifact("changes/2026-10-claims-status/spec.md", Change.load(self.change.path).get("spec")))
        self.assertEqual((users, teams), ([], ["leads", "po"]))


class Evaluation(unittest.TestCase):
    def test_latest_review_wins_and_authors_agents_and_bots_never_count(self):
        pr = {"author": {"login": "claude[bot]"}, "headRefOid": HEAD_OID, "reviews": [
            review("pat", "APPROVED", "2026-10-20T01:00:00Z"),
            review("pat", "CHANGES_REQUESTED", "2026-10-20T02:00:00Z"),
            review("priya", "APPROVED"),
            review("claude", "APPROVED"),
            review("github-actions[bot]", "APPROVED"),
            review("lee", "COMMENTED"),
        ]}
        self.assertEqual(approvers(pr, frozenset({"claude"})), frozenset({"priya"}))

    def test_bots_never_count_however_their_login_is_spelled(self):
        pr = {"author": {"login": "pat"}, "headRefOid": HEAD_OID, "reviews": [
            review("github-actions", "APPROVED"),
            {**review("renovate", "APPROVED"), "author": {"login": "renovate", "is_bot": True}},
            review("lee", "APPROVED"),
        ]}
        self.assertEqual(approvers(pr, frozenset({"github-actions[bot]"})), frozenset({"lee"}))

    def test_the_author_cannot_approve_their_own_acceptance(self):
        pr = {"author": {"login": "pat"}, "headRefOid": HEAD_OID, "reviews": [review("pat", "APPROVED")]}
        self.assertEqual(approvers(pr, frozenset()), frozenset())

    def test_an_approval_of_an_earlier_commit_does_not_count(self):
        pr = {"author": {"login": "pat"}, "headRefOid": HEAD_OID, "reviews": [
            review("priya", "APPROVED", oid="0ld"),
            review("lee", "APPROVED"),
        ]}
        self.assertEqual(approvers(pr, frozenset()), frozenset({"lee"}))

    def test_each_group_needs_one_of_its_own_members(self):
        root = git_repo(temp_project(CONFIG))
        c = change(root, intent="accepted", spec="draft")
        base = commit(root, "draft")
        spec = c.get("spec")
        spec.path.write_text(spec.with_meta(status="accepted", risk="high"))
        commit(root, "propose")
        requirements = ApprovalRules(root, CONFIG, base, Knowledge(root, CONFIG)).requirements(Git(root).changed(base, "HEAD"))
        verdicts = evaluate(requirements, frozenset({"priya"}), Directory(fake_gh))
        self.assertEqual({v.requirement.group: v.met for v in verdicts}, {"product-owners": True, "tech-leads": False})
        self.assertIn("❌", report(verdicts))
        verdicts = evaluate(requirements, frozenset({"priya", "lee"}), Directory(fake_gh))
        self.assertTrue(all(v.met for v in verdicts))

    def test_unreadable_teams_explain_how_to_fix_it(self):
        with self.assertRaises(RuntimeError) as raised:
            Directory(fake_gh).members("@org/unknown")
        self.assertIn("OPENSDLC_ORG_TOKEN", str(raised.exception))

    def test_plain_logins_need_no_lookup(self):
        self.assertEqual(Directory(fake_gh).resolve(("alice", "@Bob")), frozenset({"alice", "bob"}))


class PlanMatch(unittest.TestCase):
    def setUp(self):
        self.root = temp_project({})
        c = change(self.root, intent="accepted", spec="accepted", plan="accepted")
        plan = c.get("plan")
        plan.path.write_text(plan.text.replace("## Files that change\nReal content.", "## Files that change\n- `src/claims/status.py`: new\n- `tests/test_status.py`: new"))

    def check(self, changed, body="", config=None, before=None):
        return planmatch.check(self.root, changed, body, config or {}, before or self.committed)

    def committed(self, path):
        file = self.root / path
        return file.read_text() if file.is_file() else None

    def test_artifact_only_prs_pass(self):
        self.assertTrue(self.check(["changes/2026-10-claims-status/spec.md"]).ok)

    def test_unreferenced_code_passes_unless_required(self):
        self.assertTrue(self.check(["src/x.py"]).ok)
        self.assertFalse(self.check(["src/x.py"], config={"planMatch": {"required": True}}).ok)

    def test_files_outside_the_plan_fail(self):
        result = self.check(["src/claims/status.py", "src/other.py"], "Change: 2026-10-claims-status")
        self.assertFalse(result.ok)
        self.assertEqual(result.extras, ("src/other.py",))

    def test_matching_files_pass_whether_referenced_by_body_or_by_the_plan_in_the_diff(self):
        self.assertTrue(self.check(["src/claims/status.py", "tests/test_status.py"], "Change: changes/2026-10-claims-status/").ok)
        self.assertTrue(self.check(["src/claims/status.py", "changes/2026-10-claims-status/plan.md"]).ok)

    def test_the_plan_must_be_accepted_on_the_base_branch(self):
        def draft(path):
            return self.committed(path).replace("status: accepted", "status: draft")
        body = "Change: 2026-10-claims-status"
        self.assertFalse(self.check(["src/claims/status.py"], body, before=draft).ok)
        self.assertFalse(self.check(["src/claims/status.py"], body, before=lambda path: None).ok)

    def test_only_valid_change_ids_are_read_from_the_body(self):
        self.assertEqual(planmatch.referenced_changes([], "Change: ..\nchange: 2026-10-a\nChange: Upper\nChange: changes/2026-10-b/"), ["2026-10-a", "2026-10-b"])

    def test_ignored_paths_and_missing_plans(self):
        self.assertTrue(self.check(["package-lock.json"], "Change: 2026-10-claims-status", {"planMatch": {"ignore": ["**/package-lock.json", "package-lock.json"]}}).ok)
        self.assertFalse(self.check(["src/a.py"], "Change: 2026-10-nothing").ok)


if __name__ == "__main__":
    unittest.main()
