# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import asdict
from datetime import datetime, timedelta

from .dataset import Dataset
from .indicators import INDICATORS, SUPPLEMENTS, Indicator, Measurement
from .records import Window

STAGES = ("Plan", "Design", "Build", "Test", "Deploy", "Maintain")
FORMATS = {
    "share": lambda v: f"{v:.0%}",
    "hours": lambda v: f"{v:.1f} h" if v < 48 else f"{v / 24:.1f} d",
    "minutes": lambda v: f"{v:.0f} min" if v < 120 else f"{v / 60:.1f} h",
    "days": lambda v: f"{v:.1f} d",
}


def windows(end: datetime, days: int) -> tuple[Window, Window]:
    span = timedelta(days=days)
    return Window(end - span, end), Window(end - 2 * span, end - span)


def baseline_window(adopted: datetime | None, days: int) -> Window | None:
    return Window(adopted - timedelta(days=days), adopted) if adopted else None


def fmt(indicator: Indicator, value: float | None) -> str:
    if value is None:
        return "–"
    return FORMATS.get(indicator.unit, lambda v: f"{v:.2f}".rstrip("0").rstrip("."))(value)


def trend(indicator: Indicator, now: Measurement, before: Measurement | None, label: str) -> str:
    if before is None or now.value is None or before.value is None or now.value == before.value:
        return ""
    rising = now.value > before.value
    improving = rising == (indicator.better == "up")
    return f"{'▲' if rising else '▼'} {'better' if improving else 'worse'} than {label} ({fmt(indicator, before.value)})"


def row(indicator: Indicator, data: Dataset, current: Window, previous: Window, baseline: Window | None) -> dict:
    now, before = indicator.measure(data, current), indicator.measure(data, previous)
    base = indicator.measure(data, baseline) if baseline else None
    return {
        "id": indicator.id, "stage": indicator.stage, "play": indicator.play, "kind": indicator.kind,
        "title": indicator.title, "unit": indicator.unit, "better": indicator.better, "note": indicator.note,
        "current": asdict(now), "previous": asdict(before), "baseline": asdict(base) if base else None,
        "display": fmt(indicator, now.value),
        "baselineDisplay": fmt(indicator, base.value) if base else "",
        "trend": trend(indicator, now, before, "last window"),
        "vsBaseline": trend(indicator, now, base, "baseline"),
    }


def build(data: Dataset, end: datetime, days: int, adopted: datetime | None = None) -> dict:
    current, previous = windows(end, days)
    baseline = baseline_window(adopted, days)
    rows = [row(i, data, current, previous, baseline) for i in INDICATORS]
    return {
        "window": {"start": current.start.isoformat(), "end": current.end.isoformat(), "days": days},
        "baseline": {"start": baseline.start.isoformat(), "end": baseline.end.isoformat()} if baseline else None,
        "collected": sum(r["current"]["status"] != "unavailable" for r in rows),
        "total": len(rows),
        "indicators": rows,
    } | {s.key: [row(i, data, current, previous, baseline) for i in s.indicators] for s in SUPPLEMENTS}


def table(rows: list[dict], with_baseline: bool) -> list[str]:
    head = "| Indicator | Play | Kind | Value | n | Trend |" + (" Baseline | vs baseline |" if with_baseline else "")
    rule = "| :- | :- | :- | -: | -: | :- |" + (" -: | :- |" if with_baseline else "")
    lines = [head, rule]
    for r in rows:
        value = "not collected" if r["current"]["status"] == "unavailable" else r["display"]
        line = f"| {r['title']} | {r['play']} | {r['kind']} | {value} | {r['current']['n']} | {r['trend']} |"
        if with_baseline:
            line += f" {r['baselineDisplay']} | {r['vsBaseline']} |"
        lines.append(line)
    return lines


def markdown(report: dict) -> str:
    window = report["window"]
    with_baseline = report["baseline"] is not None
    lines = [
        f"## OpenSDLC indicators, last {window['days']} days",
        "",
        f"{report['collected']} of {report['total']} indicators collected, to {window['end'][:10]}."
        + (f" Baseline is the {window['days']} days before adoption, to {report['baseline']['end'][:10]}." if with_baseline else ""),
    ]
    for stage in STAGES:
        lines += ["", f"### {stage}", ""] + table([r for r in report["indicators"] if r["stage"] == stage], with_baseline)
    every = list(report["indicators"])
    for supplement in SUPPLEMENTS:
        lines += ["", f"### {supplement.title}", "", supplement.summary, ""] + table(report[supplement.key], with_baseline)
        every += report[supplement.key]
    missing = sorted({need for r in every if r["current"]["status"] == "unavailable" for need in r["current"]["detail"].split("; ")})
    if missing:
        lines += ["", "### To collect the rest", ""] + [f"- {need}" for need in missing]
    notes = [f"- **{r['title']}**: {r['note']}" for r in every if r["note"]]
    if notes:
        lines += ["", "### Notes", ""] + notes
    return "\n".join(lines)
