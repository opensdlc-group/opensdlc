# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .context import LOCK_DIR, STATE_DIR, Context
from .paths import matches
from .shell import write_targets

SECRET_PATTERNS = {
    "AWS access key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    "Anthropic API key": r"\bsk-ant-[A-Za-z0-9_\-]{20,}",
    "OpenAI-style API key": r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b",
    "Slack token": r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
    "Stripe live key": r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_\-]{35}\b",
}
ENV_FILES = [".env", "**/.env", ".env.*", "**/.env.*"]
ENV_TEMPLATES = ["**/.env.example", ".env.example", "**/.env.sample", ".env.sample"]
AUTONOMY = {"free": 0, "ask": 1, "approval": 2}


@dataclass(frozen=True)
class Decision:
    verdict: str
    reason: str

    @classmethod
    def deny(cls, reason: str) -> "Decision":
        return cls("deny", reason)

    @classmethod
    def ask(cls, reason: str) -> "Decision":
        return cls("ask", reason)


class PathRule(ABC):
    @abstractmethod
    def violation(self, ctx: Context, path: str) -> str | None: ...


class ProtectedPaths(PathRule):
    def violation(self, ctx, path):
        for rule in ctx.config.get("protected", []):
            if matches(path, rule["paths"]):
                return f"{path} is protected. {rule.get('reason', '')}".strip()
        return None


class EnvFiles(PathRule):
    def violation(self, ctx, path):
        if matches(path, ENV_FILES) and not matches(path, ENV_TEMPLATES):
            return f"{path} holds environment secrets; edit .env.example and let a human set real values."
        return None


class FrozenTests(PathRule):
    def violation(self, ctx, path):
        if ctx.test_lock_active() and matches(path, ctx.config.get("tests", [])):
            return f"Tests are frozen for this fix. {path} defines the bug; change the code, not the test."
        return None


def touches(path: str, folder: str) -> bool:
    path = path.rstrip("/")
    return path in ("", ".") or path == folder or path.startswith(folder + "/") or folder.startswith(path + "/")


class LoopState(PathRule):
    def violation(self, ctx, path):
        if touches(path, STATE_DIR):
            return "OpenSDLC's session state is written only by its hooks."
        if ctx.test_lock_active() and touches(path, LOCK_DIR):
            return "OpenSDLC locks can only be cleared by ending the session."
        return None


PATH_RULES: list[PathRule] = [LoopState(), ProtectedPaths(), EnvFiles(), FrozenTests()]


class Guard(ABC):
    @abstractmethod
    def check(self, ctx: Context) -> Decision | None: ...


class FileTargets(Guard):
    def check(self, ctx):
        return next((Decision.deny(v) for v in (r.violation(ctx, ctx.target) for r in PATH_RULES) if v), None)


class ShellWrites(Guard):
    def check(self, ctx):
        for target in write_targets(ctx.command) or []:
            path = ctx.relative(target)
            for rule in PATH_RULES:
                found = rule.violation(ctx, path)
                if found:
                    return Decision.deny(f"Shell write blocked: {found}")
        return None


class SecretContent(Guard):
    def check(self, ctx):
        text = ctx.written_text
        for label, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, text):
                return Decision.deny(f"The change to {ctx.target} contains what looks like a {label}. Reference it from the environment or a secret manager instead.")
        return None


class EnvironmentGate(Guard):
    def check(self, ctx):
        matched = [env for env in ctx.config.get("environments", []) if self._targets(ctx, env)]
        if not matched:
            return None
        env = max(matched, key=lambda e: AUTONOMY[e.get("autonomy", "approval")])
        autonomy = env.get("autonomy", "approval")
        route = env.get("route", "")
        if autonomy == "free":
            return None
        if autonomy == "ask":
            return Decision.ask(f"Acting on {env['name']} needs a human to confirm. {route}".strip())
        if os.environ.get(env.get("approvalEnv", "RELEASE_APPROVAL")):
            return None
        return Decision.deny(f"Acting on {env['name']} needs a release authorization. {route}".strip())

    @staticmethod
    def _targets(ctx: Context, env: dict) -> bool:
        if ctx.command:
            return any(re.search(p, ctx.command) for p in env.get("commands", []))
        return any(re.search(p, ctx.tool) for p in env.get("tools", []))


REGISTRY: dict[str, list[Guard]] = {
    "files": [FileTargets(), SecretContent()],
    "bash": [ShellWrites(), EnvironmentGate()],
    "tools": [EnvironmentGate()],
}
