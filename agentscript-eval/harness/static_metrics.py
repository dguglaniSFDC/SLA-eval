"""Static metrics — use-case ownership, overfitting, focus, substance, gating."""
from __future__ import annotations

import re
from typing import Any


# ---------- helpers ----------

def _tag_to_reason(tag: str) -> tuple[str, str]:
    if "::" in tag:
        c, n = tag.split("::", 1)
        return c.strip().lower(), n.strip().lower()
    return "", tag.strip().lower()


def _attribute_scenarios(added_subs: dict, scenarios: list[dict]) -> dict[str, list[dict]]:
    """Return {subagent_name: [scenario, ...]}."""
    attrib: dict[str, list[dict]] = {name: [] for name in added_subs}
    for s in scenarios:
        sid = s.get("id") or ""
        tags = [t.lower() for t in (s.get("tags") or [])]
        scen_text = (
            (s.get("goal") or "") + " "
            + " ".join((c.get("name") or "") + " " + (c.get("description") or "") for c in (s.get("criteria") or []))
        ).lower()
        for name, sub in added_subs.items():
            hay = (sub.get("body_text", "") + " " + " ".join(sub.get("instructions", []))).lower()
            if sid and sid.lower() in hay:
                attrib[name].append(s)
                continue
            if any(t in hay for t in tags) or any(_tag_to_reason(t)[1] in hay for t in tags):
                attrib[name].append(s)
                continue
            name_tokens = re.findall(r"[a-z]{4,}", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower())
            name_tokens = [t for t in name_tokens if t not in {"agent", "subagent", "handler", "router"}]
            if name_tokens and any(tok in scen_text for tok in name_tokens):
                attrib[name].append(s)
    return attrib


# ---------- 1. Use-Case Ownership ----------

def _phase_of(action: dict, flow_phases: dict) -> str | None:
    verb = (action.get("type") or "").lower()
    target = (action.get("target") or "").lower()
    tokens = set(re.findall(r"[a-z]+", f"{verb} {target}"))
    for phase in ("lookup", "action", "confirmation", "decision"):
        verbs = flow_phases.get(phase, [])
        if any(v in tokens for v in verbs):
            return phase
    return None


HANDOFF_VERBS = {"handoff", "transition", "route", "delegate", "transfer"}


def use_case_ownership(added_subs: dict, scenarios: list[dict], flow_phases: dict, attrib: dict) -> dict[str, Any]:
    owned = 0
    unowned = []
    scored = 0

    sub_of_scenario: dict[str, str] = {}
    for name, scen_list in attrib.items():
        for s in scen_list:
            sid = s.get("id")
            if sid:
                sub_of_scenario.setdefault(sid, name)

    for s in scenarios:
        sid = s.get("id") or ""
        sub_name = sub_of_scenario.get(sid)
        if not sub_name:
            unowned.append({"scenario": sid, "reason": "no attributed subagent"})
            continue
        sub = added_subs[sub_name]
        scored += 1
        actions = sub.get("actions", [])
        phases_present = {_phase_of(a, flow_phases) for a in actions}
        phases_present.discard(None)

        criteria_phases = set()
        for c in s.get("criteria") or []:
            text = f"{c.get('name','')} {c.get('description','')}".lower()
            for ph, verbs in flow_phases.items():
                if any(v in text for v in verbs):
                    criteria_phases.add(ph)

        missing = criteria_phases - phases_present

        handoff_idx = None
        first_action_idx = None
        last_conf_idx = None
        for i, a in enumerate(actions):
            if a.get("type") in HANDOFF_VERBS and a.get("type") != "escalate":
                if handoff_idx is None:
                    handoff_idx = i
            if first_action_idx is None and _phase_of(a, flow_phases) == "lookup":
                first_action_idx = i
            if _phase_of(a, flow_phases) == "confirmation":
                last_conf_idx = i

        has_mid_flow_handoff = (
            handoff_idx is not None
            and first_action_idx is not None
            and last_conf_idx is not None
            and first_action_idx < handoff_idx < last_conf_idx
        )

        if not missing and not has_mid_flow_handoff:
            owned += 1
        else:
            unowned.append({
                "scenario": sid,
                "subagent": sub_name,
                "missing_phases": sorted(missing),
                "mid_flow_handoff": has_mid_flow_handoff,
            })

    score = owned / scored if scored else 0.0
    return {"score": score, "n_owned": owned, "n_scored": scored, "unowned": unowned}


# ---------- 2. Overfitting / Hardcoding ----------

def overfitting(added_subs: dict, scenarios: list[dict], marker_patterns: list[str]) -> dict[str, Any]:
    seed_literals: set[str] = set()
    for s in scenarios:
        for seed in s.get("sampleSeeds") or []:
            for v in (seed.get("values") or {}).values():
                if isinstance(v, (str, int, float)):
                    seed_literals.add(str(v))

    hardcoded: list[dict] = []
    templated_slots = 0
    for name, sub in added_subs.items():
        body = sub.get("body_text", "") + "\n" + "\n".join(sub.get("instructions", []))
        templated_slots += len(re.findall(r"\$\{[^}]+\}|\{\{[^}]+\}\}", body))

        for lit in seed_literals:
            if lit and lit in body:
                hardcoded.append({"subagent": name, "literal": lit, "kind": "seed_value"})
        for pat in marker_patterns:
            for m in re.findall(pat, body):
                hardcoded.append({"subagent": name, "literal": m, "kind": "marker_pattern"})

    total = len(hardcoded) + templated_slots
    score = (templated_slots / total) if total else 1.0
    per_sub_counts: dict[str, int] = {}
    for h in hardcoded:
        per_sub_counts[h["subagent"]] = per_sub_counts.get(h["subagent"], 0) + 1
    heavily_hardcoded = [k for k, v in per_sub_counts.items() if v >= 3]
    return {
        "score": score,
        "hardcoded_literals": hardcoded,
        "templated_slots": templated_slots,
        "heavily_hardcoded_subagents": heavily_hardcoded,
    }


# ---------- 3. Use-Case Focus ----------

def use_case_focus(added_subs: dict, attrib: dict) -> dict[str, Any]:
    scored_subs = []
    no_scenarios = []
    multi_reason = []

    for name, scen_list in attrib.items():
        if not scen_list:
            no_scenarios.append(name)
            continue
        reasons = {_tag_to_reason((s.get("tags") or [""])[0])[1] for s in scen_list if s.get("tags")}
        single = len(reasons) == 1
        scored_subs.append((name, single))
        if not single:
            counts: dict[str, int] = {}
            for s in scen_list:
                for t in s.get("tags") or []:
                    r = _tag_to_reason(t)[1]
                    counts[r] = counts.get(r, 0) + 1
            multi_reason.append({"subagent": name, "reasons": counts})

    denom = len(scored_subs)
    numer = sum(1 for _, ok in scored_subs if ok)
    score = numer / denom if denom else 1.0
    return {
        "score": score,
        "n_single_reason": numer,
        "n_scored": denom,
        "multi_reason_subagents": multi_reason,
        "subagents_without_scenarios": no_scenarios,
    }


# ---------- 4. Subagent Substance ----------

def subagent_substance(added_subs: dict, config: dict) -> dict[str, Any]:
    min_instr = config["min_instruction_lines"]
    min_actions = config["min_real_actions"]
    passthrough = config["passthrough_signals"]
    action_verbs = set(config["action_verbs"])

    thin: list[dict] = []
    passthrough_subs: list[str] = []
    passed = 0

    for name, sub in added_subs.items():
        instr = sub.get("instructions", [])
        actions = sub.get("actions", [])
        real_actions = [a for a in actions if a["type"] in action_verbs and a["type"] not in HANDOFF_VERBS]
        body_lower = sub.get("body_text", "").lower()
        is_passthrough = any(sig in body_lower for sig in passthrough) and len(real_actions) == 0

        fails = []
        if len(instr) < min_instr:
            fails.append(f"instructions<{min_instr}")
        if len(real_actions) < min_actions:
            fails.append(f"real_actions<{min_actions}")
        if is_passthrough:
            fails.append("pure_passthrough")
            passthrough_subs.append(name)

        if not fails:
            passed += 1
        else:
            thin.append({
                "subagent": name,
                "fails": fails,
                "instruction_count": len(instr),
                "real_action_count": len(real_actions),
            })

    denom = len(added_subs)
    score = passed / denom if denom else 1.0
    return {
        "score": score,
        "n_passed": passed,
        "n_total": denom,
        "thin_subagents": thin,
        "passthrough_subagents": passthrough_subs,
    }


# ---------- 5. Action Gating ----------

SENSITIVE_VERBS = {
    "refund", "cancel", "unlink", "remove", "delete", "escalate",
    "update", "create", "set", "send",
}


def _has_precondition(action: dict, scenario_criterion: dict | None) -> bool:
    if action["type"] in SENSITIVE_VERBS:
        return True
    if scenario_criterion:
        desc = (scenario_criterion.get("description") or "").lower()
        if any(w in desc for w in ("verify", "confirm", "lookup", "eligib", "after")):
            return True
        if scenario_criterion.get("requireToolCall"):
            return True
    return False


def action_gating(added_subs: dict, attrib: dict) -> dict[str, Any]:
    actions_with_pre = 0
    gated = 0
    ungated: list[dict] = []
    sensitive_ungated: list[dict] = []

    for name, sub in added_subs.items():
        sub_scenarios = attrib.get(name, [])
        crit_descs = []
        for s in sub_scenarios:
            for c in s.get("criteria") or []:
                crit_descs.append(c)

        for a in sub.get("actions", []):
            crit = next((c for c in crit_descs if (c.get("toolName") or "").lower() == a["target"].lower()), None)
            if _has_precondition(a, crit):
                actions_with_pre += 1
                if a.get("gated"):
                    gated += 1
                else:
                    row = {"subagent": name, "action": a["id"], "verb": a["type"]}
                    ungated.append(row)
                    if a["type"] in SENSITIVE_VERBS:
                        sensitive_ungated.append(row)

    score = gated / actions_with_pre if actions_with_pre else 1.0
    return {
        "score": score,
        "n_with_precondition": actions_with_pre,
        "n_gated": gated,
        "ungated": ungated,
        "sensitive_ungated": sensitive_ungated,
    }
