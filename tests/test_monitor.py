# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
import unittest
from unittest import mock

from opensdlc.monitor import Detector, GithubCiFailureRate, run_monitor

BASELINE = [0.10, 0.12, 0.09, 0.11, 0.10, 0.08, 0.12, 0.11, 0.09, 0.10]
CALM = [0.10, 0.11, 0.09, 0.12, 0.10, 0.09, 0.11, 0.10]


class WesternElectric(unittest.TestCase):
    def test_calm_series_is_quiet(self):
        verdict = Detector("up").evaluate("ci", BASELINE + CALM)
        self.assertEqual(verdict.tier, "none")
        self.assertEqual(verdict.rules, [])

    def test_single_spike_is_three_sigma(self):
        verdict = Detector("up").evaluate("ci", BASELINE + CALM[:-1] + [0.40])
        self.assertEqual(verdict.tier, "3sigma")
        self.assertIn("beyond-3sigma", verdict.rules)

    def test_two_of_three_beyond_two_sigma(self):
        verdict = Detector("up").evaluate("ci", BASELINE + CALM[:-3] + [0.135, 0.10, 0.135])
        self.assertEqual(verdict.tier, "2sigma")
        self.assertIn("2-of-3-beyond-2sigma", verdict.rules)

    def test_slow_drift_is_caught(self):
        verdict = Detector("up").evaluate("ci", BASELINE + [0.105] * 8)
        self.assertIn("8-in-a-row-one-side", verdict.rules)
        self.assertEqual(verdict.tier, "2sigma")

    def test_direction_up_ignores_improvements(self):
        self.assertEqual(Detector("up").evaluate("ci", BASELINE + CALM[:-1] + [0.0]).tier, "none")
        self.assertEqual(Detector("down").evaluate("ci", BASELINE + CALM[:-1] + [0.0]).tier, "3sigma")
        self.assertEqual(Detector("both").evaluate("ci", BASELINE + CALM[:-1] + [0.0]).tier, "3sigma")

    def test_flat_baseline_treats_any_rise_as_a_breach(self):
        self.assertEqual(Detector("up").evaluate("ci", [0.0] * 10 + [0.0] * 7 + [0.2]).tier, "3sigma")

    def test_short_series_reports_instead_of_guessing(self):
        verdict = Detector("up").evaluate("ci", BASELINE[:5])
        self.assertEqual(verdict.tier, "none")
        self.assertIn("needs at least", verdict.note)


class Monitor(unittest.TestCase):
    def test_tier_maps_to_configured_action(self):
        series = BASELINE + CALM[:-1] + [0.40]
        monitor = {
            "name": "ci",
            "source": {"type": "command", "run": [sys.executable, "-c", f"print({json.dumps(series)!r})"]},
            "direction": "up",
            "tiers": {"3sigma": {"action": "propose", "tools": "Read,Bash(gh run view *)", "runbooks": ["rollback-deploy"]}},
        }
        result = run_monitor(monitor)
        self.assertEqual((result["tier"], result["action"], result["runbooks"]), ("3sigma", "propose", ["rollback-deploy"]))
        self.assertEqual(result["latest"], 0.40)
        self.assertEqual((result["allowedTools"], result["tools"]), ("Read,Bash(gh run view *)", "Read,Bash"))


class CiFailureSource(unittest.TestCase):
    def test_only_pushes_to_the_default_branch_count(self):
        runs = [{"conclusion": "failure", "createdAt": "2026-10-01T00:00:00Z"}, {"conclusion": "success", "createdAt": "2026-10-01T01:00:00Z"}]
        with mock.patch("opensdlc.monitor.subprocess.run", return_value=mock.Mock(stdout=json.dumps(runs))) as run:
            series = GithubCiFailureRate({"type": "github-ci-failure-rate", "workflow": "CI"}).series()
        args = run.call_args.args[0]
        self.assertEqual((args[args.index("--branch") + 1], args[args.index("--event") + 1]), ("main", "push"))
        self.assertEqual(series, [0.5])


if __name__ == "__main__":
    unittest.main()
