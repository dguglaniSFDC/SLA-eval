# Field Completeness Rate (P0 — static)

**Judge template:** none — pure structural check.
**Pass threshold:** 95%

## What's being measured

Across all required fields on all scenarios, the percentage that are actually populated — not technically present but empty.

Required fields (from `config.required_fields`):
`goal`, `persona`, `userContextFacts`, `agentContextFacts`, `sampleSeeds`, `criteria`, `tags`

## "Populated" definition

- Strings: non-null AND non-empty after `.strip()`.
- Objects: non-null AND has at least one key.
- Lists: non-empty.
- `sampleSeeds`: non-empty AND at least one seed has non-empty `values` (a list with one `{"values": {}}` is NOT populated).
- `persona`: non-null AND has `attributes` with ≥1 key.

## Formula

```
field_completeness = count(populated required fields) / (|scenarios| * |required_fields|)
```

## Report drill-down

- Per-field breakdown: which fields are most commonly empty.
- Per-scenario list of empty fields.
- Scenarios with ≥3 empty fields are flagged as **under-specified** (loud failure mode — likely to break training).
