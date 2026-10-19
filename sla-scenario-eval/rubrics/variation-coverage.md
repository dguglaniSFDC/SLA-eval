# Variation Coverage (P1 — experimental)

**Judge template:** `pointwise` (extraction) + `grounded-match` (matching)
**Pass threshold:** 85%

## What's being measured

Across distinct situation **variants** (not reasons — variants *within* a reason, e.g. "damaged shipment WITH prior refund on file" vs "WITHOUT"), the percentage represented by at least one scenario sampleSeed.

## Why experimental

Variant extraction is prompt-sensitive. The output below is best-read as "candidate variants surfaced from transcripts that no seed covers" — i.e. a drill-down list, not a precise score.

## Pipeline

1. **Extract** (blind): sample `variation_extract_n` transcripts. For each, judge extracts `{situation_summary, variant_axes: [{axis, value}]}` without seeing the scenarios or seeds.
2. **Cluster**: embed `situation_summary + ";" + join(variant_axes)`, agglomerative at `variation_sim_threshold`. Cluster medoid becomes a reference variant.
3. **Match**: for each reference variant, judge decides whether any scenario seed represents it. Build the "scenario fingerprint" from `(scenario.goal, seed.values)`.
4. **Score** = matched / reference_count.

## Extraction output (step 1)

```json
{
  "situation_summary": "customer reports a double-charged order, requests refund",
  "variant_axes": [
    {"axis": "evidence_provided", "value": "none"},
    {"axis": "customer_segment", "value": "first-time-buyer"},
    {"axis": "prior_refunds", "value": "unknown"}
  ]
}
```

## Match output (step 3)

```json
{"match": "yes" | "no", "scenario_id": "...", "seed_index": 0, "confidence": 0.0-1.0, "reason": "..."}
```

## Anchors

> Examples span industries deliberately — generalize the *pattern* (does any seed carry this variant's distinguishing axis). Do not anchor on the specific vertical.

### yes — Retail
Variant: "double-charged order, no prior refunds, order numbers provided"
Scenario: `s_0104` with seed matching order numbers.
Output: `{"match": "yes", "scenario_id": "s_0104", "seed_index": 0, "confidence": 0.88, "reason": "seed has both order numbers and no prior-refund path"}`

### no (missing variant) — Healthcare
Variant: "appointment reschedule WITH prior cancellations on file — patient wants to know if the no-show fee applies"
Scenarios: all reschedule scenarios lack the prior-cancellation-history axis in seeds.
Output: `{"match": "no", "scenario_id": null, "confidence": 0.0, "reason": "no scenario carries prior-cancellation state in sampleSeeds"}`

### no (missing variant) — Transportation
Variant: "delayed pickup during surge pricing — rider wants fare adjustment, not reassignment"
Scenarios: all delayed-pickup scenarios assume driver reassignment; none model fare-adjustment-only resolution.
Output: `{"match": "no", "scenario_id": null, "confidence": 0.0, "reason": "no scenario carries a fare-adjustment-only resolution path"}`

## Report drill-down

List every `no` as a **missing variant**. Taxonomy maintainer decides: add a seed to an existing scenario, or create a new scenario.
