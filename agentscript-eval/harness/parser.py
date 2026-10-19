"""Parse AgentScript (JSON, YAML, or raw DSL) into a stable IR.

IR shape:
  Script = {subagents: {name: Subagent}, raw: str, format: "json"|"yaml"|"dsl"}
  Subagent = {
    name: str,
    instructions: [str],       # non-trivial instruction lines
    actions: [Action],
    body_text: str,            # full raw body (for regex-only metrics)
    attrs: dict,               # whatever else parsed (available_when at top level, etc.)
  }
  Action = {
    id: str,                   # "<type>:<normalized_target>"
    type: str,                 # verb (run, lookup, verify, refund, ...)
    target: str,               # arg / tool name / destination
    gated: bool,
    gate_expr: str,
    raw: str,
  }

The parser is best-effort; failing to parse surfaces an empty Script with format="unknown"
so downstream metrics can SKIP cleanly instead of crashing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

INSTRUCTION_MIN_WORDS = 4
VERBS = {
    "run", "lookup", "fetch", "get", "search", "verify", "confirm", "validate",
    "create", "update", "cancel", "refund", "send", "schedule", "escalate",
    "unlink", "remove", "set", "notify", "log", "transition", "handoff",
    "route", "delegate", "transfer",
}


# ---------- IR helpers ----------

def _mk_action(verb: str, target: str, raw: str, gated: bool = False, gate_expr: str = "") -> dict:
    norm_target = _normalize_target(target)
    return {
        "id": f"{verb.lower()}:{norm_target}",
        "type": verb.lower(),
        "target": target,
        "gated": gated,
        "gate_expr": gate_expr,
        "raw": raw,
    }


def _normalize_target(target: str) -> str:
    t = (target or "").lower().strip()
    t = re.sub(r"inv-\d+", "inv-#", t)
    t = re.sub(r"ord-\d+", "ord-#", t)
    t = re.sub(r"case-\d+", "case-#", t)
    t = re.sub(r"tkt-\d+", "tkt-#", t)
    t = re.sub(r"\$\d+(?:\.\d{2})?", "$#", t)
    t = re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", t)
    t = re.sub(r"\s+", "_", t)
    return t


# ---------- JSON parser ----------

def _parse_json(data: Any) -> dict | None:
    if not isinstance(data, (dict, list)):
        return None

    subagents_src = None
    if isinstance(data, dict):
        for key in ("subagents", "agents", "sub_agents"):
            if key in data:
                subagents_src = data[key]
                break
        if subagents_src is None and _looks_like_single_subagent(data):
            subagents_src = [data]
    if subagents_src is None and isinstance(data, list):
        subagents_src = data
    if subagents_src is None:
        return None

    out: dict[str, dict] = {}
    if isinstance(subagents_src, dict):
        iterable = [{"name": k, **v} if isinstance(v, dict) else {"name": k, "body": str(v)}
                    for k, v in subagents_src.items()]
    else:
        iterable = subagents_src

    for sub in iterable:
        if not isinstance(sub, dict):
            continue
        name = sub.get("name") or sub.get("id")
        if not name:
            continue
        instructions = _extract_instructions(sub)
        actions = _extract_actions_json(sub)
        body_text = _collect_body_text(sub)
        attrs = {k: v for k, v in sub.items() if k not in ("name", "id", "actions", "steps", "flow", "instructions", "prompt", "system")}
        out[name] = {
            "name": name,
            "instructions": instructions,
            "actions": actions,
            "body_text": body_text,
            "attrs": attrs,
        }
    return out


def _looks_like_single_subagent(d: dict) -> bool:
    return any(k in d for k in ("instructions", "actions", "steps", "flow"))


def _extract_instructions(sub: dict) -> list[str]:
    text = ""
    for key in ("instructions", "prompt", "system", "description"):
        v = sub.get(key)
        if isinstance(v, str):
            text += "\n" + v
        elif isinstance(v, list):
            text += "\n" + "\n".join(str(x) for x in v)
    lines = []
    for ln in text.splitlines():
        clean = ln.strip().lstrip("-*•").strip()
        if len(clean.split()) >= INSTRUCTION_MIN_WORDS:
            lines.append(clean)
    return lines


def _extract_actions_json(sub: dict) -> list[dict]:
    actions = []
    for key in ("actions", "steps", "flow", "body"):
        v = sub.get(key)
        if isinstance(v, list):
            for item in v:
                a = _coerce_action(item)
                if a:
                    actions.append(a)
    return actions


def _coerce_action(item: Any) -> dict | None:
    if isinstance(item, str):
        return _parse_action_line(item)
    if not isinstance(item, dict):
        return None
    verb = (
        item.get("type") or item.get("action") or item.get("verb")
        or item.get("kind") or ""
    )
    target = (
        item.get("target") or item.get("tool") or item.get("name")
        or item.get("to") or item.get("args", "") or ""
    )
    if isinstance(target, dict):
        target = target.get("name") or json.dumps(target, sort_keys=True)
    gate_expr = item.get("available_when") or item.get("requires") or item.get("guard") or item.get("precondition") or ""
    if isinstance(gate_expr, list):
        gate_expr = ", ".join(str(x) for x in gate_expr)
    verb = str(verb).lower().strip()
    if not verb:
        return None
    return _mk_action(verb, str(target), raw=json.dumps(item, sort_keys=True), gated=bool(gate_expr), gate_expr=str(gate_expr))


def _collect_body_text(sub: dict) -> str:
    chunks = []
    for v in sub.values():
        if isinstance(v, str):
            chunks.append(v)
        else:
            chunks.append(json.dumps(v, sort_keys=True))
    return "\n".join(chunks)


# ---------- DSL regex fallback ----------

ACTION_LINE_RE = re.compile(
    r"^\s*(?P<verb>" + "|".join(sorted(VERBS, key=len, reverse=True)) + r")"
    r"(?:\s+(?P<target>[^\s(][^\n]*?))?"
    r"(?:\s+(?:when|if)\s+(?P<gate>.+))?$",
    re.IGNORECASE,
)
SUBAGENT_HEADER_RE = re.compile(r"^\s*(?:subagent|agent|sub_agent)\s+(?P<name>[A-Za-z0-9_\-]+)", re.IGNORECASE)


def _parse_action_line(line: str) -> dict | None:
    m = ACTION_LINE_RE.match(line.strip())
    if not m:
        return None
    verb = m.group("verb").lower()
    target = (m.group("target") or "").strip().strip("()\"'")
    gate = (m.group("gate") or "").strip()
    return _mk_action(verb, target, raw=line.strip(), gated=bool(gate), gate_expr=gate)


def _parse_dsl(text: str) -> dict:
    out: dict[str, dict] = {}
    current: dict | None = None
    for line in text.splitlines():
        header = SUBAGENT_HEADER_RE.match(line)
        if header:
            name = header.group("name")
            current = {
                "name": name,
                "instructions": [],
                "actions": [],
                "body_text": "",
                "attrs": {},
            }
            out[name] = current
            continue
        if current is None:
            continue
        current["body_text"] += line + "\n"
        action = _parse_action_line(line)
        if action:
            current["actions"].append(action)
            continue
        clean = line.strip().lstrip("-*•").strip()
        if len(clean.split()) >= INSTRUCTION_MIN_WORDS:
            current["instructions"].append(clean)
    return out


# ---------- YAML (dependency-free mini-parser) ----------

def _try_load_yaml(text: str) -> Any | None:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _mini_yaml(text)
    except Exception:
        return None


def _mini_yaml(text: str) -> Any:
    """Tiny YAML subset: top-level `subagents:` with nested dicts/lists of scalars."""
    try:
        return json.loads(text)
    except Exception:
        pass
    return None


# ---------- Entry point ----------

def parse_script(path: Path) -> dict:
    text = path.read_text()
    data = None
    fmt = "unknown"

    try:
        data = json.loads(text)
        fmt = "json"
    except json.JSONDecodeError:
        yaml_data = _try_load_yaml(text)
        if yaml_data is not None:
            data = yaml_data
            fmt = "yaml"

    subagents = None
    if data is not None:
        subagents = _parse_json(data)

    if not subagents:
        subagents = _parse_dsl(text)
        if subagents:
            fmt = "dsl"

    return {
        "subagents": subagents or {},
        "raw": text,
        "format": fmt,
        "path": str(path),
    }
