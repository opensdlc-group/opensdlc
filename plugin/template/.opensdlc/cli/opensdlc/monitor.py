# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .toolset import toolset

TIERS = ("none", "1sigma", "2sigma", "3sigma")
TAIL = 8
MIN_BASELINE = 5


class Source(ABC):
    def __init__(self, spec: dict):
        self.spec = spec

    @abstractmethod
    def series(self) -> list[float]: ...


class CommandSource(Source):
    def series(self) -> list[float]:
        out = subprocess.run(self.spec["run"], capture_output=True, text=True, check=True, timeout=120).stdout
        return [float(v) for v in json.loads(out)]


class PrometheusSource(Source):
    def series(self) -> list[float]:
        end = time.time()
        query = urllib.parse.urlencode({
            "query": self.spec["query"],
            "start": end - self.spec.get("rangeSeconds", 30 * 86400),
            "end": end,
            "step": self.spec.get("step", "1d"),
        })
        with urllib.request.urlopen(f"{self.spec['url'].rstrip('/')}/api/v1/query_range?{query}", timeout=30) as response:
            result = json.load(response)["data"]["result"]
        return [float(v) for _, v in result[0]["values"]] if result else []


class GithubCiFailureRate(Source):
    def series(self) -> list[float]:
        cmd = ["gh", "run", "list", "--limit", str(self.spec.get("limit", 1000)), "--json", "conclusion,createdAt",
               "--branch", self.spec.get("branch", "main"), "--event", self.spec.get("event", "push")]
        if self.spec.get("workflow"):
            cmd += ["--workflow", self.spec["workflow"]]
        runs = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120).stdout)
        days: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for run in runs:
            if run["conclusion"] in ("success", "failure"):
                day = days[run["createdAt"][:10]]
                day[0] += run["conclusion"] == "failure"
                day[1] += 1
        return [failed / total for _, (failed, total) in sorted(days.items())]


SOURCES: dict[str, type[Source]] = {
    "command": CommandSource,
    "prometheus": PrometheusSource,
    "github-ci-failure-rate": GithubCiFailureRate,
}


@dataclass
class Verdict:
    monitor: str
    tier: str = "none"
    rules: list[str] = field(default_factory=list)
    mean: float | None = None
    stdev: float | None = None
    series: list[float] = field(default_factory=list)
    note: str = ""


class Detector:
    def __init__(self, direction: str = "both", window: int = 30):
        self.direction = direction
        self.window = window

    def z_scores(self, tail: list[float], mean: float, stdev: float) -> list[float]:
        scores = []
        for value in tail:
            delta = value - mean
            z = delta / stdev if stdev else (0.0 if delta == 0 else float("inf") if delta > 0 else float("-inf"))
            scores.append(z if self.direction != "down" else -z)
        return scores

    def sides(self) -> tuple[int, ...]:
        return (1,) if self.direction in ("up", "down") else (1, -1)

    def evaluate(self, name: str, series: list[float]) -> Verdict:
        verdict = Verdict(monitor=name, series=series)
        baseline = series[:-TAIL][-self.window:]
        if len(baseline) < MIN_BASELINE:
            verdict.note = f"needs at least {MIN_BASELINE + TAIL} points, got {len(series)}"
            return verdict
        verdict.mean = statistics.fmean(baseline)
        verdict.stdev = statistics.pstdev(baseline)
        z = self.z_scores(series[-TAIL:], verdict.mean, verdict.stdev)
        fired = {}
        for side in self.sides():
            s = [v * side for v in z]
            if s[-1] > 3:
                fired["beyond-3sigma"] = "3sigma"
            if sum(v > 2 for v in s[-3:]) >= 2:
                fired["2-of-3-beyond-2sigma"] = "2sigma"
            if sum(v > 1 for v in s[-5:]) >= 4:
                fired["4-of-5-beyond-1sigma"] = "1sigma"
            if all(v > 0 for v in s):
                fired["8-in-a-row-one-side"] = "2sigma"
        verdict.rules = sorted(fired)
        verdict.tier = max(fired.values(), key=TIERS.index, default="none")
        return verdict


def run_monitor(monitor: dict) -> dict:
    series = SOURCES[monitor["source"]["type"]](monitor["source"]).series()
    detector = Detector(direction=monitor.get("direction", "both"), window=monitor.get("window", 30))
    verdict = detector.evaluate(monitor["name"], series)
    tier = monitor.get("tiers", {}).get(verdict.tier, {})
    allowed = tier.get("tools", "Read,Glob,Grep")
    return {
        "monitor": verdict.monitor,
        "detectedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metric": monitor.get("metric", verdict.monitor),
        "tier": verdict.tier,
        "action": tier.get("action", "none"),
        "rules": verdict.rules,
        "mean": verdict.mean,
        "stdev": verdict.stdev,
        "latest": series[-1] if series else None,
        "series": series,
        "allowedTools": allowed,
        "tools": toolset(allowed),
        "runbooks": tier.get("runbooks", []),
        "note": verdict.note,
    }
