"""Single Claude caller — renders a judge template with a rubric + item, enforces JSON."""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

SKILL_ROOT = Path(__file__).resolve().parent.parent
JUDGES_DIR = SKILL_ROOT / "judges"
RUBRICS_DIR = SKILL_ROOT / "rubrics"


@dataclass
class JudgeCall:
    template: str   # "pointwise" | "pairwise" | "grounded-match"
    rubric: str    # file stem, e.g. "precision"
    inputs: dict[str, Any]


def _load(path: Path) -> str:
    return path.read_text()


def _render(template: str, bindings: dict[str, Any]) -> str:
    text = _load(JUDGES_DIR / f"{template}.md")
    for key, value in bindings.items():
        rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
        text = text.replace("{{" + key + "}}", rendered)
    return text


def _cache_key(call: JudgeCall) -> str:
    payload = json.dumps({"t": call.template, "r": call.rubric, "i": call.inputs}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    if start >= 0:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    return json.loads(text)


class Judge:
    def __init__(self, client: anthropic.Anthropic, model: str, cache_dir: Path | None):
        self.client = client
        self.model = model
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def call(self, call: JudgeCall) -> dict[str, Any]:
        key = _cache_key(call)
        cache_file = (self.cache_dir / f"{key}.json") if self.cache_dir else None
        if cache_file and cache_file.exists():
            return json.loads(cache_file.read_text())

        rubric_body = _load(RUBRICS_DIR / f"{call.rubric}.md")
        bindings = {"rubric_body": rubric_body, **call.inputs}
        prompt = _render(call.template, bindings)

        attempt = 0
        while True:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
                status = getattr(exc, "status_code", None)
                if attempt >= 8 or (status is not None and status not in (429, 500, 502, 503, 504, 529)):
                    raise
                sleep = min(60.0, (2 ** attempt) + random.random())
                time.sleep(sleep)
                attempt += 1
        raw = response.content[0].text
        try:
            parsed = _extract_json(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Judge returned non-JSON for {call.rubric}: {raw[:200]}") from exc

        if cache_file:
            cache_file.write_text(json.dumps(parsed, indent=2))
        return parsed
