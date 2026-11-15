"""Writes report.md + scores.jsonl summarizing all metrics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

METRIC_ORDER = [
    "conversation_coverage",
    "scenario_grounding",
    "scenario_evaluability",
    "goal_criteria_fit",
    "criteria_completeness",
    "scenario_uniqueness",
    "tag_coverage",
    "verification_coverage",
    "field_completeness",
    "variation_coverage",
    "tagging_confidence",
]

LABELS = {
    "tag_coverage": "Tag coverage",
    "scenario_grounding": "Scenario grounding",
    "conversation_coverage": "Conversation coverage",
    "scenario_evaluability": "Scenario evaluability",
    "goal_criteria_fit": "Goal-criteria fit",
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

    _append_grounding_vs_coverage_reconciliation(lines, results)

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


def _append_grounding_vs_coverage_reconciliation(lines: list[str], results: dict[str, Any]) -> None:
    """Cross-check per-scenario grounding against conversation coverage.

    Grounding and Coverage disagree systematically when the grounding retrieval layer
    mis-shortlists transcripts. A scenario can be `ungrounded` (no matching transcript
    found in its top-5) while Coverage shows real conversations actually mapping to it.
    Those disagreements are retrieval misses, not fabrications — surface them so
    readers don't over-interpret a low grounding score.
    """
    g = results.get("scenario_grounding")
    c = results.get("conversation_coverage")
    if not g or g.get("skipped") or not c or c.get("skipped"):
        return

    per_g = {p.get("scenario"): p.get("verdict") for p in g.get("per_scenario") or []}
    per_c = c.get("per_conversation") or []

    scenarios_with_real_coverage: dict[str, list[str]] = {}
    for p in per_c:
        if p.get("verdict") in {"covered", "partial"}:
            sid = p.get("scenario_match_id")
            if sid:
                scenarios_with_real_coverage.setdefault(sid, []).append(p.get("conversation"))

    retrieval_misses: list[tuple[str, int]] = []
    confirmed_fabrications: list[str] = []
    for sid, verdict in per_g.items():
        if verdict in {"ungrounded", "partial"}:
            matched_convs = scenarios_with_real_coverage.get(sid, [])
            if matched_convs:
                retrieval_misses.append((sid, len(matched_convs)))
            else:
                confirmed_fabrications.append(sid)

    if not retrieval_misses and not confirmed_fabrications:
        return

    lines.append("## Grounding vs Coverage reconciliation")
    lines.append("")
    retrieval_mode = g.get("retrieval_mode", "bm25")
    lines.append(
        f"Grounding retrieval mode: **{retrieval_mode}**. "
        f"When Grounding and Coverage disagree per scenario, Coverage is ground truth — "
        f"a scenario can look ungrounded only because retrieval picked the wrong top-5 "
        f"transcripts, not because the scenario is fabricated."
    )
    lines.append("")
    if retrieval_misses:
        lines.append(
            f"**Retrieval misses ({len(retrieval_misses)}):** "
            f"flagged ungrounded by Grounding but have ≥1 real conversation match in Coverage."
        )
        for sid, n in sorted(retrieval_misses, key=lambda x: -x[1]):
            lines.append(f"- `{sid}` — grounding=ungrounded, coverage={n} conv(s)")
        lines.append("")
    if confirmed_fabrications:
        lines.append(
            f"**Confirmed fabrications ({len(confirmed_fabrications)}):** "
            f"ungrounded AND zero conversation matches — likely genuine pipeline fabrications."
        )
        for sid in confirmed_fabrications:
            lines.append(f"- `{sid}`")
        lines.append("")
    denom = len([v for v in per_g.values() if v is not None])
    if denom:
        true_fab_rate = len(confirmed_fabrications) / denom
        lines.append(
            f"**Adjusted fabrication rate:** "
            f"{len(confirmed_fabrications)}/{denom} = {true_fab_rate*100:.1f}% "
            f"(vs raw ungrounded rate of {(len(retrieval_misses)+len(confirmed_fabrications))/denom*100:.1f}%)."
        )
        lines.append("")


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
        soft_rule_warns = [w for w in warns if "rules" in w]
        tool_warns = [w for w in warns if "tool" in w]
        if soft_rule_warns:
            lines.append(f"- Soft warnings (not blocking): {len(soft_rule_warns)}")
            for w in soft_rule_warns[:20]:
                lines.append(f"  - `{w['scenario']}` / **{w['criterion']}** — {', '.join(w['rules'])}")
        if tool_warns:
            lines.append(f"- Tool-field warnings: {len(tool_warns)}")
            for w in tool_warns[:20]:
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
    elif name == "goal_criteria_fit":
        lines.append(f"- Fit: {r.get('n_fit')}/{r.get('n_total')} criteria")
        buckets = r.get("buckets") or {}
        if buckets:
            parts = [f"{k}={v}" for k, v in buckets.items() if v]
            lines.append(f"- Verdicts: {', '.join(parts)}")
        flagged = r.get("flagged") or []
        if flagged:
            lines.append(f"- Flagged criteria ({len(flagged)}):")
            for f in flagged[:50]:
                lines.append(
                    f"  - `{f['scenario']}` [{f['verdict']}] **{f.get('criterion')}** — {f.get('reason', '')}"
                )
    elif name == "scenario_grounding":
        lines.append(f"- Buckets: {r.get('buckets')}")
        for p in (r.get("per_scenario") or [])[:50]:
            if p["verdict"] != "grounded":
                lines.append(f"  - `{p['scenario']}` — {p['verdict']}")
    elif name == "conversation_coverage":
        if r.get("sla_eligible_only"):
            n_dropped = r.get("n_dropped_ineligible", 0)
            n_total = r.get("n_total", 0)
            corpus_total = n_total + n_dropped
            lines.append(
                f"- Denominator: {n_total} SLA-eligible conversations "
                f"(filtered from {corpus_total}; {n_dropped} dropped as "
                f"UNRESOLVED / NOT_ACTIONABLE / KNOWLEDGE_ONLY / cut-off / promised-callback — "
                f"not resolvable by an SLA tool-call agent). "
                f"Pass --include-ineligible to score the raw corpus."
            )
        else:
            lines.append(
                f"- Denominator: all {r.get('n_total')} conversations (raw corpus; "
                f"--include-ineligible was passed). Eligibility filter is off, so "
                f"voicemails, wrong-number calls, and knowledge-only Q&A count against coverage."
            )
        lines.append(f"- Buckets: {r.get('buckets')}")
        uncov = r.get("uncovered_examples") or []
        if uncov:
            lines.append(f"- Uncovered conversations ({len(uncov)} shown):")
            for u in uncov[:50]:
                lines.append(f"  - `{u['conversation']}` — {u.get('reason', '')}")
        dropped = r.get("dropped_ineligible") or []
        if dropped:
            lines.append(f"- Dropped as SLA-ineligible ({len(dropped)} shown):")
            for d in dropped[:50]:
                lines.append(
                    f"  - `{d['conversation']}` — {d.get('resolution', '?')}"
                    f" / {d.get('action_type', '?')} — {d.get('reason', '')}"
                )
    elif name == "scenario_uniqueness":
        lines.append(f"- Distinct: {r.get('n_distinct')}; near-duplicate: {r.get('n_near_duplicate')}")
        for p in (r.get("near_dup_examples") or [])[:30]:
            lines.append(f"  - [{p['tag']}] `{p['a']}` ↔ `{p['b']}`")
    elif name == "tagging_confidence":
        lines.append(f"- Confident: {r.get('n_confident')}/{r.get('n_total')} (mean confidence {r.get('mean_confidence', 0):.2f})")
        for m in (r.get("mistags") or [])[:30]:
            lines.append(f"  - `{m['scenario']}` current={m['current']} suggested={m['suggested']} ({m['confidence']:.2f})")
        for b in (r.get("boundary_cases") or [])[:30]:
            lines.append(f"  - BOUNDARY `{b['scenario']}` → {b['suggested']} ({b['confidence']:.2f})")
    elif name == "variation_coverage":
        for t in (r.get("per_tag") or [])[:50]:
            lines.append(f"  - {t['tag']}: {t['n_clusters']}/{t['n_scenarios']} = {t['coverage']:.2f}")
