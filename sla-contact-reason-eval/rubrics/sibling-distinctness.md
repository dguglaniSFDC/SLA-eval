# Sibling Distinctness (P1)

**Judge template:** `pairwise`
**Priority:** P1
**Pass threshold:** 85%

## What's being measured

Across all pairs of sibling reasons under the same parent, the percentage that are meaningfully distinct. Non-distinct siblings cause classifier confusion and inflate `ambiguous` in Precision.

## Formula

```
sibling_distinctness = count(pairs with verdict == distinct) / count(sibling pairs)
```

Only pairs within the same parent are evaluated. Cross-parent overlap is a separate (and much rarer) problem.

## Pre-step

For each parent category `P` in the taxonomy:
- Enumerate all pairs `(A, B)` of its direct children.
- If `|children| == 1`, skip (no pairs).
- Expected volume: a 30-reason / 8-parent taxonomy produces ~40–60 pairs. Keep it tractable.

## Judge inputs

- `<RUBRIC>` = this file's definition + anchors
- `<ITEM_A>` = `{id, name, description}` for sibling A
- `<ITEM_B>` = `{id, name, description}` for sibling B

## Definition of "distinct"

Two siblings are **distinct** if no real customer situation could legitimately be filed under either. Surface wording similarity is not overlap — only situational overlap counts.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (do the two reasons map to different situations with different downstream handling, or do real customer situations straddle both). Do not anchor on the specific vertical.

### distinct — Retail
A: `Returns > Damaged in Transit — package arrives broken`.
B: `Returns > Wrong Item Shipped — customer receives a different SKU than ordered`.
Verdict: `distinct`. Different root cause (carrier damage vs pick/pack error), different downstream workflow (replacement + damage claim vs reverse-logistics correction).

### distinct — Healthcare
A: `Appointments > Reschedule — move to a new date, slot released`.
B: `Appointments > Cancellation — appointment removed entirely, slot released and no replacement`.
Verdict: `distinct`. Observable symptom overlaps but downstream treatment differs (reschedule holds patient intent, cancellation ends it).

### overlapping (situational) — Transportation
A: `Trip Issues > Delayed Pickup — driver has not arrived by ETA`.
B: `Trip Issues > No-Show Driver — driver never arrives, rider cancels`.
Overlap example: "The driver was 20 minutes late and I ended up cancelling before they got here" fits both.
Verdict: `overlapping`. Boundary between "very late" and "no-show" is undefined.

### overlapping (surface split of same concept) — Healthcare
A: `Billing > Invoice Question`.
B: `Patient Accounts > Invoice Clarification`.
Verdict: `overlapping`. Same situation split across two parents by naming convention, not by handling.

## Report drill-down

List every `overlapping` pair as a **merge candidate** with the judge's `overlap_examples`. Taxonomy maintainer uses these to decide: merge, re-parent, or sharpen descriptions.
