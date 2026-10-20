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

HANDOFF_VERBS = {"handoff", "transition", "route", "delegate", "transfer"}

# Capture `transition to @subagent.<Name>` in subagent body text. The DSL writes
# these as `@utils.transition to @subagent.X`, so the preceding token isn't a
# verb at line start — a body_text regex is the only reliable way to find them.
_TRANSITION_TARGET_RE = re.compile(r"transition\s+to\s+@subagent\.([A-Za-z0-9_\-]+)", re.IGNORECASE)

# Subagent names that are legitimate destinations for an end-of-flow return.
# Returning to the router or escalating isn't a mid-flow handoff.
_ROUTER_NAMES = {"agent_router", "router"}


def use_case_ownership(added_subs: dict, scenarios: list[dict], flow_phases: dict, attrib: dict) -> dict[str, Any]:
    """Owned iff the attributed subagent handles the scenario without delegating to
    another non-router subagent. Phase coverage is intentionally not checked —
    `subagent_substance` and `instruction_substance` already measure whether the
    subagent has enough work in it; ownership only answers "did it stay here or
    punt."
    """
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

        body = sub.get("body_text", "") or ""
        targets = {t for t in _TRANSITION_TARGET_RE.findall(body)}
        mid_flow_targets = sorted(
            t for t in targets
            if t.lower() not in _ROUTER_NAMES and t != sub_name
        )

        if not mid_flow_targets:
            owned += 1
        else:
            unowned.append({
                "scenario": sid,
                "subagent": sub_name,
                "handoff_targets": mid_flow_targets,
            })

    score = owned / scored if scored else 0.0
    return {"score": score, "n_owned": owned, "n_scored": scored, "unowned": unowned}


# ---------- 2. Overfitting / Industry-tied (judge-backed, lives here only for its signature;
#                 the real implementation is in judge_metrics.overfitting). ----------


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

    thin: list[dict] = []
    passthrough_subs: list[str] = []
    passed = 0

    for name, sub in added_subs.items():
        instr = sub.get("instructions", [])
        actions = sub.get("actions", [])
        real_actions = [a for a in actions if a["type"] not in HANDOFF_VERBS]
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
    "update", "create", "send",
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
