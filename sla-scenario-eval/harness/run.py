"""Orchestrator — load inputs, run metrics, write report."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_config() -> dict:
    return json.loads((SKILL_ROOT / "config.json").read_text())


# ---------- input loading ----------

def load_scenarios(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        if "scenarios" in data:
            return data["scenarios"]
        if "items" in data:
            return data["items"]
        raise ValueError(f"{path}: expected list or {{scenarios: [...]}}")
    return data


def load_reasons(path: Path) -> list[dict]:
    text = path.read_text()
    if path.suffix.lower() == ".csv":
        reasons = []
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            cat = (row.get("category") or row.get("Category") or "").strip()
            name = (row.get("contact_reason") or row.get("name") or row.get("Contact Reason") or "").strip()
            if not name:
                continue
            reasons.append({"category": cat, "name": name})
        return reasons
    data = json.loads(text)
    if isinstance(data, dict) and "reasons" in data:
        data = data["reasons"]
    if isinstance(data, list):
        # First pass: build id -> name map so we can resolve parent_id to a
        # category string for taxonomies that use parent_id instead of flat
        # category fields (sla-contact-reason-eval shape).
        id_to_name = {r.get("id"): r.get("name") for r in data
                      if isinstance(r, dict) and r.get("id")}
        out = []
        for r in data:
            if isinstance(r, str):
                out.append({"category": "", "name": r})
                continue
            parent_id = r.get("parent_id")
            # Category precedence: explicit category > resolved parent name > ""
            category = r.get("category") or (id_to_name.get(parent_id) if parent_id else "") or ""
            out.append({
                "category": category,
                "name": r.get("name") or r.get("contact_reason"),
                "description": r.get("description", ""),
                "parent_id": parent_id,
            })
        return out
    raise ValueError(f"{path}: unrecognized reasons format")


def load_automation_scores(path: Path | None) -> dict[str, dict]:
    """Return {"<Category>::<SubReason>": {score, band, volume, ...}} or {} if no file.

    Accepts the DataPrep `final-result.json` shape (with `readinessStats.nodeScores`)
    or a bare `{<fqkey>: {...}}` dict.
    """
    if not path:
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "readinessStats" in data:
        data = data["readinessStats"].get("nodeScores") or {}
    if not isinstance(data, dict):
        return {}
    return data


def _annotate_reasons_with_automation(reasons: list[dict], scores: dict[str, dict]) -> None:
    """Mutate each reason in place to attach automationPotentialScore + Band when known."""
    for r in reasons:
        cat = (r.get("category") or "").strip()
        name = (r.get("name") or "").strip()
        key = f"{cat}::{name}" if cat else name
        s = scores.get(key)
        if not s:
            continue
        r["automation_potential_score"] = s.get("automationPotentialScore")
        r["automation_potential_band"] = s.get("automationPotentialBand")
        r["volume"] = s.get("volume")


def load_transcripts(dir_path: Path | None) -> dict[str, str]:
    if not dir_path or not dir_path.exists():
        return {}
    out = {}
    for p in sorted(dir_path.iterdir()):
        if p.is_file() and p.suffix.lower() in {".txt", ".md", ".json"}:
            if p.suffix.lower() == ".json":
                data = json.loads(p.read_text())
                turns = data if isinstance(data, list) else (data.get("turns") or [])
                if turns:
                    text = "\n".join(
                        f"{t.get('speaker') or t.get('role') or ''}: {t.get('text') or ''}"
                        for t in turns
                    )
                else:
                    text = p.read_text()
            else:
                text = p.read_text()
            out[p.stem] = text
    return out


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, required=True)
    ap.add_argument("--reasons", type=Path, required=True)
    ap.add_argument("--transcripts", type=Path, default=None, help="directory of normalized transcripts")
    ap.add_argument("--out", type=Path, default=SKILL_ROOT / "runs" / "latest")
    ap.add_argument("--static-only", action="store_true", help="skip judge-backed metrics")
    ap.add_argument("--include-ineligible", action="store_true",
                    help="score Conversation Coverage against ALL transcripts, including "
                         "UNRESOLVED / NOT_ACTIONABLE / KNOWLEDGE_ONLY calls. Default is "
                         "to exclude those from the denominator — SLA scenarios drive "
                         "tool-call-based resolutions, so convos a bot could not resolve "
                         "that way shouldn't count against coverage.")
    ap.add_argument("--sla-eligible-only", action="store_true",
                    help=argparse.SUPPRESS)  # kept for backward compat; now default behavior
    ap.add_argument("--coverage-sample", type=int, default=None,
                    help="when scoring conversation coverage, sample at most N conversations "
                         "(random, seeded, unbiased). Omit to score every transcript.")
    ap.add_argument("--coverage-concurrency", type=int, default=16,
                    help="parallel judge calls during conversation coverage (default 16)")
    ap.add_argument("--automation-scores", type=Path, default=None,
                    help="path to DataPrep final-result.json (or {<fqkey>: {...}} dict) "
                         "with automationPotentialScore / Band per reason. When present, "
                         "Tag coverage denominator drops leaves with band=='Not automatable' "
                         "(or score==0) — those reasons aren't SLA-training targets, so "
                         "missing scenarios on them isn't a gap.")
    ap.add_argument("--dry-run", action="store_true", help="validate inputs and exit")
    ap.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"))
    ap.add_argument("--cache-dir", type=Path, default=SKILL_ROOT / ".cache")
    args = ap.parse_args()

    config = _load_config()
    thresholds = config["thresholds"]

    scenarios = load_scenarios(args.scenarios)
    reasons = load_reasons(args.reasons)
    transcripts = load_transcripts(args.transcripts)
    automation_scores = load_automation_scores(args.automation_scores)
    if automation_scores:
        _annotate_reasons_with_automation(reasons, automation_scores)

    print(f"scenarios: {len(scenarios)}  reasons: {len(reasons)}  transcripts: {len(transcripts)}"
          + (f"  automation-scored: {sum(1 for r in reasons if 'automation_potential_score' in r)}"
             if automation_scores else ""))

    if args.dry_run:
        print("dry-run OK")
        return 0

    from static_metrics import (
        tag_coverage, evaluability, verification_coverage,
        criteria_completeness, field_completeness,
    )
    from report import write_report

    results: dict[str, Any] = {}

    any_tags = any((s.get("tags") or []) for s in scenarios)

    # P0 static
    if any_tags:
        results["tag_coverage"] = tag_coverage(scenarios, reasons)
    else:
        results["tag_coverage"] = {"skipped": True, "reason": "no tags on scenarios"}
    results["scenario_evaluability"] = evaluability(scenarios)
    results["verification_coverage"] = verification_coverage(
        scenarios, config["sensitive_patterns"], config["verification_patterns"]
    )
    results["criteria_completeness"] = criteria_completeness(
        scenarios, config["sensitive_patterns"], config["verification_patterns"]
    )
    results["field_completeness"] = field_completeness(scenarios, config["required_fields"])

    # Judge-based
    if args.static_only:
        for k in (
            "scenario_grounding", "conversation_coverage", "scenario_uniqueness",
            "tagging_confidence", "variation_coverage", "goal_criteria_fit",
        ):
            results[k] = {"skipped": True, "reason": "static-only mode"}
    else:
        import anthropic
        from judge import Judge
        from judge_metrics import (
            grounding, conversation_coverage, uniqueness, tagging_confidence,
            variation_coverage, goal_criteria_fit,
        )

        client = anthropic.Anthropic()
        judge = Judge(client=client, model=args.model, cache_dir=args.cache_dir)

        if transcripts:
            results["scenario_grounding"] = grounding(scenarios, transcripts, judge)
            results["conversation_coverage"] = conversation_coverage(
                scenarios, transcripts, judge,
                sla_eligible_only=not args.include_ineligible,
                sample_n=args.coverage_sample,
                concurrency=args.coverage_concurrency,
            )
        else:
            results["scenario_grounding"] = {"skipped": True, "reason": "no --transcripts provided"}
            results["conversation_coverage"] = {"skipped": True, "reason": "no --transcripts provided"}

        results["goal_criteria_fit"] = goal_criteria_fit(scenarios, judge)

        if any_tags:
            results["scenario_uniqueness"] = uniqueness(scenarios, judge)
            results["tagging_confidence"] = tagging_confidence(
                scenarios, reasons, config["tagging_confidence_floor"], judge
            )
            results["variation_coverage"] = variation_coverage(scenarios, reasons, judge)
        else:
            for k in ("scenario_uniqueness", "tagging_confidence", "variation_coverage"):
                results[k] = {"skipped": True, "reason": "no tags on scenarios"}

    write_report(results, thresholds, args.out)
    print(f"wrote {args.out}/report.md and scores.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
