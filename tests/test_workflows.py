# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import subprocess
import unittest

from support import REPO, TEMPLATE

from opensdlc.toolset import toolset

WORKFLOWS = TEMPLATE / ".github" / "workflows"
ACTIONS = TEMPLATE / ".github" / "actions"
AGENT_STEP = (ACTIONS / "opensdlc-agent" / "action.yml").read_text()
JOB = re.compile(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", re.M)
WRITE = re.compile(r"^\s+[\w-]+: write$", re.M)
AGENT = "uses: ./.github/actions/opensdlc-agent"
INTERACTIVE = {"opensdlc-claude.yml"}
ANSWERABLE = {"issues", "issue_comment", "pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment", "workflow_dispatch", "repository_dispatch", "schedule", "workflow_run"}
TRIGGERS = re.compile(r"^on:\n((?:  .*\n)+)", re.M)
SESSION = re.compile(r"^    - if: inputs\.prompt (==|!=) ''\n      uses: (anthropics/claude-code-action(?:/base-action)?)@(\w{40}) # (v[\d.]+)\n((?:      .*\n)+)", re.M)
ALLOWED = re.compile(r'^\s+allowed-tools: "?([^"\n]*)"?$', re.M)
OFFERED = re.compile(r'^\s+tools: "?([^"\n]*)"?$', re.M)
CREDENTIALS = {
    "anthropic-api-key": "secrets.ANTHROPIC_API_KEY",
    "claude-code-oauth-token": "secrets.CLAUDE_CODE_OAUTH_TOKEN",
}
CREDENTIAL_CHECK = re.compile(r"- name: Check the session has exactly one credential\n.*?\n      run: \|\n((?:        [^\n]*\n)+)", re.S)
MATRIX = re.compile(r"^\$\{\{ matrix\.(\w*)AllowedTools \}\}$|^\$\{\{ matrix\.allowedTools \}\}$")
INVOCATION = re.compile(r"^\s*(?:run: )?python3? (?P<flags>(?:-\w+ )*)-m opensdlc", re.M)


def split(path):
    head, body = path.read_text().split("\njobs:\n", 1)
    return head, dict(JOB.findall(body + "\n"))


def triggers(head):
    return set(re.findall(r"^  (\w+):", TRIGGERS.search(head).group(1), re.M))


def sessions():
    return {when: (action, sha, version, inputs) for when, action, sha, version, inputs in SESSION.findall(AGENT_STEP)}


def agent_jobs():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        head, jobs = split(path)
        for name, body in jobs.items():
            if AGENT in body:
                yield f"{path.name}:{name}", path.name, head, body


class AgentJobs(unittest.TestCase):
    def test_these_are_the_agent_jobs(self):
        self.assertEqual({where for where, *_ in agent_jobs()}, {
            "opensdlc-advance.yml:agent", "opensdlc-advance.yml:gate", "opensdlc-ci-triage.yml:agent", "opensdlc-claude.yml:claude",
            "opensdlc-intake.yml:agent", "opensdlc-monitor.yml:agent", "opensdlc-review.yml:reviewer",
        })

    def test_every_agent_runs_in_the_sandbox(self):
        for where, _, _, body in agent_jobs():
            self.assertIn("uses: ./.github/actions/opensdlc-sandbox", body, where)
        self.assertIn("settings: .opensdlc/ci-settings.json", AGENT_STEP)

    def test_a_cd_cannot_move_the_path_rules_agents_are_held_to(self):
        for path in (TEMPLATE / ".opensdlc" / "ci-settings.json", REPO / "docs" / "managed-settings.example.json"):
            self.assertEqual(json.loads(path.read_text())["env"]["CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"], "1", path.name)

    def test_headless_agents_hold_no_write_permission_or_credentials(self):
        for where, workflow, head, body in agent_jobs():
            if workflow in INTERACTIVE:
                continue
            self.assertIsNone(WRITE.search(head), where)
            self.assertIsNone(WRITE.search(body), where)
            self.assertIn("persist-credentials: false", body, where)
            self.assertNotIn("github-token", body, where)
        self.assertNotIn("github_token", AGENT_STEP)

    def test_every_headless_agent_is_offered_only_the_tools_its_permissions_name(self):
        for where, workflow, _, body in agent_jobs():
            if workflow in INTERACTIVE:
                continue
            allowed, offered = ALLOWED.search(body), OFFERED.search(body)
            self.assertIsNotNone(allowed, where)
            self.assertIsNotNone(offered, where)
            matrix = MATRIX.match(allowed.group(1))
            if matrix:
                self.assertEqual(offered.group(1), "${{ matrix.%s }}" % (f"{matrix.group(1)}Tools" if matrix.group(1) else "tools"), where)
            else:
                self.assertEqual(offered.group(1), toolset(allowed.group(1)), where)

    def test_every_stage_session_runs_on_the_model_its_stage_names(self):
        body = split(WORKFLOWS / "opensdlc-advance.yml")[1]
        self.assertIn("model: ${{ matrix.model }}", body["agent"])
        self.assertIn("model: ${{ matrix.gateModel }}", body["gate"])
        self.assertIn("${{ inputs.model && format('--model {0}', inputs.model) || '' }}", AGENT_STEP)

    def test_a_session_with_a_prompt_always_names_its_tools(self):
        self.assertIn("""--allowedTools "${{ inputs.allowed-tools }}" --tools "${{ inputs.tools }}"\n""", sessions()["!="][-1])
        for where, _, _, body in agent_jobs():
            self.assertEqual("prompt: " in body, where.split(":")[0] not in INTERACTIVE, where)

    def test_a_sandboxed_command_still_needs_a_rule_that_names_it(self):
        self.assertIs(json.loads((TEMPLATE / ".opensdlc" / "ci-settings.json").read_text())["sandbox"]["autoAllowBashIfSandboxed"], False)

    def test_a_private_plugin_repository_is_read_with_its_own_token_and_never_kept(self):
        action = (ACTIONS / "opensdlc-plugin" / "action.yml").read_text()
        self.assertIn("token: ${{ inputs.token || github.token }}", action)
        self.assertIn("persist-credentials: false", action)
        steps = [match for workflow in WORKFLOWS.glob("*.yml")
                 for match in re.finditer(r"uses: \./\.github/actions/opensdlc-plugin\n(.*)\n(.*)\n", workflow.read_text())]
        self.assertTrue(steps)
        for step in steps:
            self.assertEqual((step.group(1).strip(), step.group(2).strip()), ("with:", "token: ${{ secrets.OPENSDLC_PLUGIN_TOKEN }}"))

    def test_pipeline_sessions_leave_out_the_skills_claude_code_bundles(self):
        self.assertIs(json.loads((TEMPLATE / ".opensdlc" / "ci-settings.json").read_text())["disableBundledSkills"], True)

    def test_nothing_from_the_workspace_runs_after_the_agent(self):
        for where, workflow, _, body in agent_jobs():
            after = body.split(AGENT, 1)[1]
            self.assertNotIn("uses: ./", after, where)
            self.assertNotIn("python -m opensdlc", after, where)
            if "opensdlc.patch" in after:
                self.assertIn("GIT_DIR: ${{ runner.temp }}/pristine.git", after, where)

    def test_agent_patches_are_checked_before_a_pull_request_opens(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            _, jobs = split(path)
            if not any(AGENT in body and "opensdlc.patch" in body for body in jobs.values()):
                continue
            for name, body in jobs.items():
                if "create-pull-request" in body:
                    self.assertIn("uses: ./.github/actions/opensdlc-apply", body, f"{path.name}:{name}")

    def test_pipeline_commits_are_authored_by_the_actions_bot(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in split(path)[1].items():
                if "create-pull-request" in body:
                    self.assertIn("author: github-actions[bot] <", body, f"{path.name}:{name}")


class OneAgentStep(unittest.TestCase):
    def check(self, **credentials):
        env = {"PATH": os.environ["PATH"], "API_KEY": "", "OAUTH_TOKEN": "", **credentials}
        script = "".join(line[8:] for line in CREDENTIAL_CHECK.search(AGENT_STEP).group(1).splitlines(keepends=True))
        done = subprocess.run(["bash", "-eo", "pipefail", "-c", script], env=env, capture_output=True, text=True)
        return done.returncode, done.stdout

    def test_only_the_shared_step_names_the_agent_it_runs(self):
        named = [path.name for path in WORKFLOWS.glob("*.yml") if "claude-code-action" in path.read_text()]
        self.assertEqual(named, [])
        self.assertEqual(AGENT_STEP.count("uses: anthropics/claude-code-action"), 2)
        self.assertEqual(len({(sha, version) for _, _, sha, version, _ in SESSION.findall(AGENT_STEP)}), 1)

    def test_a_session_with_a_prompt_runs_on_any_event_and_for_any_actor(self):
        headless, answering = sessions()["!="], sessions()["=="]
        self.assertEqual(headless[0], "anthropics/claude-code-action/base-action")
        self.assertIn("prompt: ${{ inputs.prompt }}\n", headless[-1])
        self.assertEqual(answering[0], "anthropics/claude-code-action")
        self.assertNotIn("prompt:", answering[-1])

    def test_a_session_without_a_prompt_starts_only_on_events_the_agent_can_answer(self):
        for where, workflow, head, body in agent_jobs():
            if "prompt: " not in body:
                self.assertLessEqual(triggers(head), ANSWERABLE, where)

    def test_a_stage_can_be_run_again_from_a_base_commit(self):
        head, jobs = split(WORKFLOWS / "opensdlc-advance.yml")
        self.assertEqual(triggers(head), {"push", "workflow_dispatch"})
        self.assertRegex(head, r"  workflow_dispatch:\n    inputs:\n      base:\n(?:        .*\n)*        required: true\n")
        self.assertIn("BEFORE: ${{ inputs.base || github.event.before }}", jobs["due"])
        self.assertIn("if: github.event_name == 'push' && ", jobs["link"])

    def test_every_session_is_handed_every_credential_the_step_accepts(self):
        for where, _, _, body in agent_jobs():
            for name, source in CREDENTIALS.items():
                self.assertEqual(body.count(f"{name}: ${{{{ {source} }}}}"), body.count(AGENT), f"{where}: {name}")
        for name in CREDENTIALS:
            self.assertIn(f"{name.replace('-', '_')}: ${{{{ inputs.{name} }}}}", AGENT_STEP)

    def test_one_credential_runs(self):
        for one in ({"API_KEY": "k"}, {"OAUTH_TOKEN": "t"}):
            self.assertEqual(self.check(**one), (0, ""), one)

    def test_no_credential_stops_the_job(self):
        code, said = self.check()
        self.assertEqual(code, 1)
        self.assertIn("::error::The agent has no credential.", said)

    def test_both_credentials_stop_the_job(self):
        code, said = self.check(API_KEY="k", OAUTH_TOKEN="t")
        self.assertEqual(code, 1)
        self.assertIn("are both set. Keep one.", said)

    def test_the_eval_suite_takes_either_credential(self):
        text = (WORKFLOWS / "opensdlc-evals.yml").read_text()
        for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertIn(f"{name}: ${{{{ secrets.{name} }}}}", text)


    def test_dependabot_watches_every_shared_step_for_new_action_versions(self):
        steps = sorted(path.parent.name for path in ACTIONS.glob("*/action.yml"))
        for path, prefix in ((REPO / ".github" / "dependabot.yml", "/plugin/template"), (TEMPLATE / ".github" / "dependabot.yml", "")):
            watched = re.findall(rf"^      - {prefix}/\.github/actions/([\w-]+)$", path.read_text(), re.M)
            self.assertEqual(watched, steps, path)


class PullRequestIdentity(unittest.TestCase):
    def test_every_pull_request_opens_as_the_app_or_the_stored_token(self):
        opened = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in split(path)[1].items():
                if "create-pull-request" not in body:
                    continue
                opened += 1
                where = f"{path.name}:{name}"
                self.assertIn("token: ${{ steps.bot.outputs.token || secrets.OPENSDLC_PR_TOKEN }}", body, where)
                mint = body.index("uses: actions/create-github-app-token@")
                self.assertLess(mint, body.index("create-pull-request"), where)
                step = body[body.rindex("- id: bot", 0, mint):body.index("create-pull-request")]
                self.assertIn("if: vars.OPENSDLC_APP_CLIENT_ID != ''", step, where)
                self.assertIn("client-id: ${{ vars.OPENSDLC_APP_CLIENT_ID }}", step, where)
                self.assertIn("private-key: ${{ secrets.OPENSDLC_APP_PRIVATE_KEY }}", step, where)
        self.assertEqual(opened, 4)


class PinnedPlugin(unittest.TestCase):
    UNPLUGGED = {"opensdlc-ci-triage.yml:agent"}

    def test_every_agent_that_uses_the_plugin_loads_the_pinned_checkout(self):
        for where, _, _, body in agent_jobs():
            self.assertNotIn("plugin_marketplaces", body, where)
            if where in self.UNPLUGGED:
                continue
            self.assertLess(body.index("uses: ./.github/actions/opensdlc-plugin"), body.index(AGENT), where)
            self.assertEqual(body.count("plugin: ${{ steps.plugin.outputs.dir }}"), body.count(AGENT), where)
        self.assertIn("""${{ inputs.plugin && format('--plugin-dir "{0}"', inputs.plugin) || '' }}""", AGENT_STEP)

    def test_the_eval_suite_runs_the_pinned_plugin(self):
        text = (WORKFLOWS / "opensdlc-evals.yml").read_text()
        self.assertNotIn("plugin marketplace add", text)
        self.assertIn('--plugin-dir "$PLUGIN_DIR"', text)

    def test_every_pull_request_the_pipeline_opens_records_the_plugin_that_wrote_it(self):
        for name in ("opensdlc-advance.yml", "opensdlc-intake.yml", "opensdlc-monitor.yml"):
            text = (WORKFLOWS / name).read_text()
            self.assertIn("OpenSDLC-Plugin: ${{ steps.pin.outputs.pin }}", text, name)
            self.assertIn('echo "Written with OpenSDLC \\`$PIN\\`."', text, name)


class TrustedJudgement(unittest.TestCase):
    def test_the_cli_never_imports_from_the_working_directory(self):
        files = list(WORKFLOWS.glob("*.yml")) + list(ACTIONS.glob("*/action.yml"))
        calls = [(path.name, m["flags"].split()) for path in files for m in INVOCATION.finditer(path.read_text())]
        self.assertGreaterEqual(len(calls), 10)
        for name, flags in calls:
            self.assertIn("-P", flags, name)

    def test_scoped_write_permissions_use_edit_rules(self):
        files = list(WORKFLOWS.glob("*.yml")) + [TEMPLATE / ".opensdlc" / "config.json"]
        for path in files:
            self.assertNotRegex(path.read_text(), r"\bWrite\(", f"{path.name}: Write(path) grants nothing; scope writes with Edit(path)")

    def test_every_applied_patch_is_held_to_a_change(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in split(path)[1].items():
                if "opensdlc-apply" in body:
                    self.assertRegex(body, r"\n\s+change: \S+", f"{path.name}:{name}")

    def test_checks_and_approvals_judge_with_the_base_branch_rules(self):
        for name in ("opensdlc-checks.yml", "opensdlc-approvals.yml"):
            text = (WORKFLOWS / name).read_text()
            self.assertIn("pull_request_target", text, name)
            for job, body in split(WORKFLOWS / name)[1].items():
                self.assertIn('git checkout "$BASE" -- .opensdlc', body, f"{name}:{job}")
                self.assertIn("persist-credentials: false", body, f"{name}:{job}")


if __name__ == "__main__":
    unittest.main()
