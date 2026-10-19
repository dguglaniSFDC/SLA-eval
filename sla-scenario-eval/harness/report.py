"""Writes report.md + scores.jsonl summarizing all metrics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

METRIC_ORDER = [
    "tag_coverage",
    "scenario_grounding",
    "scenario_evaluability",
    "verification_coverage",
    "criteria_completeness",
    "field_completeness",
    "variation_coverage",
    "scenario_uniqueness",
    "tagging_confidence",
]

LABELS = {
    "tag_coverage": "Tag coverage",
    "scenario_grounding": "Scenario grounding",
    "scenario_evaluability": "Scenario evaluability",
    "verification_coverage": "Verification-criteria coverage",
    "criteria_completeness": "Criteria completeness",
    "field_completeness": "Field completeness rate",
    "variation_coverage": "Variation coverage",
    "scenario_uniqueness": "Scenario uniqueness",
    "tagging_confidence": "Taxonomy tagging confidence",
}


def _status(score: float, threshold: float) -> str:
    if score is None:
        return "SKIP"
    if score >= threshold:
        return "PASS"
    if score >= threshold - 0.05:
        return "WARN"
    return "FAIL"


def _fmt_pct(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{score * 100:.1f}%"


def write_report(results: dict[str, Any], thresholds: dict[str, float], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    scores_path = out_dir / "scores.jsonl"

    with scores_path.open("w") as f:
        for name in METRIC_ORDER:
            r = results.get(name)
            if r is None:
                continue
            f.write(json.dumps({"metric": name, **r}, default=str) + "\n")

    lines: list[str] = []
    lines.append("# SLA Scenario Evaluation Report\n")
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
        score = r.get("score")
        status = _status(score, thr)
        lines.append(f"| {label} | {_fmt_pct(score)} | {thr*100:.0f}% | {status} |")

    lines.append("")
    lines.append("## Drill-downs")
    lines.append("")
    for name in METRIC_ORDER:
        r = results.get(name)
        if r is None or r.get("skipped"):
            continue
        lines.append(f"### {LABELS[name]}")
        _append_drilldown(lines, name, r)
        lines.append("")

    report_path.write_text("\n".join(lines))


def _append_drilldown(lines: list[str], name: str, r: dict) -> None:
    if name == "tag_coverage":
        uncov = r.get("uncovered") or []
        lines.append(f"- Covered: {r.get('n_covered')}/{r.get('n_total')}")
        if uncov:
            lines.append("- Uncovered reasons:")
            for u in uncov[:50]:
                lines.append(f"  - {u.get('category')}::{u.get('name')}")
        over = r.get("oversampled") or []
        if over:
            lines.append(f"- Oversampled: {', '.join(over)}")
    elif name == "scenario_evaluability":
        lines.append(f"- Passable: {r.get('n_passable')}/{r.get('n_total')} criteria")
        blocks = r.get("blocked") or []
        if blocks:
            lines.append("- Blocked criteria:")
            for b in blocks[:50]:
                lines.append(f"  - `{b['scenario']}` / **{b['criterion']}** — {', '.join(b['rules'])}")
        warns = r.get("warnings") or []
        if warns:
            lines.append(f"- Tool-field warnings: {len(warns)}")
            for w in warns[:20]:
                lines.append(f"  - `{w['scenario']}` / {w['tool']}.{w['field']} ({w['where']})")
        unanchored = r.get("unanchored_scenarios") or []
        if unanchored:
            lines.append(f"- Unanchored scenarios: {', '.join(unanchored)}")
    elif name == "verification_coverage":
        lines.append(f"- Sensitive: {r.get('n_sensitive')}; Gated: {r.get('n_gated')}")
        for u in (r.get("ungated") or [])[:50]:
            lines.append(f"  - `{u['scenario']}` — matched: {u['matched_sensitive_keyword']}")
    elif name == "criteria_completeness":
        lines.append(f"- Fail tool-invoked: {r.get('n_fail_tool_invoked')}; fail outcome: {r.get('n_fail_outcome_stated')}; fail verification: {r.get('n_fail_verification_honored')}")
        for w in (r.get("weak_scenarios") or [])[:50]:
            lines.append(f"  - `{w['scenario']}` avg={w['avg']}")
    elif name == "field_completeness":
        lines.append(f"- Per-field missing: {r.get('per_field_missing')}")
        under = r.get("under_specified") or []
        if under:
            lines.append(f"- Under-specified (≥3 empty fields): {', '.join(under)}")
    elif name == "scenario_grounding":
        lines.append(f"- Buckets: {r.get('buckets')}")
        for p in (r.get("per_scenario") or [])[:50]:
            if p["verdict"] != "grounded":
                lines.append(f"  - `{p['scenario']}` — {p['verdict']}")
    elif name == "scenario_uniqueness":
        lines.append(f"- Distinct: {r.get('n_distinct')}; near-duplicate: {r.get('n_near_duplicate')}")
        for p in (r.get("near_dup_examples") or [])[:30]:
            lines.append(f"  - [{p['tag']}] `{p['a']}` ↔ `{p['b']}`")
    elif name == "tagging_confidence":
        lines.append(f"- Mean confidence: {r.get('mean_confidence', 0):.2f}")
        for m in (r.get("mistags") or [])[:30]:
            lines.append(f"  - `{m['scenario']}` current={m['current']} suggested={m['suggested']} ({m['confidence']:.2f})")
        for b in (r.get("boundary_cases") or [])[:30]:
            lines.append(f"  - BOUNDARY `{b['scenario']}` → {b['suggested']} ({b['confidence']:.2f})")
    elif name == "variation_coverage":
        for t in (r.get("per_tag") or [])[:50]:
            lines.append(f"  - {t['tag']}: {t['n_clusters']}/{t['n_scenarios']} = {t['coverage']:.2f}")
