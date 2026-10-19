# Coverage (P0)

**Judge template:** two-stage — `pointwise` (extraction, blind) then `grounded-match` (matching)
**Priority:** P0
**Pass threshold:** 85%

## What's being measured

Percentage of distinct intents found in the conversation corpus that have a matching reason in the taxonomy. This catches what the pipeline *missed*.

## Formula

```
coverage = count(reference_intent with match == yes) / count(reference_intents)
```

## Why two stages

A single-stage judge that sees both the transcript AND the taxonomy will anchor on the taxonomy and declare near-100% coverage. We force extraction to be **blind** so the reference intent set is corpus-grounded, not taxonomy-grounded.

## Stage A — Blind intent extraction

For each sampled transcript (`sampling.coverage_extract_n` from config, default 200):

- `<ITEM>` = the transcript
- `<RUBRIC>` = "Extract the single primary customer intent. Phrase it as `<verb> <object> [<qualifier>]`. Do not look up any taxonomy. Do not use category-style labels like 'Billing' — be specific about what the customer wanted."

Output override:
```json
{
  "intent_label": "<e.g. 'request credit for duplicate scan charge'>",
  "one_line_description": "<=20 words",
  "excerpt_turn_ids": [<turn indices supporting this>]
}
```

**Critical:** the taxonomy is NOT passed to this judge. Any leak kills coverage as a signal.

## Stage B — Cluster to reference intents

Pure code, no LLM:
- Embed `one_line_description` for each extracted intent.
- Agglomerative cluster at cosine threshold `clustering.intent_sim_threshold` (default 0.78).
- For each cluster, pick the medoid `intent_label` as the canonical reference intent.
- Expected output: 30–50 reference intents from a 200-transcript sample.

## Stage C — Match reference intents against the taxonomy

For each reference intent, run `grounded-match`:
- `<QUERY>` = reference intent label + description
- `<CANDIDATES>` = all taxonomy leaves
- `<CONSTRAINTS>` = "Match only to the deepest leaf whose description genuinely represents this intent. Prefer specific over generic. Reject surface-term matches."

## Report drill-down

List every reference intent with `match == no` — these are the **missing-from-taxonomy** findings. This is the real output; the percentage is secondary.

## Anchors (for Stage A extraction)

### Good extraction
Transcript: 15-turn call where customer complains about being charged twice for one scan, asks for refund.
Output: `{"intent_label": "request credit for duplicate scan charge", "one_line_description": "customer billed twice for a single scan, wants duplicate charge removed", "excerpt_turn_ids": [3, 7]}`

### Bad extraction (too generic)
Transcript: same as above.
Output: `{"intent_label": "billing issue"}` — too generic, loses the duplicate-charge signal. Reject at review.
