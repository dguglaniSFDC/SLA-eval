---
name: transcript-normalize
description: Normalize messy call/chat transcripts (VTT, TXT, JSON, CSV) into the canonical {id, turns:[{role, text}]} shape consumed by sla-contact-reason-eval and other eval skills. Supports a rules file to say which speaker patterns are the agent and which are the customer. Use when the user has raw transcripts in heterogeneous formats and asks to "normalize", "prep transcripts", or "convert transcripts for eval".
---

# Transcript Normalize

Converts a directory (or single file) of raw transcripts into the canonical shape:

```json
{"id": "<file-stem>", "turns": [{"role": "customer"|"agent"|"<name>", "text": "..."}]}
```

One JSON file per conversation, written to `--out`.

## Supported inputs (auto-detected by extension)

| Ext | Format | Speaker extraction |
|---|---|---|
| `.vtt` | WebVTT (Zoom, Teams exports) | `"Name: text"` cue prefix. Consecutive same-speaker cues collapse. |
| `.txt` | Plain text | One turn per `"Speaker: text"` line; follow-up lines append to current turn. |
| `.json` | Already-structured | Passes through if canonical; also accepts `{messages:[{speaker\|from\|author, text\|body\|content}]}`. |
| `.csv` | Spreadsheet export | Any columns matching `role\|speaker\|from\|author\|name` + `text\|message\|content\|body\|utterance`. |

## Role mapping

Default: phone-number speakers → `customer`, named speakers → `agent`. This matches the typical Zoom VTT (e.g., `+19707122432` dialed in, `Escarlen Castillo` is the rep).

Override with `--role-map rules.yaml`:

```yaml
agents:
  - "Escarlen Castillo"          # exact name match
  - regex: "@aztec\\.com$"        # anything with this email suffix
  - regex: "^(Rep|Agent) "        # labeled rows from a transcription vendor
customers:
  - regex: "^cust_[0-9]+$"        # anonymized ids
  - "Guest User"
```

Rules are tried in order (agents first, then customers). Unmatched speakers fall back to the default (phone → customer, name → agent). To keep raw names in the output instead of collapsing, just leave the file off — but downstream judges read cleaner reports when roles are normalized.

## Usage

```bash
# Single file
python normalize.py --input ~/Downloads/call.vtt --out ./runs/aztec/conversations

# Whole directory, recursive, auto-pick parsers
python normalize.py --input ~/Downloads/OneDrive_1_6-18-2026 --out ./runs/aztec/conversations

# With role rules
python normalize.py --input ~/Downloads/transcripts --out ./runs/aztec/conversations --role-map rules.yaml

# Force format (e.g., JSON file saved with .log extension)
python normalize.py --input ./weird.log --out ./out --format json
```

Output: one `<stem>.json` per transcript in `--out`, plus a stderr summary of skipped files.

## Trigger phrases

Invoke this skill when the user says:
- "normalize these transcripts"
- "prep transcripts for the eval"
- "convert the VTTs" / "convert this transcripts folder"
- "map phone numbers to customer"

## Pairs with

- [`sla-contact-reason-eval`](../sla-contact-reason-eval/SKILL.md) — consumes `conversations/*.json` in exactly this shape.
