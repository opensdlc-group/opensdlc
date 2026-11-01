# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
from dataclasses import dataclass
from typing import Any

from .adapters import Adapter, AdapterError
from .model import Check


@dataclass(frozen=True)
class CheckResult:
    key: str
    status: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def unknown_like(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return value + 999_999
    if isinstance(value, str) and value.isdigit():
        return str(int(value) + 999_999)
    return f"{value}-unknown"


def resolve(value: Any, saved: dict[str, Any]) -> Any:
    if isinstance(value, dict) and set(value) == {"unknown"}:
        return unknown_like(resolve(value["unknown"], saved))
    if isinstance(value, str) and value.startswith("$") and "." in value:
        name, field = value[1:].split(".", 1)
        if not isinstance(saved.get(name), dict) or field not in saved[name]:
            raise AdapterError(f"{value} is unavailable because an earlier step returned {brief(saved.get(name))}")
        return saved[name][field]
    if isinstance(value, dict):
        return {k: resolve(v, saved) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, saved) for v in value]
    return value


def matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(matches(e, a) for e, a in zip(expected, actual))
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    return expected == actual


def brief(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= 160 else text[:157] + "..."


class CheckRunner:
    def __init__(self, adapter: Adapter, target: str):
        self.adapter = adapter
        self.target = target

    def run(self, check: Check) -> CheckResult:
        if not check.applies_to(self.target):
            return CheckResult(check.key, "skip", f"not applicable to {self.target}")
        try:
            session = self.adapter.session()
        except AdapterError as error:
            return CheckResult(check.key, "fail", f"could not start: {error}")
        try:
            return CheckResult(check.key, *self.steps(check, session))
        except AdapterError as error:
            return CheckResult(check.key, "fail", str(error))
        finally:
            session.close()

    def steps(self, check: Check, session) -> tuple[str, str]:
        saved: dict[str, Any] = {}
        for number, step in enumerate(check.steps, 1):
            args = resolve(step.get("args", {}), saved)
            if step["op"] == "distinct":
                values = [str(v) for v in args["values"]]
                if len(set(values)) != len(values):
                    return "fail", f"step {number}: ids repeat: {values}"
                continue
            actual = session.call(step["op"], args)
            expected = resolve(step.get("expect"), saved)
            if expected is None and isinstance(actual, dict) and "error" in actual:
                return "fail", f"step {number} {step['op']} {brief(args)}: unexpected {actual['error']} error"
            if expected is not None and not matches(expected, actual):
                return "fail", f"step {number} {step['op']} {brief(args)}: expected {brief(expected)}, got {brief(actual)}"
            if "as" in step:
                saved[step["as"]] = actual
        return "pass", ""


def run_checks(adapter: Adapter, target: str, checks: list[Check]) -> list[CheckResult]:
    runner = CheckRunner(adapter, target)
    try:
        try:
            adapter.prepare()
        except AdapterError as error:
            return [CheckResult(c.key, "fail" if c.applies_to(target) else "skip", f"could not prepare: {error}") for c in checks]
        return [runner.run(c) for c in checks]
    finally:
        adapter.stop()
