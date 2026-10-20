"""Orchestrator — parse before/after, diff, run metrics, write report."""
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

from parser import parse_script
from diff import compute_diff, effective_added_subagents


def _load_config() -> dict:
    return json.loads((SKILL_ROOT / "config.json").read_text())


def load_scenarios(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        if "scenarios" in data:
            return data["scenarios"]
        if "items" in data:
            return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: unrecognized scenarios format")


def load_reasons(path: Path | None) -> list[dict]:
    if not path:
        return []
    text = path.read_text()
    if path.suffix.lower() == ".csv":
        out = []
        for row in csv.DictReader(text.splitlines()):
            name = (row.get("contact_reason") or row.get("name") or "").strip()
            if not name:
                continue
            out.append({"category": (row.get("category") or "").strip(), "name": name})
        return out
    data = json.loads(text)
    if isinstance(data, dict) and "reasons" in data:
        data = data["reasons"]
    if isinstance(data, list):
        return [{"category": r.get("category", ""), "name": r.get("name") or r.get("contact_reason") or r} if isinstance(r, dict) else {"category": "", "name": r} for r in data]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--scenarios", type=Path, required=True)
    ap.add_argument("--reasons", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=SKILL_ROOT / "runs" / "latest")
    ap.add_argument("--static-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"))
    ap.add_argument("--cache-dir", type=Path, default=SKILL_ROOT / ".cache")
    args = ap.parse_args()

    config = _load_config()
    thresholds = config["thresholds"]

    before = parse_script(args.before)
    after = parse_script(args.after)
    scenarios = load_scenarios(args.scenarios)
    reasons = load_reasons(args.reasons)

    diff = compute_diff(before, after)
    added_subs = effective_added_subagents(diff)

    print(
        f"before: {len(before['subagents'])} subs ({before['format']})  "
        f"after: {len(after['subagents'])} subs ({after['format']})  "
        f"added-or-modified: {len(added_subs)}  scenarios: {len(scenarios)}"
    )
    if before["format"] == "unknown":
        print(f"WARN: could not parse --before ({args.before}); diff may be unreliable")
    if after["format"] == "unknown":
        print(f"WARN: could not parse --after ({args.after})")

    if args.dry_run:
        print("dry-run OK")
        return 0

    from static_metrics import (
        use_case_ownership, overfitting,
        use_case_focus, subagent_substance, action_gating,
        _attribute_scenarios,
    )
    from report import write_report

    attrib = _attribute_scenarios(added_subs, scenarios)

    results: dict[str, Any] = {}

    results["use_case_ownership"] = use_case_ownership(added_subs, scenarios, config["flow_phases"], attrib)
    results["overfitting_hardcoding"] = overfitting(added_subs, scenarios, config["hardcode_marker_patterns"])
    results["use_case_focus"] = use_case_focus(added_subs, attrib)
    results["subagent_substance"] = subagent_substance(added_subs, config)
    results["action_gating"] = action_gating(added_subs, attrib)

    if args.static_only:
        results["determinism"] = {"skipped": True, "reason": "static-only mode"}
        results["instruction_substance"] = {"skipped": True, "reason": "static-only mode"}
    else:
        import anthropic
        from judge import Judge
        from judge_metrics import determinism, instruction_substance
        client = anthropic.Anthropic()
        judge = Judge(client=client, model=args.model, cache_dir=args.cache_dir)
        results["determinism"] = determinism(added_subs, scenarios, config, attrib, judge)
        results["instruction_substance"] = instruction_substance(added_subs, attrib, judge)

    diff_summary = {
        "n_added": len(diff["added_subagents"]),
        "n_modified": len(diff["modified_subagents"]),
        "n_removed": len(diff["removed_subagents"]),
        "n_unchanged": len(diff["unchanged_subagents"]),
    }
    write_report(results, thresholds, args.out, diff_summary)
    print(f"wrote {args.out}/report.md and scores.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
