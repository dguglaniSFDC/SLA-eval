"""Compute what training added between before and after AgentScripts.

Returns:
  Diff = {
    added_subagents: {name: Subagent},
    removed_subagents: {name: Subagent},
    modified_subagents: {name: {before, after, added_actions, added_instructions}},
    unchanged_subagents: [name],
  }

A subagent is "added" if the name is absent in before.
"Modified" if actions or instruction set differs. "Unchanged" otherwise.
"""
from __future__ import annotations

from typing import Any


def _action_ids(sub: dict) -> set[str]:
    return {a["id"] for a in sub.get("actions", [])}


def _instruction_set(sub: dict) -> set[str]:
    return {ln.strip().lower() for ln in sub.get("instructions", []) if ln.strip()}


def compute_diff(before: dict, after: dict) -> dict[str, Any]:
    b_subs = before.get("subagents", {})
    a_subs = after.get("subagents", {})

    added = {}
    removed = {}
    modified = {}
    unchanged = []

    for name, sub in a_subs.items():
        if name not in b_subs:
            added[name] = sub
            continue
        b_sub = b_subs[name]
        b_actions = _action_ids(b_sub)
        a_actions = _action_ids(sub)
        b_instr = _instruction_set(b_sub)
        a_instr = _instruction_set(sub)
        added_actions = a_actions - b_actions
        added_instructions = a_instr - b_instr
        if added_actions or added_instructions:
            modified[name] = {
                "before": b_sub,
                "after": sub,
                "added_action_ids": sorted(added_actions),
                "added_instructions": sorted(added_instructions),
            }
        else:
            unchanged.append(name)

    for name, sub in b_subs.items():
        if name not in a_subs:
            removed[name] = sub

    return {
        "added_subagents": added,
        "removed_subagents": removed,
        "modified_subagents": modified,
        "unchanged_subagents": unchanged,
    }


def effective_added_subagents(diff: dict) -> dict:
    """Union of fully-added subagents + modified subagents (presented as the delta)."""
    out = dict(diff.get("added_subagents", {}))
    for name, m in diff.get("modified_subagents", {}).items():
        after_sub = m["after"]
        added_action_ids = set(m["added_action_ids"])
        added_instr = set(m["added_instructions"])
        delta_sub = {
            "name": name,
            "instructions": [ln for ln in after_sub["instructions"] if ln.strip().lower() in added_instr],
            "actions": [a for a in after_sub["actions"] if a["id"] in added_action_ids],
            "body_text": after_sub.get("body_text", ""),
            "attrs": after_sub.get("attrs", {}),
            "_modified": True,
            "_full_after": after_sub,
        }
        out[name] = delta_sub
    return out
