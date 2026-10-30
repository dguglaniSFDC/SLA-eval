"""Write report.md + scores.jsonl from the metric results dict."""
from __future__ import annotations

import json
from pathlib import Path

METRIC_TITLES = {
    "coverage": "Coverage",
    "evidence_backing": "Evidence Backing",
    "sibling_distinctness": "Sibling Distinctness",
}

METRIC_WHAT = {
    "coverage": "Of distinct customer intents in the sampled corpus, the fraction represented by at least one taxonomy reason.",
    "evidence_backing": "Of taxonomy reasons, the fraction grounded in at least one real conversation (not invented).",
    "sibling_distinctness": "Of sibling reason pairs under the same parent, the fraction that are meaningfully distinct.",
}


def _status(score: float, threshold: float) -> str:
    if score >= threshold:
        return "PASS"
    if score >= threshold - 0.05:
        return "WARN"
    return "FAIL"


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def write_report(run_dir: Path, results: dict[str, dict]) -> None:
    scores_path = run_dir / "scores.jsonl"
    with scores_path.open("w") as f:
        for metric, r in results.items():
            f.write(json.dumps({
                "metric": metric,
                "priority": r["priority"],
                "score": r["score"],
                "threshold": r["threshold"],
                "status": _status(r["score"], r["threshold"]),
            }) + "\n")

    lines: list[str] = []
    lines.append(f"# Contact Reason Eval — {run_dir.name}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Priority | Score | Threshold | Status |")
    lines.append("|---|---|---|---|---|")
    for metric, r in results.items():
        if r["details"].get("skipped"):
            lines.append(f"| {METRIC_TITLES[metric]} | {r['priority']} | — | {_fmt_pct(r['threshold'])} | SKIPPED |")
            continue
        lines.append(
            f"| {METRIC_TITLES[metric]} | {r['priority']} | "
            f"{_fmt_pct(r['score'])} | {_fmt_pct(r['threshold'])} | "
            f"{_status(r['score'], r['threshold'])} |"
        )
    lines.append("")

    for metric, r in results.items():
        lines.append(f"## {METRIC_TITLES[metric]}")
        lines.append("")
        lines.append(f"**What's being measured:** {METRIC_WHAT[metric]}")
        lines.append("")
        d = r["details"]
        if d.get("skipped"):
            lines.append(f"_Skipped: {d.get('reason', 'no reason given')}_")
            lines.append("")
            continue

        if metric == "coverage":
            lines.append(f"- Reference intents (post-clustering): {d['reference_intent_count']}")
            lines.append(f"- Matched to a taxonomy leaf: {d['matched']}")
            if d["missing_from_taxonomy"]:
                lines.append("")
                lines.append("### Missing from taxonomy (unassignable intents)")
                for ex in d["missing_from_taxonomy"][:15]:
                    lines.append(
                        f"- **{ex.get('intent_label', '(unlabeled)')}** "
                        f"(support: {ex.get('support_count')}) — "
                        f"{ex.get('one_line_description', '')[:200]}"
                    )
        elif metric == "evidence_backing":
            lines.append(f"- Reasons evaluated: {d['total']}")
            lines.append(f"- Supported by corpus: {d['supported']}")
            if d["candidate_removals"]:
                lines.append("")
                lines.append("### Candidate removals (reasons with no corpus support)")
                for ex in d["candidate_removals"][:20]:
                    lines.append(
                        f"- `{ex.get('reason_id')}` **{ex.get('name')}** — "
                        f"{ex.get('reason', '')[:200]}"
                    )
        elif metric == "sibling_distinctness":
            lines.append(f"- Sibling pairs evaluated: {d['pairs']}")
            lines.append(f"- Distinct: {d['distinct']}")
            if d["merge_candidates"]:
                lines.append("")
                lines.append(f"### Merge candidates ({len(d['merge_candidates'])} total)")
                for ex in d["merge_candidates"]:
                    examples = ex.get("overlap_examples") or []
                    ex_line = "; ".join(examples[:2]) if examples else ""
                    lines.append(
                        f"- **{ex.get('a_name')}** (`{ex.get('a_id')}`) ↔ "
                        f"**{ex.get('b_name')}** (`{ex.get('b_id')}`)"
                        + (f" — overlap: {ex_line}" if ex_line else "")
                    )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## How to read this report")
    lines.append("")
    lines.append("- **PASS** = at or above threshold. **WARN** = within 5 pts below. **FAIL** = more than 5 pts below.")
    lines.append("- Each metric uses its own judge rubric (`rubrics/<metric>.md`) and template (`judges/<template>.md`).")
    lines.append("- Numbers are reproducible when the judge model, rubric, and inputs are unchanged (temperature=0 + cache).")
    lines.append("")

    (run_dir / "report.md").write_text("\n".join(lines))
