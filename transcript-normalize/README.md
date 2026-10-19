# transcript-normalize

Normalize messy call/chat transcripts into the canonical shape consumed by downstream eval skills.

**Input:** a file or directory of raw transcripts (VTT, TXT, JSON, CSV).
**Output:** one JSON per transcript, shape:

```json
{"id": "<file-stem>", "turns": [{"role": "customer"|"agent"|"<name>", "text": "..."}]}
```

## Install

Zero runtime dependencies — stock Python 3.10+.

The skill lives at `~/.claude/skills/transcript-normalize/`. Claude Code loads it automatically.

## Usage

```bash
# Single file
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/call.vtt \
  --out ./conversations

# Whole directory (recursive, auto-pick parser by extension)
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/raw-transcripts \
  --out ./conversations

# With role rules
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/raw-transcripts \
  --out ./conversations \
  --role-map ./rules.yaml

# Force format (e.g., JSON stored with a .log extension)
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ./weird.log --out ./out --format json
```

## Supported inputs

| Ext | Format | Speaker extraction |
|---|---|---|
| `.vtt` | WebVTT (Zoom, Teams) | `"Name: text"` cue prefix. Same-speaker cues collapse. |
| `.txt` | Plain text | One turn per `"Speaker: text"` line; follow-up lines append. |
| `.json` | Already-structured | Passes through canonical; also accepts `{messages:[{speaker\|from\|author, text\|body\|content}]}`. |
| `.csv` | Spreadsheet export | Any `role\|speaker\|from\|author\|name` + `text\|message\|content\|body\|utterance` columns. |

## Role mapping

**Default:** phone-number speakers → `customer`, named speakers → `agent`.

**Override:** `--role-map rules.yaml`

```yaml
agents:
  - "Escarlen Castillo"           # exact (case-insensitive)
  - regex: "@aztec\\.com$"
  - regex: "^(Rep|Agent) "
customers:
  - regex: "^cust_[0-9]+$"
  - "Guest User"
```

Agents checked before customers. Unmatched speakers fall back to the default. See [`examples/rules.yaml`](examples/rules.yaml).

## Pairs with

- [`sla-contact-reason-eval`](../sla-contact-reason-eval/) — consumes the `conversations/*.json` this skill writes.

## Files

```
transcript-normalize/
  SKILL.md             # trigger phrases + usage summary (loaded by Claude Code)
  normalize.py         # the CLI entry point
  examples/
    rules.yaml         # example role map
```
