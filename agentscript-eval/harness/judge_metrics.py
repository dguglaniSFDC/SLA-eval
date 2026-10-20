"""Judge-backed metrics — determinism, instruction-substance, overfitting."""
from __future__ import annotations

import re
from typing import Any

from judge import Judge, JudgeCall


def overfitting(added_subs: dict, judge: Judge) -> dict[str, Any]:
    """Industry-tied vs industry-generic. For each added subagent, ask the judge
    whether its prose, action references, and variable names reveal a specific
    industry/vertical that would prevent the subagent from being reused in a
    different domain. Score = fraction of added subagents the judge marks generic."""
    generic = 0
    tied: list[dict] = []
    per_sub: list[dict] = []

    for name, sub in added_subs.items():
        body = sub.get("body_text", "") or ""
        instr = "\n".join(sub.get("instructions", []))
        evidence = (body + "\n" + instr)[:6000]

        verdict = judge.call(JudgeCall(
            template="pointwise",
            rubric="overfitting",
            inputs={
                "item_json": {"subagent": name},
                "evidence_block": evidence,
            },
        ))
        is_generic = bool(verdict.get("industry_generic"))
        markers = verdict.get("industry_markers") or []
        inferred = verdict.get("inferred_industry") or ""
        reason = verdict.get("reason") or ""

        row = {
            "subagent": name,
            "industry_generic": is_generic,
            "inferred_industry": inferred,
            "markers": markers,
            "reason": reason,
        }
        per_sub.append(row)
        if is_generic:
            generic += 1
        else:
            tied.append(row)

    denom = len(added_subs)
    score = generic / denom if denom else 1.0
    return {
        "score": score,
        "n_generic": generic,
        "n_total": denom,
        "industry_tied_subagents": tied,
        "per_subagent": per_sub,
    }


def _render_determinism_evidence(sub: dict) -> str:
    body = sub.get("body_text", "") or ""
    return body[:6000]


_SET_VAR_RE = re.compile(r"set\s+@variables\.([A-Za-z_][A-Za-z0-9_]*)\s*=", re.IGNORECASE)
_LINKED_VAR_RE = re.compile(r"@variables\.([A-Za-z_][A-Za-z0-9_]*)\s*:\s*linked", re.IGNORECASE)
_LINKED_DECL_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*linked\s", re.MULTILINE)
_VAR_REF_RE = re.compile(r"@variables\.([A-Za-z_][A-Za-z0-9_]*)")


def _collect_written_variables(script: dict) -> set[str]:
    """Return the set of @variables.X names that any action writes to or that are linked
    from an external source (both are legitimate "has a writer" cases)."""
    written: set[str] = set()
    for sub in (script or {}).values():
        body = sub.get("body_text") or ""
        for m in _SET_VAR_RE.finditer(body):
            written.add(m.group(1))
        for m in _LINKED_DECL_RE.finditer(body):
            written.add(m.group(1))
    return {v.lower() for v in written}


def determinism(added_subs: dict, scenarios: list[dict], config: dict, attrib: dict, judge: Judge, full_after: dict | None = None) -> dict[str, Any]:
    known_signals = [s.lower() for s in config["known_condition_signals"]]
    rules_scorable = 0
    rules_deterministic = 0
    nl_rules: list[dict] = []
    grammar_limit_rules: list[dict] = []
    open_ended: list[dict] = []

    written_vars = _collect_written_variables(full_after or added_subs)

    for name, sub in added_subs.items():
        evidence = _render_determinism_evidence(sub)
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
                        "item_json": {"criterion": c, "subagent": name, "written_variables": sorted(written_vars)},
                        "evidence_block": evidence,
                    },
                ))
                ctype = str(verdict.get("condition_type", "open_ended")).lower()
                encoding = str(verdict.get("encoding", "natural_language")).lower()
                predloc = str(verdict.get("predicate_location", "none")).lower()
                if predloc == "none" and encoding == "deterministic":
                    encoding = "natural_language"

                # Static override: if the judge said natural_language and cited a predicate
                # variable, verify at least one of the referenced variables actually has a
                # writer (set statement or linked source) somewhere in the script. If none
                # do, the predicate cannot be lifted deterministically — reclassify as
                # grammar_limit so the author is not penalized for a fix the grammar
                # cannot support.
                if encoding == "natural_language":
                    reason_text = str(verdict.get("reason") or "")
                    referenced = {m.group(1).lower() for m in _VAR_REF_RE.finditer(reason_text)}
                    if referenced and not (referenced & written_vars):
                        encoding = "grammar_limit"
                        verdict["reason"] = (
                            reason_text
                            + f" [grammar-limit: referenced variable(s) {sorted(referenced)} have no writer in the script; cannot be gated.]"
                        )

                if ctype == "known" or known:
                    if encoding == "grammar_limit":
                        grammar_limit_rules.append({"subagent": name, "criterion": c.get("name"), "reason": verdict.get("reason")})
                        continue
                    rules_scorable += 1
                    if encoding == "deterministic":
                        rules_deterministic += 1
                    else:
                        nl_rules.append({
                            "subagent": name,
                            "criterion": c.get("name"),
                            "reason": verdict.get("reason"),
                            "suggested_fix": "Lift the predicate onto an `available when @variables.X==Y` clause on the relevant action/transition, or add a single-line `if @variables.X: transition to @subagent.Y` tail. Do not add if/else to instructions.",
                        })
                else:
                    open_ended.append({"subagent": name, "criterion": c.get("name"), "reason": verdict.get("reason")})

    score = rules_deterministic / rules_scorable if rules_scorable else 1.0
    return {
        "score": score,
        "n_known_rules": rules_scorable,
        "n_deterministic": rules_deterministic,
        "n_grammar_limit": len(grammar_limit_rules),
        "natural_language_rules": nl_rules,
        "grammar_limit_rules": grammar_limit_rules,
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
