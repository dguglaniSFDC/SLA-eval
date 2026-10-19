"""Judge-backed metrics — determinism, instruction-substance."""
from __future__ import annotations

from typing import Any

from judge import Judge, JudgeCall


def determinism(added_subs: dict, scenarios: list[dict], config: dict, attrib: dict, judge: Judge) -> dict[str, Any]:
    known_signals = [s.lower() for s in config["known_condition_signals"]]
    rules_scored = 0
    rules_deterministic = 0
    nl_rules: list[dict] = []
    open_ended: list[dict] = []

    for name, sub in added_subs.items():
        for s in attrib.get(name, []):
            fact_keys = list((s.get("userContextFacts") or {}).keys()) + list((s.get("agentContextFacts") or {}).keys())
            fact_keys_l = [k.lower() for k in fact_keys]
            for c in s.get("criteria") or []:
                text = f"{c.get('name','')} {c.get('description','')}".lower()
                known = any(sig in text for sig in known_signals) or any(k in text for k in fact_keys_l)

                verdict = judge.call(JudgeCall(
                    template="pointwise",
                    rubric="determinism",
                    inputs={
                        "item_json": {"criterion": c, "subagent": name},
                        "evidence_block": sub.get("body_text", "")[:4000],
                    },
                ))
                ctype = str(verdict.get("condition_type", "open_ended")).lower()
                encoding = str(verdict.get("encoding", "natural_language")).lower()

                if ctype == "known" or known:
                    rules_scored += 1
                    if encoding == "deterministic":
                        rules_deterministic += 1
                    else:
                        nl_rules.append({"subagent": name, "criterion": c.get("name"), "reason": verdict.get("reason")})
                else:
                    open_ended.append({"subagent": name, "criterion": c.get("name"), "reason": verdict.get("reason")})

    score = rules_deterministic / rules_scored if rules_scored else 1.0
    return {
        "score": score,
        "n_known_rules": rules_scored,
        "n_deterministic": rules_deterministic,
        "natural_language_rules": nl_rules,
        "open_ended_rules": open_ended,
    }


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
