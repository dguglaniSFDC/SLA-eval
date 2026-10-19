"""Normalize messy transcripts into the canonical shape the eval expects.

Canonical shape (one JSON per conversation):
    {"id": "<stem>", "turns": [{"role": "<speaker>", "text": "..."}]}

Supported inputs (auto-detected by extension; override with --format):
    .vtt       WebVTT (Zoom-style). Speaker inferred from "Speaker: text" cue prefix.
    .txt       Plain text. One speaker turn per line in the form "Speaker: text".
    .json      Already-structured — passes through if it has {turns:[{role,text}]},
               otherwise accepts {messages:[{speaker|from|author, text|body|content}]}.
    .csv       Columns include speaker|role|from and text|message|content; one row per turn.

Role mapping:
    Zoom-style default — phone-number speakers become "customer", named speakers
    become "agent". Override with --role-map rules.yaml for explicit control:
        agents:
          - "Escarlen Castillo"
          - regex: "@aztec\\.com$"
        customers:
          - regex: "^cust_"
    Unmatched speakers fall back to the phone/name default.

Usage:
    python harness/normalize.py --input ~/Downloads/OneDrive_1_6-18-2026 --out ./runs/aztec/conversations
    python harness/normalize.py --input foo.vtt --out ./runs/aztec/conversations
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Turn:
    role: str
    text: str


# ---------- VTT ----------

VTT_CUE_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}")
SPEAKER_PREFIX_RE = re.compile(r"^([^:]{1,80}?):\s*(.*)$")


def parse_vtt(text: str) -> list[Turn]:
    lines = text.splitlines()
    i = 0
    turns: list[Turn] = []
    while i < len(lines):
        line = lines[i].strip()
        if VTT_CUE_RE.match(line):
            i += 1
            payload: list[str] = []
            while i < len(lines) and lines[i].strip() != "":
                payload.append(lines[i].strip())
                i += 1
            if payload:
                joined = " ".join(payload)
                m = SPEAKER_PREFIX_RE.match(joined)
                if m:
                    turns.append(Turn(role=m.group(1).strip(), text=m.group(2).strip()))
                else:
                    turns.append(Turn(role="unknown", text=joined))
        i += 1
    return _collapse(turns)


# ---------- Plain text ----------

def parse_txt(text: str) -> list[Turn]:
    turns: list[Turn] = []
    current: Turn | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = SPEAKER_PREFIX_RE.match(line)
        if m and len(m.group(1).split()) <= 6:
            if current:
                turns.append(current)
            current = Turn(role=m.group(1).strip(), text=m.group(2).strip())
        elif current:
            current.text = (current.text + " " + line.strip()).strip()
        else:
            current = Turn(role="unknown", text=line.strip())
    if current:
        turns.append(current)
    return _collapse(turns)


# ---------- JSON ----------

def parse_json(text: str) -> list[Turn]:
    data = json.loads(text)
    if isinstance(data, dict) and "turns" in data and data["turns"]:
        first = data["turns"][0]
        if "role" in first and "text" in first:
            return [Turn(role=t["role"], text=t["text"]) for t in data["turns"]]
    messages = (
        data.get("messages") if isinstance(data, dict) else None
    ) or (data if isinstance(data, list) else [])
    turns: list[Turn] = []
    for m in messages:
        role = m.get("role") or m.get("speaker") or m.get("from") or m.get("author") or "unknown"
        text = m.get("text") or m.get("body") or m.get("content") or m.get("message") or ""
        if text:
            turns.append(Turn(role=str(role), text=str(text)))
    return _collapse(turns)


# ---------- CSV ----------

SPEAKER_COLS = ("role", "speaker", "from", "author", "name")
TEXT_COLS = ("text", "message", "content", "body", "utterance")


def parse_csv(text: str) -> list[Turn]:
    reader = csv.DictReader(text.splitlines())
    speaker_col = text_col = None
    for col in reader.fieldnames or []:
        low = col.lower().strip()
        if speaker_col is None and low in SPEAKER_COLS:
            speaker_col = col
        if text_col is None and low in TEXT_COLS:
            text_col = col
    if not speaker_col or not text_col:
        raise ValueError(
            f"CSV must have one of {SPEAKER_COLS} + one of {TEXT_COLS}; "
            f"got columns {reader.fieldnames}"
        )
    turns = [
        Turn(role=str(row[speaker_col]).strip(), text=str(row[text_col]).strip())
        for row in reader
        if row.get(text_col)
    ]
    return _collapse(turns)


# ---------- Shared ----------

def _collapse(turns: list[Turn]) -> list[Turn]:
    """Merge consecutive turns by the same speaker — VTT splits one utterance into many cues."""
    out: list[Turn] = []
    for t in turns:
        if out and out[-1].role == t.role:
            out[-1].text = (out[-1].text + " " + t.text).strip()
        else:
            out.append(Turn(role=t.role, text=t.text))
    return out


PHONE_RE = re.compile(r"^\+?\d[\d\s\-().]{7,}$")


def _default_role(name: str) -> str:
    """Zoom-style default: phone-number speakers are the customer, named speakers are the agent."""
    n = name.strip()
    if not n or n.lower() == "unknown":
        return n or "unknown"
    if PHONE_RE.match(n):
        return "customer"
    if any(ch.isalpha() for ch in n):
        return "agent"
    return n


def _compile_role_map(rules: dict | None):
    def match(name: str, patterns) -> bool:
        for p in patterns or []:
            if isinstance(p, str) and p.lower() == name.lower():
                return True
            if isinstance(p, dict) and "regex" in p and re.search(p["regex"], name):
                return True
        return False
    agents = (rules or {}).get("agents") or []
    customers = (rules or {}).get("customers") or []

    def apply(name: str) -> str:
        if match(name, agents):
            return "agent"
        if match(name, customers):
            return "customer"
        return _default_role(name)
    return apply


PARSERS = {".vtt": parse_vtt, ".txt": parse_txt, ".json": parse_json, ".csv": parse_csv}


def _load_rules(path: Path) -> dict:
    """Load role rules from YAML or JSON. Tries pyyaml, falls back to a tiny parser.

    Only supports the shape:
        agents:
          - "string"
          - regex: "pattern"
        customers:
          - "string"
    which covers every documented example without pulling in pyyaml.
    """
    text = path.read_text()
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        return _parse_mini_yaml(text)


def _parse_mini_yaml(text: str) -> dict:
    rules: dict = {}
    current: str | None = None
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        if not raw.startswith(" ") and stripped.endswith(":"):
            current = stripped[:-1].strip()
            rules[current] = []
            continue
        if current is None:
            continue
        item = stripped.strip()
        if not item.startswith("- "):
            continue
        value = item[2:].strip()
        if value.startswith("regex:"):
            pattern = value.split(":", 1)[1].strip().strip("'\"")
            rules[current].append({"regex": pattern})
        else:
            rules[current].append(value.strip("'\""))
    return rules


def normalize_file(path: Path, fmt: str | None, map_role) -> dict:
    ext = fmt or path.suffix.lower()
    if not ext.startswith("."):
        ext = "." + ext
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"Unsupported format: {ext} (supported: {list(PARSERS)})")
    turns = parser(path.read_text(encoding="utf-8", errors="replace"))
    return {
        "id": path.stem,
        "turns": [{"role": map_role(t.role), "text": t.text} for t in turns if t.text.strip()],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="File or directory of raw transcripts")
    parser.add_argument("--out", required=True, help="Output directory for canonical JSON")
    parser.add_argument("--format", help="Force a format (vtt|txt|json|csv). Default: by extension")
    parser.add_argument("--role-map", help="YAML with agents/customers lists for role normalization")
    parser.add_argument("--glob", default="**/*", help="Glob when --input is a directory")
    args = parser.parse_args()

    rules = _load_rules(Path(args.role_map)) if args.role_map else None
    map_role = _compile_role_map(rules)

    in_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [in_path] if in_path.is_file() else [
        p for p in in_path.glob(args.glob)
        if p.is_file() and p.suffix.lower() in PARSERS
    ]
    if not files:
        print(f"No supported files in {in_path} (looked for {list(PARSERS)})", file=sys.stderr)
        sys.exit(1)

    ok, bad = 0, []
    for f in files:
        try:
            conv = normalize_file(f, args.format, map_role)
            if not conv["turns"]:
                bad.append((f, "no turns extracted"))
                continue
            (out_dir / f"{conv['id']}.json").write_text(json.dumps(conv, indent=2))
            ok += 1
        except Exception as e:
            bad.append((f, str(e)))

    print(f"Wrote {ok} conversations to {out_dir}")
    if bad:
        print(f"Skipped {len(bad)}:")
        for f, why in bad[:10]:
            print(f"  - {f.name}: {why}")
        if len(bad) > 10:
            print(f"  ... and {len(bad) - 10} more")


if __name__ == "__main__":
    main()
