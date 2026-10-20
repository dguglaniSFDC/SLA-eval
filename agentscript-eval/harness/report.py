"""Writes report.md + scores.jsonl for the agentscript eval."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

METRIC_ORDER = [
    "use_case_ownership",
    "determinism",
    "overfitting_hardcoding",
    "use_case_focus",
    "subagent_substance",
    "instruction_substance",
    "action_gating",
]

LABELS = {
    "use_case_ownership": "Use-case ownership",
    "determinism": "Determinism",
    "overfitting_hardcoding": "Overfitting / hardcoding",
    "use_case_focus": "Use-case focus",
    "subagent_substance": "Subagent substance",
    "instruction_substance": "Instruction substance",
    "action_gating": "Action gating",
}


def _status(score, threshold):
    if score is None:
        return "SKIP"
    if score >= threshold:
        return "PASS"
    if score >= threshold - 0.05:
        return "WARN"
    return "FAIL"


def _fmt_pct(score):
    if score is None:
        return "—"
    return f"{score * 100:.1f}%"


def write_report(results: dict[str, Any], thresholds: dict[str, float], out_dir: Path, diff_summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    scores_path = out_dir / "scores.jsonl"
    report_path = out_dir / "report.md"

    with scores_path.open("w") as f:
        for name in METRIC_ORDER:
            r = results.get(name)
            if r is None:
                continue
            f.write(json.dumps({"metric": name, **r}, default=str) + "\n")

    lines: list[str] = []
    lines.append("# AgentScript Evaluation Report\n")
    lines.append("## Diff summary\n")
    lines.append(f"- Subagents added: {diff_summary['n_added']}")
    lines.append(f"- Subagents modified: {diff_summary['n_modified']}")
    lines.append(f"- Subagents removed: {diff_summary['n_removed']}")
    lines.append(f"- Subagents unchanged: {diff_summary['n_unchanged']}")
    lines.append("")
    lines.append("| Metric | Score | Threshold | Status |")
    lines.append("|---|---|---|---|")
    for name in METRIC_ORDER:
        r = results.get(name)
        label = LABELS[name]
        thr = thresholds.get(name, 0.0)
        if r is None or r.get("skipped"):
            lines.append(f"| {label} | — | {thr*100:.0f}% | SKIP |")
            continue
        status = _status(r.get("score"), thr)
        lines.append(f"| {label} | {_fmt_pct(r.get('score'))} | {thr*100:.0f}% | {status} |")

    lines.append("")
    lines.append("## Drill-downs")
    lines.append("")
    for name in METRIC_ORDER:
        r = results.get(name)
        if r is None or r.get("skipped"):
            continue
        lines.append(f"### {LABELS[name]}")
        _drilldown(lines, name, r)
        lines.append("")

    report_path.write_text("\n".join(lines))


def _drilldown(lines, name, r):
    if name == "use_case_ownership":
        lines.append(f"- Owned: {r.get('n_owned')}/{r.get('n_scored')}")
        for u in (r.get("unowned") or [])[:30]:
            lines.append(f"  - `{u.get('scenario')}` → missing={u.get('missing_phases', [])}, handoff={u.get('mid_flow_handoff', False)}")
    elif name == "determinism":
        lines.append(f"- Deterministic: {r.get('n_deterministic')}/{r.get('n_known_rules')} known-condition rules")
        for n in (r.get("natural_language_rules") or [])[:20]:
            lines.append(f"  - `{n['subagent']}` — {n['criterion']}: {n['reason']}")
    elif name == "overfitting_hardcoding":
        lines.append(f"- Templated slots: {r.get('templated_slots')}; hardcoded literals: {len(r.get('hardcoded_literals', []))}")
        for h in (r.get("hardcoded_literals") or [])[:30]:
            lines.append(f"  - `{h['subagent']}` literal `{h['literal']}` ({h['kind']})")
        if r.get("heavily_hardcoded_subagents"):
            lines.append(f"- Heavy offenders: {', '.join(r['heavily_hardcoded_subagents'])}")
    elif name == "use_case_focus":
        lines.append(f"- Single-reason: {r.get('n_single_reason')}/{r.get('n_scored')}")
        for m in (r.get("multi_reason_subagents") or [])[:20]:
            lines.append(f"  - `{m['subagent']}` reasons={m['reasons']}")
        if r.get("subagents_without_scenarios"):
            lines.append(f"- No attributed scenarios: {', '.join(r['subagents_without_scenarios'])}")
    elif name == "subagent_substance":
        lines.append(f"- Passed: {r.get('n_passed')}/{r.get('n_total')}")
        for t in (r.get("thin_subagents") or [])[:30]:
            lines.append(f"  - `{t['subagent']}` fails={t['fails']} instr={t['instruction_count']} actions={t['real_action_count']}")
    elif name == "instruction_substance":
        lines.append(f"- Reflected: {r.get('n_reflected')}/{r.get('n_total')}")
        for p in (r.get("per_subagent") or [])[:20]:
            if p["ratio"] is not None and p["ratio"] < 1.0:
                lines.append(f"  - `{p['subagent']}` {p['reflected']}/{p['total']} missing={p['missing']}")
    elif name == "action_gating":
        lines.append(f"- Gated: {r.get('n_gated')}/{r.get('n_with_precondition')}")
        for u in (r.get("sensitive_ungated") or [])[:30]:
            lines.append(f"  - SENSITIVE ungated: `{u['subagent']}` {u['action']}")
        for u in (r.get("ungated") or [])[:30]:
            lines.append(f"  - `{u['subagent']}` {u['action']} ({u['verb']})")
