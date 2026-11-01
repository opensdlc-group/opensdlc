# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import unittest

from opensdlc.reviewing import GitHubReviews, PullRequestPublisher, Tally, key_counts, publish, rated_comments, tallies, tuning


def pr(number, findings, nit=0):
    tally = {"important": len(findings), "nit": nit, "findings": findings}
    return {"number": number, "comments": [{"body": "older"}, {"body": f"summary <!-- opensdlc:review {json.dumps(tally)} -->"}]}


def inline(axis, severity, key, up=0, down=0, login="github-actions[bot]"):
    return {"user": {"login": login}, "body": f"**[{axis} · {severity} · {key}]** detail", "reactions": {"+1": up, "-1": down}}


class History(unittest.TestCase):
    def test_keys_are_counted_across_other_prs(self):
        prs = [pr(1, [{"key": "money-as-float"}]), pr(2, [{"key": "money-as-float"}, {"key": "pii-in-logs"}]), pr(3, [{"key": "pii-in-logs"}])]
        self.assertEqual(key_counts(prs, exclude=3), {"money-as-float": 2, "pii-in-logs": 1})

    def test_a_key_counts_once_per_pr(self):
        self.assertEqual(key_counts([pr(1, [{"key": "a"}, {"key": "a"}])]), {"a": 1})

    def test_prs_without_a_tally_are_skipped(self):
        self.assertEqual(tallies([{"number": 9, "comments": [{"body": "lgtm"}]}]), {})


class Tuning(unittest.TestCase):
    def test_precision_comes_from_reactions_on_tagged_comments(self):
        rated = rated_comments([
            inline("spec", "important", "missing-auth", up=3),
            inline("standards", "nit", "naming", down=2),
            inline("standards", "nit", "naming", down=1, up=0),
            {"user": {"login": "pat"}, "body": "a human comment", "reactions": {"+1": 5}},
            inline("security", "important", "x", up=1, login="pat"),
        ], frozenset({"github-actions[bot]"}))
        data, markdown = tuning(rated, {1: {"nit": 6}, 2: {"nit": 5}}, nit_cap=5)
        self.assertEqual(data["precision"], {"spec": 1.0, "standards": 0.0})
        self.assertTrue(any("Tighten the standards axis" in s for s in data["suggestions"]))
        self.assertTrue(any("Nits average 5.5" in s for s in data["suggestions"]))
        self.assertTrue(any("`naming` were voted down 2 times" in s for s in data["suggestions"]))
        self.assertIn("**spec**: 100% useful", markdown)

    def test_no_ratings_asks_people_to_react(self):
        _, markdown = tuning([], {}, 5)
        self.assertIn("react 👍 or 👎", markdown)


def finding(severity="important", key="missing-auth-check", line=12, **extra):
    return {"axis": "security", "severity": severity, "key": key, "file": "src/a.ts", "line": line, "summary": "No auth.", **extra}


class FakeTarget:
    def __init__(self, placeable):
        self.placeable = placeable
        self.inlined = []
        self.posted = None

    def inline(self, f):
        self.inlined.append(f.key)
        return f.key in self.placeable

    def upsert(self, body):
        self.posted = body


class Publishing(unittest.TestCase):
    def test_counts_come_from_valid_findings_not_the_agents_totals(self):
        tally = Tally.of({"important": 9, "nit": 9, "findings": [finding(), finding(axis="vibes"), finding(key="Bad Key"), "junk", finding("nit", "naming")]})
        self.assertEqual((tally.count("important"), tally.count("nit")), (1, 1))
        self.assertEqual(tally.marker()["axes"], {"standards": 0, "spec": 0, "security": 2})

    def test_nits_are_capped_and_unplaceable_findings_go_in_the_summary(self):
        tally = Tally.of({"findings": [finding(), finding("nit", "a"), finding("nit", "b"), finding(key="whole-file", line=None)]})
        target = FakeTarget({"a"})
        markdown = publish(tally, target, nit_cap=1)
        self.assertEqual(target.inlined, ["missing-auth-check", "a"])
        self.assertIn("#### Findings not on a changed line", markdown)
        self.assertIn("`src/a.ts:12` No auth.", markdown)
        self.assertIn("**[security · important · whole-file]** `src/a.ts` No auth.", markdown)
        self.assertEqual(target.posted, markdown)

    def test_repeats_suggest_agents_md_rules_and_the_marker_round_trips(self):
        tally = Tally.of({"agentsMdOutdated": True, "findings": [finding(repeat=True, suggestedRule="Routes go through requireAuth() --> always.")]})
        markdown = tally.markdown([])
        self.assertIn("- `missing-auth-check`: Routes go through requireAuth() --> always.", markdown)
        self.assertIn("makes `AGENTS.md` outdated", markdown)
        self.assertEqual(tallies([{"number": 1, "comments": [{"body": markdown}]}])[1], tally.marker())

    def test_inline_comments_carry_the_rating_tag(self):
        f = Tally.of({"findings": [finding(policy="secure-api-review")]}).findings[0]
        self.assertEqual(rated_comments([{"user": {"login": "bot"}, "body": f.comment(), "reactions": {"+1": 1}}], frozenset())[0].key, "missing-auth-check")


class Client(unittest.TestCase):
    def test_a_rejected_inline_comment_is_reported_not_raised(self):
        def shell(args):
            raise RuntimeError("line not in diff")
        f = Tally.of({"findings": [finding()]}).findings[0]
        self.assertFalse(PullRequestPublisher(shell, "o/r", 4, "abc").inline(f))

    def test_the_tally_comment_is_edited_in_place(self):
        calls = []

        def shell(args):
            calls.append(args)
            if args[1].endswith("/issues/4/comments") and "--slurp" in args:
                return json.dumps([[{"id": 7, "user": {"type": "Bot"}, "body": '<!-- opensdlc:review {"important": 0} -->'},
                                    {"id": 8, "user": {"type": "User"}, "body": '<!-- opensdlc:review {"important": 5} -->'}]])
            return "{}"
        PullRequestPublisher(shell, "o/r", 4, "abc").upsert("new")
        self.assertEqual(calls[-1], ["api", "-X", "PATCH", "repos/o/r/issues/comments/7", "-f", "body=new"])

    def test_inline_comments_flatten_paginated_pages(self):
        github = GitHubReviews(lambda args: json.dumps([[{"id": 1}], [{"id": 2}]]))
        self.assertEqual([c["id"] for c in github.inline_comments("o/r", 4)], [1, 2])


if __name__ == "__main__":
    unittest.main()
