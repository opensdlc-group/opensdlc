# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from .metrics.dataset import markers

Shell = Callable[[list[str]], str]
TAG = re.compile(r"^\*\*\[(?P<axis>standards|spec|security) · (?P<severity>important|nit)(?: · (?P<key>[\w-]+))?\]\*\*", re.I)
AXES = ("standards", "spec", "security")
SEVERITIES = ("important", "nit")
KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class ReviewFinding:
    axis: str
    severity: str
    key: str
    file: str
    line: int | None
    summary: str
    policy: str
    repeat: bool
    suggested_rule: str

    @classmethod
    def of(cls, raw: dict) -> "ReviewFinding | None":
        try:
            line = int(raw["line"]) if raw.get("line") is not None else None
            finding = cls(str(raw["axis"]).lower(), str(raw["severity"]).lower(), str(raw["key"]), str(raw["file"]), line,
                          str(raw.get("summary") or ""), str(raw.get("policy") or ""), bool(raw.get("repeat")), str(raw.get("suggestedRule") or ""))
        except (KeyError, TypeError, ValueError):
            return None
        valid = finding.axis in AXES and finding.severity in SEVERITIES and KEY.match(finding.key) and (line is None or line > 0)
        return finding if valid else None

    @property
    def tag(self) -> str:
        return f"**[{self.axis} · {self.severity} · {self.key}]**"

    def comment(self) -> str:
        parts = [f"{self.tag} {self.summary}"]
        if self.policy:
            parts.append(f"Policy: `{self.policy}`")
        if self.repeat and self.suggested_rule:
            parts.append(f"Repeat finding. Suggested `AGENTS.md` rule: {self.suggested_rule}")
        return "\n\n".join(parts)

    def marker(self) -> dict:
        return {"axis": self.axis, "severity": self.severity, "key": self.key, "policy": self.policy, "repeat": self.repeat, "suggestedRule": self.suggested_rule}


@dataclass(frozen=True)
class Tally:
    findings: tuple[ReviewFinding, ...]
    agents_md_outdated: bool

    @classmethod
    def of(cls, raw: object) -> "Tally":
        raw = raw if isinstance(raw, dict) else {}
        found = [ReviewFinding.of(f) for f in raw.get("findings") or [] if isinstance(f, dict)]
        return cls(tuple(f for f in found if f), raw.get("agentsMdOutdated") is True)

    def count(self, severity: str) -> int:
        return sum(f.severity == severity for f in self.findings)

    def selected(self, nit_cap: int) -> list[ReviewFinding]:
        nits = [f for f in self.findings if f.severity == "nit"][:nit_cap]
        return [f for f in self.findings if f.severity == "important"] + nits

    def marker(self) -> dict:
        axes = {axis: sum(f.axis == axis for f in self.findings) for axis in AXES}
        return {"important": self.count("important"), "nit": self.count("nit"), "axes": axes,
                "agentsMdOutdated": self.agents_md_outdated, "findings": [f.marker() for f in self.findings]}

    def markdown(self, unplaced: list[ReviewFinding]) -> str:
        marker = self.marker()
        axes = " / ".join(f"{axis.title()} {n}" for axis, n in marker["axes"].items())
        lines = ["### OpenSDLC review", "", f"Important: {marker['important']} · Nits: {marker['nit']} · {axes}"]
        if self.agents_md_outdated:
            lines += ["", "This change makes `AGENTS.md` outdated."]
        rules = {f.key: f.suggested_rule for f in self.findings if f.repeat and f.suggested_rule}
        if rules:
            lines += ["", "#### Repeated mistakes", "", "Each has been raised before. Adding the rule to `AGENTS.md` stops the next one:", ""]
            lines += [f"- `{key}`: {rule}" for key, rule in rules.items()]
        if unplaced:
            lines += ["", "#### Findings not on a changed line", ""]
            lines += [f"- {f.tag} `{f.file}{f':{f.line}' if f.line else ''}` {f.summary}" for f in unplaced]
        encoded = json.dumps(marker).replace(">", "\\u003e")
        return "\n".join(lines + ["", f"<!-- opensdlc:review {encoded} -->"])


def tallies(prs: list[dict]) -> dict[int, dict]:
    found = {}
    for pr in prs:
        for comment in reversed(pr.get("comments", [])):
            marked = markers(comment.get("body", ""), "review")
            if marked:
                found[pr["number"]] = marked[-1]
                break
    return found


def key_counts(prs: list[dict], exclude: int | None = None) -> Counter:
    counts = Counter()
    for number, tally in tallies(prs).items():
        if number != exclude:
            counts.update({f["key"] for f in tally.get("findings", []) if f.get("key")})
    return counts


@dataclass(frozen=True)
class Rated:
    axis: str
    severity: str
    key: str
    up: int
    down: int


def rated_comments(raw: list[dict], reviewers: frozenset[str]) -> list[Rated]:
    found = []
    for comment in raw:
        login = (comment.get("user") or {}).get("login", "")
        tag = TAG.match(comment.get("body", ""))
        if tag and (not reviewers or login in reviewers):
            reactions = comment.get("reactions") or {}
            found.append(Rated(tag["axis"].lower(), tag["severity"].lower(), tag["key"] or "", reactions.get("+1", 0), reactions.get("-1", 0)))
    return found


def tuning(rated: list[Rated], tallies_: dict[int, dict], nit_cap: int) -> tuple[dict, str]:
    by_axis = defaultdict(lambda: [0, 0])
    disliked = Counter()
    for r in rated:
        by_axis[r.axis][0] += r.up
        by_axis[r.axis][1] += r.down
        if r.down > r.up and r.key:
            disliked[r.key] += 1
    precision = {axis: up / (up + down) for axis, (up, down) in by_axis.items() if up + down}
    nits = [int(t.get("nit", 0)) for t in tallies_.values()]
    nit_mean = sum(nits) / len(nits) if nits else 0.0
    suggestions = [f"Tighten the {axis} axis in REVIEW.md: only {p:.0%} of rated findings were useful." for axis, p in sorted(precision.items()) if p < 0.6]
    if nit_mean > nit_cap * 0.8:
        suggestions.append(f"Nits average {nit_mean:.1f} per PR against a cap of {nit_cap}; lower the cap or move recurring nits into lint.")
    suggestions += [f"Findings keyed `{key}` were voted down {n} times; add it to Do not report or fix the rule behind it." for key, n in disliked.most_common(5) if n >= 2]
    data = {"precision": precision, "ratings": len(rated), "reviews": len(tallies_), "nitMean": nit_mean, "disliked": dict(disliked), "suggestions": suggestions}
    lines = ["## OpenSDLC review tuning", "", f"{len(tallies_)} reviews, {len(rated)} rated findings (👍/👎 on the reviewer's inline comments).", ""]
    lines += [f"- **{axis}**: {p:.0%} useful" for axis, p in sorted(precision.items())] or ["- No findings were rated. Ask reviewers to react 👍 or 👎 to OpenSDLC's inline comments."]
    lines += ["", "### Suggested changes", ""] + ([f"- {s}" for s in suggestions] or ["- None this month."])
    return data, "\n".join(lines)


class GitHubReviews:
    def __init__(self, shell: Shell):
        self.shell = shell

    def prs(self, since: str) -> list[dict]:
        return json.loads(self.shell(["pr", "list", "--state", "all", "--limit", "500", "--search", f"updated:>={since}", "--json", "number,comments"]))

    def inline_comments(self, repo: str, number: int) -> list[dict]:
        pages = json.loads(self.shell(["api", f"repos/{repo}/pulls/{number}/comments", "--paginate", "--slurp"]) or "[]")
        return [comment for page in pages for comment in page]

    def repo(self) -> str:
        return json.loads(self.shell(["repo", "view", "--json", "nameWithOwner"]))["nameWithOwner"]


class PullRequestPublisher:
    def __init__(self, shell: Shell, repo: str, number: int, head: str):
        self.shell = shell
        self.repo = repo
        self.number = number
        self.head = head

    def inline(self, finding: ReviewFinding) -> bool:
        try:
            self.shell(["api", f"repos/{self.repo}/pulls/{self.number}/comments", "-f", f"body={finding.comment()}", "-f", f"path={finding.file}",
                        "-F", f"line={finding.line}", "-f", "side=RIGHT", "-f", f"commit_id={self.head}"])
        except RuntimeError:
            return False
        return True

    def upsert(self, body: str) -> None:
        pages = json.loads(self.shell(["api", f"repos/{self.repo}/issues/{self.number}/comments", "--paginate", "--slurp"]) or "[]")
        mine = [c for page in pages for c in page if (c.get("user") or {}).get("type") == "Bot" and markers(c.get("body", ""), "review")]
        if mine:
            self.shell(["api", "-X", "PATCH", f"repos/{self.repo}/issues/comments/{mine[-1]['id']}", "-f", f"body={body}"])
        else:
            self.shell(["api", f"repos/{self.repo}/issues/{self.number}/comments", "-f", f"body={body}"])


def publish(tally: Tally, target: PullRequestPublisher, nit_cap: int) -> str:
    unplaced = [f for f in tally.selected(nit_cap) if f.line is None or not target.inline(f)]
    markdown = tally.markdown(unplaced)
    target.upsert(markdown)
    return markdown
