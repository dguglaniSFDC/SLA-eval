"""Judge-backed metrics — instruction-substance."""
from __future__ import annotations

from typing import Any

from judge import Judge, JudgeCall


def instruction_substance(added_subs: dict, attrib: dict, judge: Judge) -> dict[str, Any]:
    totals = 0
    reflected = 0
    per_sub = []
    for name, sub in added_subs.items():
        sub_scenarios = attrib.get(name, [])
        sub_rules = []
        for s in sub_scenarios:
            sub_rules.extend(s.get("criteria") or [])
        if not sub_rules:
            continue
        instr_blob = "\n".join(sub.get("instructions", []))[:6000]
        sub_total = 0
        sub_reflected = 0
        missing: list[str] = []
        for c in sub_rules:
            verdict = judge.call(JudgeCall(
                template="pointwise",
                rubric="instruction-substance",
                inputs={
                    "item_json": {"criterion": c, "subagent": name},
                    "evidence_block": instr_blob,
                },
            ))
            ok = bool(verdict.get("reflected"))
            sub_total += 1
            if ok:
                sub_reflected += 1
            else:
                missing.append(c.get("name") or "")
        totals += sub_total
        reflected += sub_reflected
        per_sub.append({
            "subagent": name,
            "reflected": sub_reflected,
            "total": sub_total,
            "ratio": round(sub_reflected / sub_total, 3) if sub_total else None,
            "missing": missing,
        })

    score = reflected / totals if totals else 1.0
    return {
        "score": score,
        "n_reflected": reflected,
        "n_total": totals,
        "per_subagent": per_sub,
    }
