# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import unittest
from datetime import date
from pathlib import Path

from support import temp_project
from test_artifacts import change

from opensdlc.cli import main
from opensdlc.knowledge import Knowledge

CONFIG = {"knowledge": {"sources": ["knowledge/", "docs/adr/"], "always": ["GLOSSARY.md"], "reviewWarnDays": 14, "graceDays": 14}}
TODAY = date(2026, 10, 26)


def doc(root: Path, path: str, front: dict, body: str = "# Title\n\n## Rules\n- Rule one.\n") -> str:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("---\n" + "\n".join(f"{k}: {v}" for k, v in front.items()) + "\n---\n" + body)
    return path


def policy(root: Path, **extra) -> str:
    front = {"kind": "policy", "owner": "@org/security", "review-by": "2027-01-01", "description": "Secure external APIs",
             "systems": "claims-api", "tags": "api", "paths": "src/api/**", "skill": "secure-api-review", **extra}
    return doc(root, "knowledge/policies/secure-api.md", front, "# Secure API\n\n## Rules\n- Every endpoint needs auth.\n")


class Selection(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)
        (self.root / "GLOSSARY.md").write_text("## Claim\nA request for payment.\n")
        policy(self.root)
        doc(self.root, "knowledge/architecture/portal.md", {"kind": "architecture", "owner": "@org/web", "review-by": "2027-01-01", "systems": "portal"})
        doc(self.root, "docs/adr/0001-postgres.md", {"kind": "decision", "paths": "db/**"})
        self.change = change(self.root, intent="accepted", spec="draft", plan="draft")

    def knowledge(self):
        return Knowledge(self.root, CONFIG, TODAY)

    def selected(self, stage, files=None):
        current = type(self.change).load(self.change.path)
        return {s.path: s for s in self.knowledge().select(current, stage, files)}

    def test_intent_text_and_tags_select_documents(self):
        intent = self.change.get("intent")
        intent.path.write_text(intent.text.replace("## Affected users and systems\nReal content.", "## Affected users and systems\nThe Claims-API and its callers."))
        found = self.selected("spec")
        self.assertIn("system claims-api", found["knowledge/policies/secure-api.md"].reasons)
        self.assertNotIn("knowledge/architecture/portal.md", found)

    def test_plan_files_select_by_path(self):
        plan = self.change.get("plan")
        plan.path.write_text(plan.text.replace("## Files that change\nReal content.", "## Files that change\n- `db/schema.sql`: add column"))
        self.assertIn("path db/schema.sql", self.selected("plan")["docs/adr/0001-postgres.md"].reasons)
        self.assertNotIn("docs/adr/0001-postgres.md", self.selected("spec"))

    def test_review_can_add_the_pr_files(self):
        self.assertIn("path src/api/routes.py", self.selected("review", ["src/api/routes.py"])["knowledge/policies/secure-api.md"].reasons)

    def test_glossary_is_read_but_never_pinned(self):
        glossary = self.selected("spec")["GLOSSARY.md"]
        self.assertFalse(glossary.pinned)
        self.assertNotIn("GLOSSARY.md", self.knowledge().context_for(self.change, "spec"))

    def test_stages_limit_where_a_document_applies(self):
        policy(self.root, stages="review", tags="claims")
        self.assertIn("knowledge/policies/secure-api.md", self.selected("review"))
        self.assertNotIn("knowledge/policies/secure-api.md", self.selected("spec"))

    def test_review_manifest_merges_changes_and_pr_files(self):
        manifest = self.knowledge().review_manifest([], ["src/api/routes.py"])
        self.assertIn("# Context for review of this PR", manifest)
        self.assertIn("`knowledge/policies/secure-api.md` (pinned): path src/api/routes.py", manifest)

    def test_manifest_says_what_to_read_and_why(self):
        policy(self.root, tags="claims")
        manifest = self.knowledge().manifest(self.change, "spec")
        self.assertIn("`knowledge/policies/secure-api.md` (pinned): tag claims", manifest)
        self.assertIn("`GLOSSARY.md`: read for every stage", manifest)


class Links(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)
        policy(self.root, tags="claims", requires="0002-tokens")
        doc(self.root, "docs/adr/0001-sessions.md", {"kind": "decision", "paths": "src/auth/**"})
        doc(self.root, "docs/adr/0002-tokens.md", {"kind": "decision", "supersedes": "0001-sessions", "requires": "0003-keys"})
        doc(self.root, "docs/adr/0003-keys.md", {"kind": "decision", "stages": "review"})
        self.change = change(self.root, intent="accepted", spec="draft", plan="draft")

    def knowledge(self, config=CONFIG):
        return Knowledge(self.root, config, TODAY)

    def messages(self, config=CONFIG):
        return [f.message for f in self.knowledge(config).problems()]

    def test_a_selected_document_brings_what_it_requires(self):
        found = {s.path: s for s in self.knowledge().select(self.change, "spec")}
        self.assertEqual(found["docs/adr/0002-tokens.md"].reasons, ["required by secure-api"])
        self.assertEqual(found["docs/adr/0003-keys.md"].reasons, ["required by 0002-tokens"])
        self.assertIn("docs/adr/0003-keys.md", self.knowledge().context_for(self.change, "spec"))

    def test_a_superseded_document_is_never_selected(self):
        found = [s.path for s in self.knowledge().select(self.change, "review", ["src/auth/login.py"])]
        self.assertNotIn("docs/adr/0001-sessions.md", found)

    def test_a_document_keeps_its_own_reasons_when_also_required(self):
        doc(self.root, "docs/adr/0002-tokens.md", {"kind": "decision", "tags": "claims"})
        found = {s.path: s for s in self.knowledge().select(self.change, "spec")}
        self.assertEqual(found["docs/adr/0002-tokens.md"].reasons, ["tag claims", "required by secure-api"])

    def test_sound_links_pass_the_check(self):
        self.assertEqual([m for m in self.messages() if "requires" in m or "supersede" in m], [])

    def test_broken_links_fail_the_check(self):
        doc(self.root, "docs/adr/0003-keys.md", {"kind": "decision", "requires": "missing, 0001-sessions", "supersedes": "0003-keys"})
        messages = self.messages()
        self.assertIn("docs/adr/0003-keys.md: requires unknown document 'missing'", messages)
        self.assertIn("docs/adr/0003-keys.md: requires '0001-sessions', which '0002-tokens' supersedes", messages)
        self.assertIn("docs/adr/0003-keys.md: a document cannot supersede itself", messages)

    def test_a_loop_of_requirements_fails_the_check_once(self):
        doc(self.root, "docs/adr/0003-keys.md", {"kind": "decision", "requires": "secure-api"})
        loops = [m for m in self.messages() if "forms a loop" in m]
        self.assertEqual(loops, ["knowledge: requires forms a loop: 0002-tokens → 0003-keys → secure-api → 0002-tokens"])

    def test_tags_outside_the_configured_list_fail_the_check(self):
        config = {"knowledge": {**CONFIG["knowledge"], "tags": ["api", "billing"]}}
        self.assertIn("knowledge/policies/secure-api.md: tag 'claims' is not in knowledge.tags", self.messages(config))
        self.assertEqual([f.message for f in self.knowledge(config).change_problems(self.change)],
                         [f"{self.change.id}/intent.md: tag 'claims' is not in knowledge.tags"])
        self.assertEqual([m for m in self.messages() if "knowledge.tags" in m], [])


class Health(unittest.TestCase):
    def test_required_fields_by_kind(self):
        root = temp_project(CONFIG)
        doc(root, "knowledge/policies/x.md", {"kind": "policy"})
        doc(root, "knowledge/domain/y.md", {"kind": "glossary"})
        messages = [f.message for f in Knowledge(root, CONFIG, TODAY).problems()]
        self.assertTrue(any("x.md: missing 'owner'" in m for m in messages))
        self.assertTrue(any("x.md: missing 'review-by'" in m for m in messages))
        self.assertTrue(any("y.md: kind must be one of" in m for m in messages))

    def test_review_by_warns_then_fails_after_the_grace_period(self):
        root = temp_project(CONFIG)
        path = doc(root, "knowledge/architecture/a.md", {"kind": "architecture", "owner": "@o/t", "review-by": "2026-11-01"})
        levels = lambda when: [f.level for f in Knowledge(root, CONFIG, when).problems() if path in f.message]
        self.assertEqual(levels(date(2026, 10, 1)), [])
        self.assertEqual(levels(date(2026, 10, 26)), ["warning"])
        self.assertEqual(levels(date(2026, 11, 10)), ["warning"])
        self.assertEqual(levels(date(2026, 11, 20)), ["error"])

    def test_duplicate_names_are_rejected(self):
        root = temp_project(CONFIG)
        doc(root, "knowledge/a/x.md", {"kind": "decision"})
        doc(root, "knowledge/b/x.md", {"kind": "decision"})
        self.assertTrue(any("two documents are named 'x'" in f.message for f in Knowledge(root, CONFIG, TODAY).problems()))


class PolicySkills(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)
        self.policy = policy(self.root)
        self.knowledge = Knowledge(self.root, CONFIG, TODAY)
        self.skill = self.root / ".claude" / "skills" / "secure-api-review" / "SKILL.md"

    def test_generation_writes_a_skill_from_the_policy(self):
        self.assertEqual(self.knowledge.generate_skills(), [".claude/skills/secure-api-review/SKILL.md"])
        text = self.skill.read_text()
        self.assertTrue(text.startswith("---\nname: secure-api-review\ndescription: Secure external APIs. Applies the Secure API policy owned by @org/security.\n---\n"))
        self.assertIn("Every endpoint needs auth.", text)
        self.assertIn("opensdlc:generated from knowledge/policies/secure-api.md@", text)
        self.assertEqual(self.knowledge.generate_skills(), [])

    def test_missing_edited_or_stale_skills_fail_the_check(self):
        self.assertTrue(any("out of date" in f.message for f in self.knowledge.skill_problems()))
        self.knowledge.generate_skills()
        self.assertEqual(self.knowledge.skill_problems(), [])
        self.skill.write_text(self.skill.read_text() + "\nA hand edit.\n")
        self.assertTrue(any("out of date" in f.message for f in self.knowledge.skill_problems()))
        self.knowledge.generate_skills()
        policy(self.root, description="Secure every external API")
        self.assertTrue(any("out of date" in f.message for f in self.knowledge.skill_problems()))

    def test_orphaned_generated_skills_are_reported_but_hand_written_ones_are_not(self):
        self.knowledge.generate_skills()
        (self.root / self.policy).unlink()
        hand = self.root / ".claude" / "skills" / "mine" / "SKILL.md"
        hand.parent.mkdir(parents=True)
        hand.write_text("---\nname: mine\ndescription: Mine\n---\nHand written.\n")
        messages = [f.message for f in self.knowledge.skill_problems()]
        self.assertEqual(len(messages), 1)
        self.assertIn("secure-api-review", messages[0])

    def test_skills_command(self):
        self.assertEqual(main(["--root", str(self.root), "skills"]), 0)
        self.assertTrue(self.skill.is_file())


class Concerns(unittest.TestCase):
    def test_concerns_resolve_policy_owners_and_flag_unknown_policies(self):
        root = temp_project(CONFIG)
        policy(root)
        c = change(root, intent="accepted", spec="draft")
        spec = c.get("spec")
        spec.path.write_text(spec.text.replace("## Concerns\nReal content.", "## Concerns\n- **Logs** (policy: secure-api-review): tokens in logs.\n- **Retention** (policy: data-retention): unclear.\n- **Copy** (no policy): wording."))
        reloaded = type(c).load(c.path)
        knowledge = Knowledge(root, CONFIG, TODAY)
        owners, unknown = knowledge.concern_owners(reloaded)
        self.assertEqual(owners, {"secure-api": "@org/security"})
        self.assertEqual(unknown, ["data-retention"])
        self.assertIn("unknown policy 'data-retention'", knowledge.change_problems(reloaded)[0].message)

    def test_a_policy_cited_by_its_title_or_with_a_rule_still_needs_its_owner(self):
        root = temp_project(CONFIG)
        policy(root)
        c = change(root, intent="accepted", spec="draft")
        spec = c.get("spec")
        spec.path.write_text(spec.text.replace("## Concerns\nReal content.", "## Concerns\n- **Logs** (policy: Secure API, rule 1; ADR 0004): tokens in logs.\n- **Auth** (policy: secure-api): new route."))
        owners, unknown = Knowledge(root, CONFIG, TODAY).concern_owners(type(c).load(c.path))
        self.assertEqual((owners, unknown), ({"secure-api": "@org/security"}, []))


if __name__ == "__main__":
    unittest.main()
