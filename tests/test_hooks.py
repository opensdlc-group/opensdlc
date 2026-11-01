# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import unittest

from support import TEMPLATE, decision, run_hook, temp_project

CONFIG = json.loads((TEMPLATE / ".opensdlc" / "config.json").read_text())


def write(root, path, content="x = 1\n"):
    return {"tool_name": "Write", "tool_input": {"file_path": str(root / path), "content": content}}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def stop(active=False):
    return {"hook_event_name": "Stop", "stop_hook_active": active}


class FileGuards(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)

    def test_ordinary_write_has_no_opinion(self):
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, "src/app.py"))))

    def test_protected_paths_are_denied_with_reason(self):
        result = run_hook(self.root, "files", write(self.root, "db/migrations/0002_add.sql"))
        self.assertEqual(decision(result), "deny")
        self.assertIn("change ticket", result.stdout)

    def test_glob_double_star_matches_root_level_files(self):
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, "src/gen/model.ts"))), "deny")

    def test_secrets_in_new_content_are_denied(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, "src/cfg.py", f"KEY='{key}'"))), "deny")

    def test_secrets_in_edit_and_multiedit_are_denied(self):
        token = "ghp_" + "a" * 36
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(self.root / "a.py"), "old_string": "x", "new_string": token}}
        multi = {"tool_name": "MultiEdit", "tool_input": {"file_path": str(self.root / "a.py"), "edits": [{"old_string": "x", "new_string": token}]}}
        self.assertEqual(decision(run_hook(self.root, "files", edit)), "deny")
        self.assertEqual(decision(run_hook(self.root, "files", multi)), "deny")

    def test_env_files_are_denied_but_examples_are_not(self):
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, ".env"))), "deny")
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, "api/.env.local"))), "deny")
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, ".env.example"))))

    def test_hook_state_cannot_be_written_by_the_agent(self):
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, ".opensdlc/state/s1.json", "{}"))), "deny")

    def test_missing_config_still_guards_secrets(self):
        bare = temp_project()
        self.assertIsNone(decision(run_hook(bare, "files", write(bare, "db/migrations/1.sql"))))
        self.assertEqual(decision(run_hook(bare, "files", write(bare, ".env"))), "deny")


class ShellWrites(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)

    def test_shell_writes_to_guarded_paths_are_denied(self):
        for command in (
            "echo SECRET=1 > .env",
            "cat schema.sql | tee db/migrations/0003.sql",
            "cp new.sql db/migrations/0004.sql",
            "sed -i 's/a/b/' src/gen/client.ts",
            "rm -rf .opensdlc/state",
            "rm -rf .opensdlc",
        ):
            result = run_hook(self.root, "bash", bash(command))
            self.assertEqual(decision(result), "deny", command)
            self.assertIn("Shell write blocked", result.stdout, command)

    def test_ordinary_shell_writes_pass(self):
        for command in ("echo hi > notes.txt", "cp a.py src/b.py", "make test", "rm -f build/out.o"):
            self.assertIsNone(decision(run_hook(self.root, "bash", bash(command))), command)

    def test_frozen_tests_cannot_be_rewritten_through_the_shell(self):
        (self.root / ".opensdlc" / "locks").mkdir()
        (self.root / ".opensdlc" / "locks" / "tests.json").write_text(json.dumps({"session": "s1"}))
        self.assertEqual(decision(run_hook(self.root, "bash", bash("git checkout -- tests/test_a.py"))), "deny")
        self.assertEqual(decision(run_hook(self.root, "bash", bash("echo '' > tests/test_a.py"))), "deny")

    def test_unparseable_commands_are_left_to_the_sandbox(self):
        self.assertIsNone(decision(run_hook(self.root, "bash", bash("echo 'unterminated > .env"))))


class TestFreeze(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)

    def lock(self, session):
        (self.root / ".opensdlc" / "locks").mkdir(exist_ok=True)
        (self.root / ".opensdlc" / "locks" / "tests.json").write_text(json.dumps({"session": session}))

    def test_tests_are_editable_without_a_lock(self):
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, "tests/test_a.py"))))

    def test_writing_the_lock_is_allowed(self):
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, ".opensdlc/locks/tests.json", '{"session": "s1"}'))))

    def test_lock_freezes_tests_for_its_session(self):
        self.lock("s1")
        for path in ("tests/test_a.py", "src/util.test.ts", "pkg/x_test.go", "web/__tests__/a.tsx"):
            self.assertEqual(decision(run_hook(self.root, "files", write(self.root, path))), "deny", path)
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, "src/util.ts"))))

    def test_lock_from_another_session_is_ignored(self):
        self.lock("other")
        self.assertIsNone(decision(run_hook(self.root, "files", write(self.root, "tests/test_a.py"))))

    def test_lock_cannot_be_removed_by_the_agent(self):
        self.lock("s1")
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, ".opensdlc/locks/tests.json", "{}"))), "deny")
        self.assertEqual(decision(run_hook(self.root, "bash", bash("rm .opensdlc/locks/tests.json"))), "deny")

    def test_corrupt_lock_fails_closed(self):
        (self.root / ".opensdlc" / "locks").mkdir()
        (self.root / ".opensdlc" / "locks" / "tests.json").write_text("not json")
        self.assertEqual(decision(run_hook(self.root, "files", write(self.root, "tests/test_a.py"))), "deny")


class EnvironmentTiers(unittest.TestCase):
    def setUp(self):
        self.root = temp_project(CONFIG)

    def test_production_needs_a_release_authorization(self):
        for command in ("make deploy ENV=production", "terraform apply -var-file=prod.tfvars", "npx wrangler deploy --env production", "helm upgrade api ./chart -n prod"):
            self.assertEqual(decision(run_hook(self.root, "bash", bash(command))), "deny", command)

    def test_release_approval_lets_production_through(self):
        result = run_hook(self.root, "bash", bash("make deploy ENV=production"), env={"RELEASE_APPROVAL": "CHG-1042"})
        self.assertIsNone(decision(result))

    def test_staging_asks_and_development_is_free(self):
        self.assertEqual(decision(run_hook(self.root, "bash", bash("make deploy ENV=staging"))), "ask")
        self.assertIsNone(decision(run_hook(self.root, "bash", bash("make deploy ENV=dev"))))

    def test_ordinary_commands_have_no_opinion(self):
        for command in ("make test", "git log --oneline"):
            self.assertIsNone(decision(run_hook(self.root, "bash", bash(command))), command)

    def test_mcp_tools_follow_the_same_tiers(self):
        self.assertEqual(decision(run_hook(self.root, "tools", {"tool_name": "mcp__deployer__deploy_production", "tool_input": {}})), "deny")
        self.assertEqual(decision(run_hook(self.root, "tools", {"tool_name": "mcp__deployer__deploy_staging", "tool_input": {}})), "ask")
        self.assertIsNone(decision(run_hook(self.root, "tools", {"tool_name": "mcp__deployer__status", "tool_input": {}})))

    def test_the_strictest_matching_environment_wins(self):
        result = run_hook(self.root, "bash", bash("make deploy ENV=staging && make deploy ENV=production"))
        self.assertEqual(decision(result), "deny")


class VerifyBeforeDone(unittest.TestCase):
    def setUp(self):
        self.root = temp_project({**CONFIG, "verify": {**CONFIG["verify"], "commands": ["make test", "make lint"]}})

    def edit(self, path="src/app.py"):
        return run_hook(self.root, "edited", {**write(self.root, path), "hook_event_name": "PostToolUse"})

    def passed(self, command):
        return run_hook(self.root, "ran", {**bash(command), "hook_event_name": "PostToolUse"})

    def stop_output(self, active=False):
        out = run_hook(self.root, "stop", stop(active)).stdout.strip()
        return json.loads(out) if out else {}

    def test_a_session_without_code_edits_stops_freely(self):
        self.assertEqual(self.stop_output(), {})

    def test_editing_code_blocks_stop_until_every_verify_command_passes(self):
        self.edit()
        blocked = self.stop_output()
        self.assertEqual(blocked["decision"], "block")
        self.assertIn("`make test` and `make lint`", blocked["reason"])
        self.passed("make test")
        self.assertIn("`make lint`", self.stop_output(True)["reason"])
        self.passed("make lint")
        self.assertEqual(self.stop_output(True), {})

    def test_chained_commands_count_only_when_failure_would_surface(self):
        self.edit()
        self.passed("make test || true")
        self.passed("make lint; echo done")
        self.assertEqual(self.stop_output()["decision"], "block")
        self.passed("make build && make test && make lint")
        self.assertEqual(self.stop_output(), {})

    def test_editing_again_after_verifying_requires_verifying_again(self):
        self.edit()
        self.passed("make test && make lint")
        self.edit("src/other.py")
        self.assertEqual(self.stop_output()["decision"], "block")

    def test_docs_and_artifacts_do_not_need_verification(self):
        for path in ("changes/x/spec.md", "README.md", "knowledge/policies/pii.md"):
            self.edit(path)
        self.assertEqual(self.stop_output(), {})

    def test_blocking_gives_up_after_the_limit_with_a_warning(self):
        self.edit()
        for _ in range(3):
            self.assertEqual(self.stop_output(True)["decision"], "block")
        final = self.stop_output(True)
        self.assertNotIn("decision", final)
        self.assertIn("unverified", final["systemMessage"])

    def test_sessions_are_tracked_separately(self):
        self.edit()
        other = run_hook(self.root, "stop", {**stop(), "session_id": "s2"})
        self.assertEqual(other.stdout.strip(), "")

    def test_no_verify_commands_means_no_enforcement(self):
        root = temp_project({**CONFIG, "verify": {"commands": []}})
        run_hook(root, "edited", {**write(root, "src/a.py"), "hook_event_name": "PostToolUse"})
        self.assertEqual(run_hook(root, "stop", stop()).stdout.strip(), "")


class Formatter(unittest.TestCase):
    def test_formatter_runs_on_matching_files(self):
        root = temp_project({"format": [{"paths": ["**/*.txt"], "run": ["sh", "-c", "echo formatted > \"$0\""]}]})
        (root / "a.txt").write_text("raw")
        result = run_hook(root, "edited", write(root, "a.txt"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual((root / "a.txt").read_text().strip(), "formatted")

    def test_formatter_failure_is_shown_to_claude(self):
        root = temp_project({"format": [{"paths": ["**/*.txt"], "run": ["sh", "-c", "echo bad syntax >&2; exit 3"]}]})
        result = run_hook(root, "edited", write(root, "a.txt"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("bad syntax", result.stderr)

    def test_non_matching_files_are_left_alone(self):
        root = temp_project({"format": [{"paths": ["**/*.txt"], "run": ["false"]}]})
        self.assertEqual(run_hook(root, "edited", write(root, "a.py")).returncode, 0)


if __name__ == "__main__":
    unittest.main()
