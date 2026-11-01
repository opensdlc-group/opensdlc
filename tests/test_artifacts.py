# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
import unittest
from pathlib import Path

from support import PLUGIN, temp_project

from opensdlc.artifacts import KINDS, Change
from opensdlc.document import FRONTMATTER, HEADING


def template(kind: str) -> str:
    return (PLUGIN / "skills" / kind / "template.md").read_text()


def filled(kind: str, status: str, **meta) -> str:
    match = FRONTMATTER.match(template(kind))
    fields = {"kind": kind, "status": status, "author": "J. Ortiz", "source": "idea", "ref": "none",
              "started": "2026-10-01T09:00:00Z", "tags": "claims", "intent": "intent.md@<pin>", "context": "<pinned>",
              "spec": "spec.md@<pin>", "risk": "low", "approver": "A. Lee", **meta}
    front = "\n".join(f"{k}: {fields[k]}" for k in (line.split(":")[0] for line in match.group(1).splitlines()))
    body = re.sub(r"^<[^>\n]+>$", "Real content.", match.group(2), flags=re.M).replace("<short title>", "Claims status")
    return f"---\n{front}\n---\n{body}"


def no_context(change_: Change, kind: str) -> list[str]:
    return []


def change(root: Path, pinned: bool = True, context_for=no_context, **artifacts: str) -> Change:
    folder = root / "changes" / "2026-10-claims-status"
    folder.mkdir(parents=True, exist_ok=True)
    for kind, status in artifacts.items():
        (folder / f"{kind}.md").write_text(filled(kind, status))
    loaded = Change.load(folder)
    if pinned:
        loaded.pin(reaccept=True, context_for=context_for)
    return Change.load(folder)


def edit_body(change_: Change, kind: str, extra: str = "\nA late addition.\n") -> Change:
    path = change_.get(kind).path
    path.write_text(path.read_text() + extra)
    return Change.load(change_.path)


def set_status(change_: Change, kind: str, status: str) -> Change:
    artifact = change_.get(kind)
    artifact.path.write_text(artifact.with_meta(status=status))
    return Change.load(change_.path)


def levels(change_: Change) -> list[tuple[str, str]]:
    return [(f.level, f.message) for f in change_.problems()]


def errors(change_: Change) -> list[str]:
    return [m for level, m in levels(change_) if level == "error"]


def warnings(change_: Change) -> list[str]:
    return [m for level, m in levels(change_) if level == "warning"]


class TemplatesMatchTheChecker(unittest.TestCase):
    def test_every_kind_has_a_plugin_template(self):
        for kind in KINDS:
            self.assertTrue((PLUGIN / "skills" / kind / "template.md").is_file(), kind)

    def test_template_sections_are_exactly_the_required_sections(self):
        for name, kind in KINDS.items():
            self.assertEqual(HEADING.findall(template(name)), list(kind.sections), name)

    def test_template_frontmatter_carries_every_required_field(self):
        for name, kind in KINDS.items():
            keys = {line.split(":")[0] for line in FRONTMATTER.match(template(name)).group(1).splitlines()}
            self.assertLessEqual({"kind", "status", *kind.fields}, keys, name)

    def test_unfilled_templates_fail_the_check(self):
        root = temp_project()
        folder = root / "changes" / "x"
        folder.mkdir(parents=True)
        (folder / "intent.md").write_text(template("intent"))
        found = errors(Change.load(folder))
        self.assertTrue(any("'author' still holds a template placeholder" in m for m in found))
        self.assertTrue(any("placeholder" in m for m in found))

    def test_downstream_templates_start_unpinned(self):
        self.assertTrue(FRONTMATTER.match(template("spec")).group(1).count("intent: intent.md@<pin>"))
        self.assertTrue(FRONTMATTER.match(template("plan")).group(1).count("spec: spec.md@<pin>"))


class ChainRules(unittest.TestCase):
    def test_a_complete_pinned_chain_passes(self):
        self.assertEqual(levels(change(temp_project(), intent="accepted", spec="accepted", plan="implemented")), [])

    def test_change_ids_are_lowercase_letters_digits_and_hyphens(self):
        c = change(temp_project(), intent="accepted")
        renamed = c.path.rename(c.path.parent / "Claims Status")
        self.assertTrue(any("change ids use" in m for m in errors(Change.load(renamed))))

    def test_spec_needs_an_intent(self):
        self.assertTrue(any("needs intent.md" in m for m in errors(change(temp_project(), spec="draft"))))

    def test_accepted_plan_needs_accepted_spec(self):
        found = errors(change(temp_project(), intent="accepted", spec="draft", plan="accepted"))
        self.assertTrue(any("cannot be accepted while spec.md is draft" in m for m in found))

    def test_draft_downstream_of_draft_is_fine(self):
        self.assertEqual(levels(change(temp_project(), intent="draft", spec="draft")), [])

    def test_invalid_status_and_risk_are_reported(self):
        root = temp_project()
        folder = root / "changes" / "y"
        folder.mkdir(parents=True)
        (folder / "intent.md").write_text(filled("intent", "accepted"))
        (folder / "spec.md").write_text(filled("spec", "accepted"))
        (folder / "plan.md").write_text(filled("plan", "done", risk="medium"))
        found = errors(Change.load(folder))
        self.assertTrue(any("status must be one of" in m for m in found))
        self.assertTrue(any("risk must be one of" in m for m in found))


class Pins(unittest.TestCase):
    def test_pin_writes_a_content_hash_of_the_upstream(self):
        c = change(temp_project(), intent="accepted", spec="draft")
        self.assertEqual(c.get("spec").meta["intent"], f"intent.md@{c.get('intent').hash}")
        self.assertRegex(c.get("spec").meta["intent"], r"^intent\.md@[0-9a-f]{12}$")

    def test_missing_pin_warns_on_drafts_and_fails_accepted(self):
        c = change(temp_project(), pinned=False, intent="accepted", spec="draft")
        self.assertTrue(any("'intent' is not pinned" in m for m in warnings(c)))
        self.assertTrue(any("context is not pinned" in m for m in warnings(c)))
        self.assertEqual(errors(c), [])
        c = set_status(c, "spec", "accepted")
        self.assertTrue(any("'intent' is not pinned" in m for m in errors(c)))
        self.assertTrue(any("context is not pinned" in m for m in errors(c)))

    def test_status_changes_do_not_stale_downstream(self):
        c = change(temp_project(), intent="draft", spec="draft")
        c = set_status(c, "intent", "accepted")
        self.assertFalse(c.stale(c.get("spec")))
        self.assertEqual(levels(c), [])

    def test_editing_an_accepted_intent_fails_its_accepted_spec(self):
        c = change(temp_project(), intent="accepted", spec="accepted", plan="accepted")
        c = edit_body(c, "intent")
        found = errors(c)
        self.assertEqual(len(found), 1)
        self.assertIn("spec.md: is accepted against intent.md@", found[0])
        self.assertIn("reopen 2026-10-claims-status --from spec", found[0])
        self.assertIn("--reaccept", found[0])

    def test_stale_draft_is_only_a_warning(self):
        c = change(temp_project(), intent="accepted", spec="draft")
        c = edit_body(c, "intent")
        self.assertEqual(errors(c), [])
        self.assertTrue(any("draft is behind intent.md" in m for m in warnings(c)))

    def test_pin_leaves_accepted_artifacts_alone_without_reaccept(self):
        c = edit_body(change(temp_project(), intent="accepted", spec="accepted"), "intent")
        self.assertEqual(c.pin(context_for=no_context), [])
        self.assertTrue(c.stale(c.get("spec")))
        self.assertEqual(len(c.pin(reaccept=True, context_for=no_context)), 1)
        self.assertEqual(levels(Change.load(c.path)), [])

    def test_pinning_cascades_in_order(self):
        c = change(temp_project(), pinned=False, intent="accepted", spec="draft", plan="draft")
        c.pin(context_for=no_context)
        c = Change.load(c.path)
        self.assertFalse(c.stale(c.get("spec")))
        self.assertFalse(c.stale(c.get("plan")))

    def test_reopen_returns_the_chain_to_draft_and_keeps_pins_valid(self):
        c = change(temp_project(), intent="accepted", spec="accepted", plan="implemented")
        self.assertEqual(c.reopen("spec"), ["spec.md", "plan.md"])
        c = Change.load(c.path)
        self.assertEqual((c.get("spec").status, c.get("plan").status), ("draft", "draft"))
        self.assertFalse(c.stale(c.get("plan")))

    def test_reopen_resolves_the_stale_error(self):
        c = edit_body(change(temp_project(), intent="accepted", spec="accepted", plan="accepted"), "intent")
        c.reopen("spec")
        c = Change.load(c.path)
        self.assertEqual(errors(c), [])

    def test_rejected_artifacts_are_never_pinned_or_reopened(self):
        c = edit_body(change(temp_project(), intent="accepted", spec="rejected"), "intent")
        self.assertEqual(c.pin(reaccept=True, context_for=no_context), [])
        self.assertEqual(c.reopen("spec"), [])



class ContextPins(unittest.TestCase):
    def policy(self, root: Path, text: str = "Never log card numbers.") -> str:
        path = root / "knowledge" / "policies" / "pci.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nkind: policy\nowner: @org/security\nreview-by: 2099-01-01\ndescription: Card data\n---\n# PCI\n\n{text}\n")
        return "knowledge/policies/pci.md"

    def test_pin_records_the_knowledge_each_artifact_was_written_against(self):
        root = temp_project()
        doc = self.policy(root)
        c = change(root, context_for=lambda ch, kind: [doc], intent="accepted", spec="accepted")
        self.assertRegex(c.get("spec").meta["context"], r"^knowledge/policies/pci\.md@[0-9a-f]{12}$")
        self.assertEqual(c.get("spec").context, {doc: c.doc_hash(doc)})

    def test_policy_change_fails_accepted_specs_built_on_it(self):
        root = temp_project()
        doc = self.policy(root)
        c = change(root, context_for=lambda ch, kind: [doc], intent="accepted", spec="accepted")
        self.policy(root, "Never store card numbers either.")
        found = errors(Change.load(c.path))
        self.assertEqual(len(found), 1)
        self.assertIn("knowledge that has since moved: knowledge/policies/pci.md changed", found[0])

    def test_knowledge_that_moves_after_a_change_is_implemented_is_history(self):
        root = temp_project()
        doc = self.policy(root)
        c = change(root, context_for=lambda ch, kind: [doc], intent="accepted", spec="accepted", plan="accepted")
        self.assertEqual(c.implement(), "plan.md")
        self.policy(root, "Never store card numbers either.")
        self.assertEqual(errors(Change.load(c.path)), [])

    def test_only_an_accepted_plan_can_be_marked_implemented(self):
        c = change(temp_project(), intent="accepted", spec="accepted", plan="draft")
        with self.assertRaisesRegex(ValueError, "no accepted plan.md"):
            c.implement()
        self.assertEqual(Change.load(c.path).get("plan").status, "draft")

    def test_reviewing_a_policy_without_changing_it_does_not_stale_anything(self):
        root = temp_project()
        doc = self.policy(root)
        c = change(root, context_for=lambda ch, kind: [doc], intent="accepted", spec="accepted")
        path = root / doc
        path.write_text(path.read_text().replace("review-by: 2099-01-01", "review-by: 2099-06-01"))
        self.assertEqual(errors(Change.load(c.path)), [])

    def test_removed_policy_is_reported(self):
        root = temp_project()
        doc = self.policy(root)
        c = change(root, context_for=lambda ch, kind: [doc], intent="accepted", spec="draft")
        (root / doc).unlink()
        self.assertTrue(any("pci.md was removed" in m for m in warnings(Change.load(c.path))))

    def test_accept_proposes_acceptance(self):
        c = change(temp_project(), intent="accepted", spec="draft")
        self.assertEqual(c.accept("spec"), "spec.md")
        self.assertEqual(Change.load(c.path).get("spec").status, "accepted")


if __name__ == "__main__":
    unittest.main()
