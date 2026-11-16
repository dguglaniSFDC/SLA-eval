"""Static metrics — tag coverage, evaluability, verification coverage, criteria/field completeness."""
from __future__ import annotations

import re
from statistics import mean
from typing import Any

OUTCOME_VERBS = (
    "confirm", "verify", "resolve", "send", "process", "create", "update",
    "remove", "escalate", "provide", "explain", "communicate", "notify",
    "offer", "guide", "share", "schedule", "collect", "cancel", "refund",
)
SHARE_SIGNALS = (
    "provide", "communicate", "share", "explain", "offer", "inform", "notify",
    "quote", "give", "state",
)
CONDITIONAL_SIGNALS = (
    r"\bif\b", r"\bwhen\b", r"\bshould the\b", r"\bin case\b", r"\bunless\b",
)
POST_CHAT_SIGNALS = (
    "after the chat", "follow-up email", "once the technician arrives", "after the call",
    "later today", "tomorrow", "end of day", "eventually", "once resolved",
)

TAG_SEP = "::"


# ---------- helpers ----------

def _text_blob(criterion: dict[str, Any]) -> str:
    return f"{criterion.get('name', '')} {criterion.get('description', '')}".lower()


def _scenario_blob(scenario: dict[str, Any]) -> str:
    parts = [scenario.get("goal") or ""]
    for c in scenario.get("criteria") or []:
        parts.append(_text_blob(c))
    return " ".join(parts).lower()


def _matches_any(text: str, patterns: list[str]) -> str | None:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return p
    return None


def is_sensitive(scenario: dict[str, Any], sensitive_patterns: list[str]) -> str | None:
    return _matches_any(_scenario_blob(scenario), sensitive_patterns)


def is_verification_criterion(criterion: dict[str, Any], verification_patterns: list[str]) -> bool:
    return _matches_any(_text_blob(criterion), verification_patterns) is not None


def normalize_tag(tag: str) -> tuple[str, str]:
    if TAG_SEP in tag:
        cat, name = tag.split(TAG_SEP, 1)
        return cat.strip().lower(), name.strip().lower()
    return "", tag.strip().lower()


def reason_to_tag(reason: dict[str, Any]) -> tuple[str, str]:
    cat = (reason.get("category") or "").strip().lower()
    name = (reason.get("name") or reason.get("contact_reason") or "").strip().lower()
    return cat, name


def tag_matches_reason(tag: str, reason: dict[str, Any]) -> bool:
    tag_cat, tag_name = normalize_tag(tag)
    r_cat, r_name = reason_to_tag(reason)
    if tag_cat and r_cat:
        if tag_cat == r_cat and tag_name == r_name:
            return True
    return tag_name == r_name


# ---------- 1. Tag Coverage ----------

def _is_automatable(reason: dict) -> bool:
    """A reason is in-scope for Tag coverage if its automation score is > 0 (or missing).

    When the harness is run with --automation-scores, each reason gets an
    `automation_potential_score` / `automation_potential_band` field. Reasons with
    band=="Not automatable" OR score==0 are dropped from the denominator — SLA
    scenarios target automation, so missing scenarios on non-automatable reasons
    (e.g. pricing lookups, call transfers, human-dispatch RMAs) isn't a gap.

    Reasons lacking an annotation (no scores file provided) default to automatable
    so Tag coverage behaves exactly as before.
    """
    if "automation_potential_band" in reason:
        band = (reason.get("automation_potential_band") or "").lower()
        if band == "not automatable":
            return False
    if "automation_potential_score" in reason:
        score = reason.get("automation_potential_score")
        if score is not None and score == 0:
            return False
    return True


def tag_coverage(scenarios: list[dict], reasons: list[dict]) -> dict[str, Any]:
    tag_counts: dict[str, int] = {}
    for s in scenarios:
        for t in s.get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    # Filter to parent-less leaves when parent_id is present (parents aren't
    # tagged against). Then filter to automatable reasons when annotated.
    has_parent_info = any("parent_id" in r for r in reasons)
    if has_parent_info:
        scorable = [r for r in reasons if r.get("parent_id")]
    else:
        scorable = list(reasons)

    has_automation_info = any("automation_potential_band" in r or "automation_potential_score" in r
                              for r in scorable)
    automatable = [r for r in scorable if _is_automatable(r)]
    excluded_not_automatable = [r for r in scorable if not _is_automatable(r)]

    denom_reasons = automatable if has_automation_info else scorable

    hit = []
    miss = []
    reason_counts: dict[str, int] = {}
    for r in denom_reasons:
        name = r.get("name") or r.get("contact_reason") or ""
        count = sum(c for t, c in tag_counts.items() if tag_matches_reason(t, r))
        reason_counts[name] = count
        (hit if count > 0 else miss).append(r)

    # Also detect scenarios tagged against non-automatable reasons (wasted coverage).
    tagged_but_not_automatable = []
    if has_automation_info:
        for r in excluded_not_automatable:
            if any(tag_matches_reason(t, r) for t in tag_counts):
                tagged_but_not_automatable.append(
                    {"category": r.get("category"), "name": r.get("name"),
                     "automation_band": r.get("automation_potential_band")}
                )

    med = sorted(reason_counts.values())[len(reason_counts) // 2] if reason_counts else 0
    oversampled = [n for n, c in reason_counts.items() if med and c > 5 * med]

    return {
        "score": len(hit) / len(denom_reasons) if denom_reasons else 0.0,
        "n_covered": len(hit),
        "n_total": len(denom_reasons),
        "denominator_filter": "automatable_leaves" if has_automation_info else (
            "leaves" if has_parent_info else "all"
        ),
        "n_excluded_not_automatable": len(excluded_not_automatable) if has_automation_info else 0,
        "n_excluded_parents": len(reasons) - len(scorable) if has_parent_info else 0,
        "uncovered": [
            {
                "category": r.get("category"),
                "name": r.get("name"),
                "automation_band": r.get("automation_potential_band"),
                "automation_score": r.get("automation_potential_score"),
                "volume": r.get("volume"),
            }
            for r in miss
        ],
        "oversampled": oversampled,
        "tagged_non_automatable": tagged_but_not_automatable,
    }


# ---------- 2. Evaluability (5 block rules + warnings) ----------

def _iter_tool_defs(scenario: dict, criterion: dict | None = None):
    """Yield tool definitions from either shape:
       - scenario-level: scenario.suggestedToolcalls[*].tool  (nested)
       - criterion-level: criterion.suggestedToolcalls[*]      (flat)
    """
    if criterion is not None:
        for stc in criterion.get("suggestedToolcalls") or []:
            if isinstance(stc, dict):
                yield stc.get("tool") or stc
    for stc in scenario.get("suggestedToolcalls") or []:
        if isinstance(stc, dict):
            yield stc.get("tool") or stc


def _has_tool_defined(scenario: dict, tool_name: str, criterion: dict | None = None) -> bool:
    for tool in _iter_tool_defs(scenario, criterion):
        if (tool.get("name") or "").lower() == (tool_name or "").lower():
            return True
    return False


def _any_tool_defined(scenario: dict, criterion: dict | None = None) -> bool:
    if criterion is not None and (criterion.get("suggestedToolcalls") or []):
        return True
    return bool(scenario.get("suggestedToolcalls"))


def _agent_facts_cover(scenario: dict, text: str) -> bool:
    keys = list((scenario.get("agentContextFacts") or {}).keys())
    if not keys:
        return False
    text_l = text.lower()
    for k in keys:
        if k.lower() in text_l or _tokens_overlap(k, text_l):
            return True
    return False


def _tokens_overlap(key: str, text: str) -> bool:
    key_tokens = [t for t in re.split(r"[^a-z]+", key.lower()) if len(t) > 3]
    return any(t in text for t in key_tokens)


def _condition_disambiguated(scenario: dict, text: str) -> bool:
    merged = {
        **(scenario.get("userContextFacts") or {}),
        **(scenario.get("agentContextFacts") or {}),
    }
    for seed in scenario.get("sampleSeeds") or []:
        merged.update(seed.get("values") or {})
    if not merged:
        return False
    for k in merged:
        if k.lower() in text or _tokens_overlap(k, text):
            return True
    return False


def _tool_field_warnings(scenario: dict) -> list[dict]:
    warnings = []
    merged_keys = [
        *((scenario.get("userContextFacts") or {}).keys()),
        *((scenario.get("agentContextFacts") or {}).keys()),
    ]
    merged_keys_l = [k.lower() for k in merged_keys]
    tools = list(_iter_tool_defs(scenario))
    for c in scenario.get("criteria") or []:
        tools.extend(_iter_tool_defs({}, c))
    for tool in tools:
        name = tool.get("name", "")
        for schema_key in ("inputSchema", "outputSchema"):
            schema = tool.get(schema_key) or {}
            props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
            for field in props:
                field_l = field.lower()
                if any(field_l in k or k in field_l for k in merged_keys_l):
                    continue
                warnings.append({"tool": name, "field": field, "where": schema_key})
    return warnings


def evaluability(scenarios: list[dict]) -> dict[str, Any]:
    total_criteria = 0
    blocked_criteria = 0
    blocks = []
    warnings = []
    unanchored = []

    for s in scenarios:
        sid = s.get("id") or s.get("scenarioId") or "<unknown>"
        criteria = s.get("criteria") or []

        rule_e = (
            not (s.get("goal") or "").strip()
            or not s.get("persona")
            or not (s.get("userContextFacts") or {})
        )
        if rule_e:
            unanchored.append(sid)

        for c in criteria:
            total_criteria += 1
            desc = c.get("description", "")
            name = c.get("name", "")
            fired: list[str] = []
            soft: list[str] = []

            if rule_e:
                soft.append("e_empty_anchors")

            if c.get("requireToolCall"):
                tool_name = (c.get("toolName") or "").strip()
                if tool_name:
                    if not _has_tool_defined(s, tool_name, c):
                        fired.append("a_missing_tool_definition")
                elif not _any_tool_defined(s, c):
                    fired.append("a_missing_tool_definition")

            if any(sig in desc.lower() for sig in SHARE_SIGNALS):
                if not _agent_facts_cover(s, desc):
                    soft.append("b_shares_undocumented_info")

            if any(re.search(p, desc, flags=re.IGNORECASE) for p in CONDITIONAL_SIGNALS):
                if not _condition_disambiguated(s, desc.lower()):
                    fired.append("c_unresolved_conditional")

            if any(sig in desc.lower() for sig in POST_CHAT_SIGNALS):
                fired.append("d_post_chat_event")

            if fired:
                blocked_criteria += 1
                blocks.append({"scenario": sid, "criterion": name, "rules": fired})
            if soft:
                warnings.append({"scenario": sid, "criterion": name, "rules": soft})

        warnings.extend([{"scenario": sid, **w} for w in _tool_field_warnings(s)])

    passable = total_criteria - blocked_criteria
    score = passable / total_criteria if total_criteria else 0.0
    return {
        "score": score,
        "n_passable": passable,
        "n_total": total_criteria,
        "blocked": blocks,
        "warnings": warnings,
        "unanchored_scenarios": unanchored,
    }


# ---------- 3. Verification Coverage ----------

def verification_coverage(
    scenarios: list[dict], sensitive_patterns: list[str], verification_patterns: list[str]
) -> dict[str, Any]:
    sensitive = []
    ungated = []
    for s in scenarios:
        hit = is_sensitive(s, sensitive_patterns)
        if not hit:
            continue
        sensitive.append(s)
        has_v = any(is_verification_criterion(c, verification_patterns) for c in s.get("criteria") or [])
        if not has_v:
            ungated.append({
                "scenario": s.get("id") or "<unknown>",
                "matched_sensitive_keyword": hit,
            })

    denom = len(sensitive)
    score = (denom - len(ungated)) / denom if denom else 1.0
    return {
        "score": score,
        "n_sensitive": denom,
        "n_gated": denom - len(ungated),
        "ungated": ungated,
    }


# ---------- 4. Criteria Completeness ----------

def criteria_completeness(
    scenarios: list[dict], sensitive_patterns: list[str], verification_patterns: list[str]
) -> dict[str, Any]:
    scenario_scores: list[float] = []
    weak = []
    fail_tool = fail_outcome = fail_verif = 0

    for s in scenarios:
        sid = s.get("id") or "<unknown>"
        criteria = s.get("criteria") or []
        if not criteria:
            continue
        sensitive = bool(is_sensitive(s, sensitive_patterns))
        has_verif = any(is_verification_criterion(c, verification_patterns) for c in criteria)
        verif_ok = (not sensitive) or has_verif
        if sensitive and not has_verif:
            fail_verif += 1

        per_criterion = []
        for c in criteria:
            if not c.get("requireToolCall"):
                tool_ok = True
            else:
                tn = (c.get("toolName") or "").strip()
                tool_ok = _has_tool_defined(s, tn, c) if tn else _any_tool_defined(s, c)
            outcome_ok = any(v in _text_blob(c) for v in OUTCOME_VERBS)
            if not tool_ok:
                fail_tool += 1
            if not outcome_ok:
                fail_outcome += 1
            per_criterion.append(int(tool_ok) + int(outcome_ok) + int(verif_ok))

        avg = mean(per_criterion) if per_criterion else 0.0
        scenario_scores.append(avg)
        if avg < 2.0:
            weak.append({"scenario": sid, "avg": round(avg, 2)})

    score = (mean(scenario_scores) / 3) if scenario_scores else 0.0
    return {
        "score": score,
        "weak_scenarios": weak,
        "n_fail_tool_invoked": fail_tool,
        "n_fail_outcome_stated": fail_outcome,
        "n_fail_verification_honored": fail_verif,
    }


# ---------- 5. Field Completeness ----------

def _is_populated(scenario: dict, field: str) -> bool:
    val = scenario.get(field)
    if val is None:
        return False
    if field == "sampleSeeds":
        return isinstance(val, list) and any((s.get("values") or {}) for s in val)
    if field == "persona":
        return isinstance(val, dict) and bool((val.get("attributes") or {}))
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (dict,)):
        return bool(val)
    if isinstance(val, list):
        return bool(val)
    return True


def field_completeness(scenarios: list[dict], required_fields: list[str]) -> dict[str, Any]:
    total = len(scenarios) * len(required_fields)
    populated = 0
    per_field_missing: dict[str, int] = {f: 0 for f in required_fields}
    per_scenario_missing: list[dict] = []
    under_specified: list[str] = []

    for s in scenarios:
        missing = []
        for f in required_fields:
            if _is_populated(s, f):
                populated += 1
            else:
                per_field_missing[f] += 1
                missing.append(f)
        if missing:
            per_scenario_missing.append({"scenario": s.get("id") or "<unknown>", "missing": missing})
        if len(missing) >= 3:
            under_specified.append(s.get("id") or "<unknown>")

    return {
        "score": populated / total if total else 1.0,
        "per_field_missing": per_field_missing,
        "per_scenario_missing": per_scenario_missing,
        "under_specified": under_specified,
    }
