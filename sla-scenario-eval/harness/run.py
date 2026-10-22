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
        out = []
        for r in data:
            if isinstance(r, str):
                out.append({"category": "", "name": r})
            else:
                out.append({
                    "category": r.get("category", ""),
                    "name": r.get("name") or r.get("contact_reason"),
                    "description": r.get("description", ""),
                })
        return out
    raise ValueError(f"{path}: unrecognized reasons format")


def load_transcripts(dir_path: Path | None) -> dict[str, str]:
    if not dir_path or not dir_path.exists():
        return {}
    out = {}
    for p in sorted(dir_path.iterdir()):
        if p.is_file() and p.suffix.lower() in {".txt", ".md", ".json"}:
            if p.suffix.lower() == ".json":
                data = json.loads(p.read_text())
                if isinstance(data, list):
                    text = "\n".join(
                        f"{t.get('speaker') or t.get('role') or ''}: {t.get('text') or ''}"
                        for t in data
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
    ap.add_argument("--dry-run", action="store_true", help="validate inputs and exit")
    ap.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"))
    ap.add_argument("--cache-dir", type=Path, default=SKILL_ROOT / ".cache")
    args = ap.parse_args()

    config = _load_config()
    thresholds = config["thresholds"]

    scenarios = load_scenarios(args.scenarios)
    reasons = load_reasons(args.reasons)
    transcripts = load_transcripts(args.transcripts)

    print(f"scenarios: {len(scenarios)}  reasons: {len(reasons)}  transcripts: {len(transcripts)}")

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
        for k in ("scenario_grounding", "scenario_uniqueness", "tagging_confidence", "variation_coverage", "goal_criteria_fit"):
            results[k] = {"skipped": True, "reason": "static-only mode"}
    else:
        import anthropic
        from judge import Judge
        from judge_metrics import (
            grounding, uniqueness, tagging_confidence, variation_coverage,
            goal_criteria_fit,
        )

        client = anthropic.Anthropic()
        judge = Judge(client=client, model=args.model, cache_dir=args.cache_dir)

        if transcripts:
            results["scenario_grounding"] = grounding(scenarios, transcripts, judge)
        else:
            results["scenario_grounding"] = {"skipped": True, "reason": "no --transcripts provided"}

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
