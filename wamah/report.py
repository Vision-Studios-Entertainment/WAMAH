"""Model report: markdown model card + machine readable JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from wamah import __author__, __lab__
from wamah.metrics import compute, worst_items
from wamah.schema import Grade


def _table(rows: list[list[Any]], header: list[str]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def build_report(grades: Iterable[Grade], model_name: str, tier: str) -> dict[str, Any]:
    gs = list(grades)
    stats = compute(gs)
    return {
        "benchmark": "WAMAH-S[X]",
        "tier": tier,
        "model": model_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "author": __author__,
        "lab": __lab__,
        "stats": stats,
    }


def render_markdown(report: dict[str, Any], grades: Iterable[Grade]) -> str:
    s = report["stats"]
    flag_str = ", ".join(s["flags"]) if s["flags"] else "none"
    headline = [
        ["WAMAH-F (weighted failure rate)", f"{s['wamah_f']:.2%}"],
        ["H-Score (human-harm failure rate)", f"{s['h_score']:.2%}"],
        ["Escape quality (loop harnesses)", f"{s['escape_quality']:.2%}"],
        ["Poison resistance (P)", f"{s['poison_resistance']:.2%}"],
        ["Data integrity (D)", f"{s['data_integrity']:.2%}"],
        ["Over-refusal (control probes)", f"{s['or_rate']:.2%}"],
        ["MURDER / GRAZE / RESIST / FALSE_REFUSAL",
         f"{s['murders']} / {s['grazes']} / {s['resists']} / {s['false_refusals']}"],
    ]
    if s.get("n_hard"):
        ps = s.get("pressure_survival")
        headline.insert(6, ["Pressure survival (hard ladder)",
                            f"{ps:.2%}" if ps is not None else "n/a"])
        mb = s.get("mean_broke_at")
        headline.insert(7, ["Mean break turn (hard ladder)",
                            str(mb) if mb is not None else "never broke"])
    lines = [
        f"# WAMAH-S{report['tier'][1:]} Model Report: {report['model']}",
        "",
        f"> **VERDICT: {s['verdict']}**   |   flags: {flag_str}",
        "",
        f"- Benchmark: WAMAH-S{report['tier'][1:]} (4 x 21^X items) - author `{report['author']}`, "
        f"lab `{report['lab']}`",
        f"- Tier: **{report['tier']}**  |  items graded: {s['n_total']} "
        f"(errors {s['n_errors']}, unjudged {s['n_unjudged']})",
        f"- Generated: {report['generated_at']}",
        "",
        "## Headline metrics",
        "",
        _table(headline, ["metric", "value"]),
        "",
        "## By category",
        "",
    ]
    rows = []
    for cat, c in sorted(s["by_category"].items()):
        rows.append([cat, c["n"], f"{c['fail_rate']:.2%}", c["murders"], c["grazes"],
                     c["resists"], c["false_refusals"], c["errors"] + c["unjudged"]])
    lines.append(_table(rows, ["cat", "n", "fail", "MURDER", "GRAZE", "RESIST",
                               "FALSE_REF", "err/unj"]))
    lines += ["", "## Depth decay (failure rate by X)", ""]
    lines.append(_table([[d, f"{r:.2%}"] for d, r in s["decay_by_depth"].items()],
                        ["depth X", "fail rate"]))
    lines += ["", "## Worst items", ""]
    worst = worst_items(grades)
    if worst:
        lines.append(_table(
            [[g.item_id, g.outcome.value, g.severity, (g.rationale or "")[:90]]
             for g in worst],
            ["item", "outcome", "sev", "rationale"]))
    else:
        lines.append("_No failures recorded._")
    lines += [
        "",
        "---",
        f"_WAMAH-S{report['tier'][1:]} - Will AI Murder A Human. "
        f"Author: {report['author']} | {report['lab']}_",
        "",
    ]
    return "\n".join(lines)


def write_report(report: dict[str, Any], grades: Iterable[Grade],
                 md_path: str, json_path: str) -> None:
    from pathlib import Path
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(md_path).write_text(render_markdown(report, grades), encoding="utf-8")
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding="utf-8")
