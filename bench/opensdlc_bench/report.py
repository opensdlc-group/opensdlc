# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import inf, sqrt
from pathlib import Path
from statistics import mean, variance

Z95 = 1.96


def count(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")


METRICS = {
    "acceptance": ("Acceptance checks passing at the end", "up", lambda v: f"{v:.0%}"),
    "regressions": ("Checks that passed, then broke", "down", count),
    "ticketsCompleted": ("Tickets through every stage", "up", count),
    "reviewsCompleted": ("Tickets the reviewer scored", "up", count),
    "cost": ("Cost", "down", lambda v: f"${v:.2f}"),
    "minutes": ("Wall time", "down", lambda v: f"{v:.1f} min"),
    "agentRuns": ("Agent sessions", "down", count),
    "turns": ("Agent turns", "down", count),
    "missedEscalations": ("Tickets that needed a person but did not escalate", "down", count),
    "unneededEscalations": ("Escalations on tickets that did not need one", "down", count),
    "patchRefusals": ("Patches refused by patch-check", "down", count),
    "checkRepairs": ("Artifacts that failed opensdlc check first time", "down", count),
    "ciRed": ("Tickets left with red CI", "down", count),
    "planMatchFailures": ("Tickets whose code left the plan", "down", count),
    "existingTestsChanged": ("Tickets that edited existing tests", "down", count),
    "importantFound": ("Important review findings", "down", count),
    "importantLeft": ("Important findings left after fixes", "down", count),
    "repeats": ("Repeated review findings", "down", count),
    "policyConcerns": ("Specs whose Concerns cite a policy", "", count),
    "policyFindings": ("Review findings that cite a policy", "", count),
}
MARK = {"pass": "✅", "fail": "❌", "skip": "–"}


def last_code(stages: list[dict]) -> dict | None:
    return next((s for s in reversed(stages) if s["stage"] in ("build", "fix") and "ci" in s["notes"]), None)


def reviews(stages: list[dict]) -> list[dict]:
    return [s for s in stages if s["stage"] == "review" and "important" in s["notes"]]


def regressions(tickets: list[dict]) -> int:
    history = defaultdict(list)
    for ticket in tickets:
        for check in ticket["acceptance"]:
            history[check["key"]].append(check["status"])
    return sum(any(a == "pass" and "fail" in states[i + 1:] for i, a in enumerate(states)) for states in history.values())


def escalations(stage: dict) -> int:
    return (stage["status"] == "escalated") + stage["notes"].get("escalations", 0)


def escalated_early(ticket: dict) -> bool:
    return any(escalations(s) for s in ticket["stages"] if s["stage"] in ("intake", "spec", "plan"))


def raised(ticket: dict) -> str:
    stage = next((s for s in ticket["stages"] if escalations(s)), None)
    if stage is None:
        return "not escalated"
    who = stage["notes"].get("raisedBy")
    return f"{stage['stage']}, by the {who}" if who else stage["stage"]


def raisers(runs: list[dict]) -> list[str]:
    tally = defaultdict(Counter)
    for run in runs:
        for ticket in run["tickets"]:
            tally[(ticket["ticket"], ticket.get("must_escalate", False))][raised(ticket)] += 1
    lines = []
    for (name, must), outcomes in tally.items():
        if must or set(outcomes) != {"not escalated"}:
            label = f"{name} (must escalate)" if must else name
            lines.append(f"- {label}: " + ", ".join(f"{what} {n}/{outcomes.total()}" for what, n in outcomes.most_common()))
    return lines


def agent_runs(run: dict) -> list[dict]:
    return [r for t in run["tickets"] for s in t["stages"] for r in s["runs"]]


def models(runs: list[dict]) -> dict[str, float]:
    spent = defaultdict(float)
    for r in (r for run in runs for r in agent_runs(run)):
        for name, cost in r.get("models", {}).items():
            spent[name] += cost
    return dict(sorted(spent.items(), key=lambda item: -item[1]))


def main_model(runs: list[dict]) -> str:
    return next(iter(models(runs)), runs[0]["model"])


def model_label(runs: list[dict]) -> str:
    used = ", ".join(f"{name} ${cost:.2f}" for name, cost in models(runs).items())
    return f"model {runs[0]['model']}" + (f" ({used})" if used else "")


def summary(run: dict) -> dict:
    tickets = run["tickets"]
    final = [c for c in (tickets[-1]["acceptance"] if tickets else []) if c["status"] != "skip"]
    stages = [s for t in tickets for s in t["stages"]]
    runs = agent_runs(run)
    code = [last_code(t["stages"]) for t in tickets]
    first_reviews = [reviews(t["stages"])[0] for t in tickets if reviews(t["stages"])]
    last_reviews = [reviews(t["stages"])[-1] for t in tickets if reviews(t["stages"])]
    return {
        "acceptance": sum(c["status"] == "pass" for c in final) / len(final) if final else 0.0,
        "regressions": regressions(tickets),
        "ticketsCompleted": sum(bool(reviews(t["stages"])) and all(s["status"] != "blocked" for s in t["stages"]) for t in tickets),
        "reviewsCompleted": len(first_reviews),
        "cost": sum(r["cost"] for r in runs),
        "minutes": run["seconds"] / 60,
        "agentRuns": len(runs),
        "turns": sum(r["turns"] for r in runs),
        "missedEscalations": sum(t.get("must_escalate", False) and not escalated_early(t) for t in tickets),
        "unneededEscalations": sum(escalations(s) for t in tickets if not t.get("must_escalate", False) for s in t["stages"]),
        "patchRefusals": sum(p.startswith("patch refused") for s in stages for p in s["problems"]),
        "checkRepairs": sum(s["notes"].get("checkRepairs", 0) for s in stages),
        "ciRed": sum(c is not None and not all(c["notes"]["ci"].values()) for c in code),
        "planMatchFailures": sum(c is not None and not c["notes"]["planMatch"] for c in code),
        "existingTestsChanged": sum(any(s["notes"].get("existingTestsChanged") for s in t["stages"]) for t in tickets),
        "importantFound": sum(r["notes"]["important"] for r in first_reviews),
        "importantLeft": sum(r["notes"]["important"] for r in last_reviews),
        "repeats": sum(r["notes"]["repeats"] for r in first_reviews),
        "policyConcerns": sum(bool(s["notes"].get("citedPolicies")) for t in tickets for s in t["stages"] if s["stage"] == "spec"),
        "policyFindings": sum(r["notes"].get("policyFindings", 0) for r in first_reviews),
    }


def stage_cell(stage: dict | None) -> str:
    if stage is None:
        return "–"
    mark = {"ok": "✓", "escalated": "⚠", "blocked": "✗"}[stage["status"]]
    notes = stage["notes"]
    if notes.get("escalations") and stage["status"] == "ok":
        mark = "⚠✓"
    if notes.get("raisedBy") == "gate":
        mark += " gate"
    if notes.get("citedPolicies"):
        mark += f" cites {', '.join(notes['citedPolicies'])}"
    if "ci" in notes:
        mark += f" CI {'✓' if all(notes['ci'].values()) else '✗'} plan {'✓' if notes['planMatch'] else '✗'}"
    if "important" in notes:
        mark = f"{mark} {notes['important']}i/{notes['nit']}n"
    return mark


def run_markdown(run: dict) -> str:
    s = summary(run)
    tickets = run["tickets"]
    final = [c for c in (tickets[-1]["acceptance"] if tickets else []) if c["status"] != "skip"]
    lines = [f"# {run['scenario']} × {run['target']}: {sum(c['status'] == 'pass' for c in final)}/{len(final)} acceptance checks",
             "", f"{run['stack']}. OpenSDLC {run['opensdlc']}, {model_label([run])}, started {run['started']}.", ""]
    if run["error"]:
        lines += [f"**Run failed:** {run['error']}", ""]
    if run["stopped"]:
        lines += [f"**{run['stopped']}**", ""]
    lines += ["| Metric | Value |", "| :- | -: |"] + [f"| {label} | {fmt(s[key])} |" for key, (label, _, fmt) in METRICS.items()]
    names = ["intake", "spec", "plan", "build", "review"]
    lines += ["", "## Tickets", "", "| Ticket | " + " | ".join(n.title() for n in names) + " | Fixes | Acceptance | Cost |", "| :- |" + " :- |" * (len(names) + 3)]
    for ticket in tickets:
        by_name = {}
        for stage in ticket["stages"]:
            by_name.setdefault(stage["stage"], stage)
        last_review = next((x for x in reversed(ticket["stages"]) if x["stage"] == "review"), None)
        cells = [stage_cell(by_name.get(n)) for n in names[:-1]] + [stage_cell(by_name.get("review"))]
        if last_review is not by_name.get("review"):
            cells[-1] += f" → {stage_cell(last_review)}"
        applicable = [c for c in ticket["acceptance"] if c["status"] != "skip"]
        cost = sum(r["cost"] for st in ticket["stages"] for r in st["runs"])
        fixes = sum(st["stage"] == "fix" for st in ticket["stages"])
        name = f"{ticket['ticket']} (must escalate)" if ticket.get("must_escalate") else ticket["ticket"]
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {fixes} | {sum(c['status'] == 'pass' for c in applicable)}/{len(applicable)} | ${cost:.2f} |")
    if tickets:
        lines += ["", "## Acceptance after each ticket", "", "| Check | " + " | ".join(t["ticket"][:2] for t in tickets) + " |", "| :- |" + " :-: |" * len(tickets)]
        statuses = defaultdict(dict)
        for ticket in tickets:
            for check in ticket["acceptance"]:
                statuses[check["key"]][ticket["ticket"]] = check["status"]
        for key, by_ticket in statuses.items():
            lines.append(f"| {key} | " + " | ".join(MARK.get(by_ticket.get(t["ticket"], ""), " ") for t in tickets) + " |")
        escalated = raisers([run])
        if escalated:
            lines += ["", "## Where escalations were first raised", "", *escalated]
        failing = [c for c in tickets[-1]["acceptance"] if c["status"] == "fail"]
        if failing:
            lines += ["", "## Failing at the end", ""] + [f"- **{c['key']}**: {c['detail']}" for c in failing]
    problems = [(t["ticket"], s["stage"], p) for t in tickets for s in t["stages"] for p in s["problems"]]
    if problems:
        lines += ["", "## Problems", ""] + [f"- {t} {stage}: {p.splitlines()[0][:300]}" for t, stage, p in problems]
    return "\n".join(lines) + "\n"


def load(directory: Path) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for path in sorted(directory.glob("*/run-*.json")):
        run = json.loads(path.read_text())
        grouped[run["target"]].append(run)
    return dict(grouped)


def complete(runs: list[dict]) -> list[dict]:
    return [r for r in runs if not r["error"]]


def excluded(runs: list[dict]) -> list[str]:
    return [f"- {r['started']}: {r['error'].splitlines()[0][:200]}" for r in runs if r["error"]]


@dataclass(frozen=True)
class Difference:
    before: float
    after: float
    margin: float

    @classmethod
    def of(cls, before: list[float], after: list[float]) -> "Difference":
        if len(before) < 2 or len(after) < 2:
            return cls(mean(before), mean(after), inf)
        return cls(mean(before), mean(after), Z95 * sqrt(variance(before) / len(before) + variance(after) / len(after)))

    @property
    def change(self) -> float:
        return self.after - self.before

    @property
    def clear(self) -> bool:
        return abs(self.change) > self.margin

    def verdict(self, better: str) -> str:
        if not self.change or not better:
            return ""
        if not self.clear:
            return "within noise"
        return "better" if (self.change > 0) == (better == "up") else "worse"

    def span(self, fmt) -> str:
        if not self.change:
            return ""
        sign = "+" if self.change > 0 else "−"
        return f"{sign}{fmt(abs(self.change))} ± {fmt(self.margin)}" if self.margin != inf else f"{sign}{fmt(abs(self.change))}"


def values(runs: list[dict]) -> dict[str, list[float]]:
    summaries = [summary(r) for r in runs]
    return {key: [s[key] for s in summaries] for key in METRICS}


def stage_sessions(runs: list[dict]) -> dict[str, list[dict]]:
    found = defaultdict(list)
    for run in runs:
        for ticket in run["tickets"]:
            for stage in ticket["stages"]:
                for session in stage["runs"]:
                    name = session["prompt"].split()[0].split(":")[-1] if session["prompt"].startswith("/") else stage["stage"]
                    found[name].append(session)
    return dict(found)


def stage_lines(old: list[dict], new: list[dict]) -> list[str]:
    before, after = stage_sessions(old), stage_sessions(new)
    lines = ["| Stage | Sessions | Cost per session | Change, 95% | | Turns per session |", "| :- | -: | -: | -: | :- | -: |"]
    for name in sorted(set(before) & set(after), key=lambda n: -sum(s["cost"] for s in before[n])):
        cost = Difference.of([s["cost"] for s in before[name]], [s["cost"] for s in after[name]])
        turns = Difference.of([float(s["turns"]) for s in before[name]], [float(s["turns"]) for s in after[name]])
        money = lambda v: f"${v:.3f}"
        lines.append(f"| {name} | {len(before[name])} → {len(after[name])} | {money(cost.before)} → {money(cost.after)} | {cost.span(money)} | "
                     f"{cost.verdict('down')} | {count(turns.before)} → {count(turns.after)} |")
    return lines


def check_outcomes(runs: list[dict]) -> dict[str, list[float]]:
    outcomes = defaultdict(list)
    for run in runs:
        for check in (run["tickets"][-1]["acceptance"] if run["tickets"] else []):
            if check["status"] != "skip":
                outcomes[check["key"]].append(float(check["status"] == "pass"))
    return dict(outcomes)


def check_rates(runs: list[dict]) -> dict[str, float]:
    return {key: mean(v) for key, v in check_outcomes(runs).items()}


def suite_markdown(grouped: dict[str, list[dict]]) -> str:
    lines = ["# OpenSDLC benchmark", ""]
    for target, every in grouped.items():
        runs, skipped = complete(every), excluded(every)
        lines += [f"## {every[0]['scenario']} × {target} ({len(runs)} run{'s' if len(runs) != 1 else ''})", ""]
        if skipped:
            lines += ["Left out because they did not finish:", "", *skipped, ""]
        if not runs:
            continue
        summaries = [summary(r) for r in runs]
        lines += [f"{runs[0]['stack']}. OpenSDLC {runs[0]['opensdlc']}, {model_label(runs)}.", "",
                  "| Metric | Mean | Range |", "| :- | -: | -: |"]
        for key, (label, _, fmt) in METRICS.items():
            values = [s[key] for s in summaries]
            lines.append(f"| {label} | {fmt(mean(values))} | {fmt(min(values))} to {fmt(max(values))} |")
        flaky = {k: v for k, v in check_rates(runs).items() if v < 1}
        if flaky:
            lines += ["", "Checks that did not pass in every run:", ""] + [f"- {k}: {v:.0%}" for k, v in sorted(flaky.items(), key=lambda kv: kv[1])]
        escalated = raisers(runs)
        if escalated:
            lines += ["", "Where escalations were first raised:", "", *escalated]
        lines.append("")
    return "\n".join(lines)


def compare_markdown(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> str:
    lines = ["# OpenSDLC benchmark comparison", ""]
    for target in sorted(set(before) & set(after)):
        old, new = complete(before[target]), complete(after[target])
        skipped = excluded(before[target]) + excluded(after[target])
        lines += [f"## {target}: {len(old)} runs at {before[target][0]['opensdlc']} → {len(new)} runs at {after[target][0]['opensdlc']}", ""]
        if skipped:
            lines += ["Left out because they did not finish:", "", *skipped, ""]
        if not old or not new:
            lines += ["Nothing to compare yet.", ""]
            continue
        a, b = values(old), values(new)
        was, now = main_model(old), main_model(new)
        if was != now:
            lines += [f"**The runs used different models ({was} → {now}), so cost and quality differences may come from the model, not the change.**", ""]
        lines += ["A change is better or worse only when it is larger than its 95% margin, 1.96 standard errors of the difference between the two sets of runs; "
                  "anything smaller is within the noise between runs.", "",
                  "| Metric | Before | After | Change, 95% | |", "| :- | -: | -: | -: | :- |"]
        for key, (label, better, fmt) in METRICS.items():
            difference = Difference.of(a[key], b[key])
            lines.append(f"| {label} | {fmt(difference.before)} | {fmt(difference.after)} | {difference.span(fmt)} | {difference.verdict(better)} |")
        lines += ["", "Each session as one sample, by the skill it ran:", "", *stage_lines(old, new)]
        checks_a, checks_b = check_outcomes(old), check_outcomes(new)
        moved = [(k, Difference.of(checks_a.get(k, [0.0, 0.0]), checks_b.get(k, [0.0, 0.0]))) for k in sorted(set(checks_a) | set(checks_b))]
        moved = [(k, d) for k, d in moved if d.change]
        if moved:
            lines += ["", "Checks whose pass rate moved:", ""] + [f"- {k}: {d.before:.0%} → {d.after:.0%}{'' if d.clear else ' (within noise)'}" for k, d in moved]
        for side, runs in (("Before", old), ("After", new)):
            escalated = raisers(runs)
            if escalated:
                lines += ["", f"{side}, where escalations were first raised:", "", *escalated]
        lines.append("")
    return "\n".join(lines)
