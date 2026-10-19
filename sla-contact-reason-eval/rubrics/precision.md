# Precision (P0)

**Judge template:** `grounded-match` (variant — see below)
**Priority:** P0
**Pass threshold:** 90%

## What's being measured

Across sampled conversations, the percentage assigned the *correct* contact reason by the pipeline. "Correct" means an independent judge, given the full taxonomy and the transcript, confirms the pipeline's choice is the best fit.

## Formula

```
precision = count(verdict == correct) / count(verdict in {correct, wrong})
```

Items judged `ambiguous` are reported separately and excluded from the denominator. If `ambiguous > 10%`, flag the taxonomy for sibling overlap (likely also fails Sibling Distinctness).

## Judge inputs

- `<QUERY>` = the transcript (truncated to 4K tokens if needed)
- `<CANDIDATES>` = the full taxonomy as `{id, name, description}` leaves
- `<CONSTRAINTS>`:
  - "Compare the pipeline's assigned reason (passed in extras) against the best candidate."
  - "Return verdict: `correct` if assigned == best, `wrong` if a different candidate is clearly better, `ambiguous` if two or more candidates fit equally."
- Extras: `assigned_reason_id`

## Output override

```json
{
  "verdict": "correct" | "wrong" | "ambiguous",
  "assigned_reason_id": "<echo input>",
  "best_reason_id": "<id of judge's pick>",
  "reason": "<=25 words"
}
```

## Independence guard

The judge prompt deliberately asks the model to pick the best candidate FIRST, then compare to the pipeline's assignment. This avoids anchoring on the pipeline's choice. If the judge prompt ever asks "is the pipeline's assignment correct?" directly, precision will inflate.

## Anchors

### correct
Transcript: customer reports device not powering on, asks for replacement under warranty.
Pipeline assigned: `Device Replacement`.
Judge picks: `Device Replacement`. Match.

### wrong
Transcript: customer asks why their invoice shows two charges for the same scan.
Pipeline assigned: `General Inquiry`.
Judge picks: `Billing Inquiry > Duplicate Charge`. Clearly better fit.

### ambiguous
Transcript: customer calls about "my account" and mentions both a password reset and a billing question in the same turn.
Pipeline assigned: `Account Update > Password Reset`.
Judge finds `Account Update > Password Reset` AND `Billing Inquiry` both fit. Not resolvable from transcript alone.
