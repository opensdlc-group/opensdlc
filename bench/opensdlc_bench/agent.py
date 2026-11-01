# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from opensdlc.toolset import toolset

from .paths import PLUGIN

REFUSED = re.compile(r"^(API Error|You've hit your .*limit)")
KEPT_CLAUDE_VARIABLES = frozenset({"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                                   "CLAUDE_CODE_USE_FOUNDRY"})
API_KEY_CACHE = {"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"}


@dataclass(frozen=True)
class AgentRun:
    prompt: str
    ok: bool
    cost: float = 0.0
    turns: int = 0
    seconds: float = 0.0
    result: str = ""
    error: str = ""
    session: str = ""
    models: dict[str, float] = field(default_factory=dict)


class AgentUnavailable(Exception):
    pass


class Agent(ABC):
    @abstractmethod
    def run(self, prompt: str, cwd: Path, tools: str, max_turns: int, model: str = "") -> AgentRun: ...


class ClaudeCode(Agent):
    def __init__(self, model: str | None = None, timeout: int = 1800, plugin: Path = PLUGIN):
        self.model = model
        self.timeout = timeout
        self.plugin = plugin

    def command(self, prompt: str, cwd: Path, tools: str, max_turns: int, session: str, model: str = "") -> list[str]:
        command = ["claude", "-p", prompt, "--plugin-dir", str(self.plugin), "--settings", str(cwd / ".opensdlc" / "ci-settings.json"),
                   "--setting-sources", "project,local", "--allowedTools", tools, "--tools", toolset(tools), "--max-turns", str(max_turns),
                   "--output-format", "json", "--session-id", session]
        chosen = model or self.model
        return command + (["--model", chosen] if chosen else [])

    @staticmethod
    def environment() -> dict[str, str]:
        kept = {name: value for name, value in os.environ.items() if not name.startswith("CLAUDE") or name in KEPT_CLAUDE_VARIABLES}
        return {**kept, **API_KEY_CACHE}

    def run(self, prompt: str, cwd: Path, tools: str, max_turns: int, model: str = "") -> AgentRun:
        session, started = str(uuid.uuid4()), time.monotonic()
        try:
            result = subprocess.run(self.command(prompt, cwd, tools, max_turns, session, model), cwd=cwd, env=self.environment(), capture_output=True,
                                    text=True, timeout=self.timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return AgentRun(prompt, False, seconds=time.monotonic() - started, error=f"timed out after {self.timeout}s", session=session)
        return self.parse(prompt, result, time.monotonic() - started, session)

    @staticmethod
    def parse(prompt: str, result: subprocess.CompletedProcess, seconds: float, session: str) -> AgentRun:
        try:
            data = json.loads(result.stdout)
        except ValueError:
            return AgentRun(prompt, False, seconds=seconds, error=(result.stderr or result.stdout)[-1000:], session=session)
        result = str(data.get("result", "")).strip()
        if data.get("is_error") and REFUSED.match(result):
            raise AgentUnavailable(result)
        failed = data.get("is_error") or data.get("subtype") != "success"
        error = (result[:300] if data.get("is_error") and result else str(data.get("subtype", ""))) if failed else ""
        models = {name: float(usage.get("costUSD") or 0) for name, usage in (data.get("modelUsage") or {}).items()}
        return AgentRun(prompt, not failed, float(data.get("total_cost_usd") or 0), int(data.get("num_turns") or 0), seconds,
                        result[-2000:], error, session, models)

    def transcript(self, session: str) -> Path | None:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        return next((config / "projects").glob(f"*/{session}.jsonl"), None)
