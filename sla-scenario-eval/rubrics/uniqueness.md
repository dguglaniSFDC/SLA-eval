# Scenario Uniqueness (P1)

**Judge template:** `pairwise`
**Pass threshold:** 90%

## What's being measured

Across all scenario pairs within the same contact reason, the percentage that are meaningfully distinct. Non-distinct scenarios inflate the training set with near-duplicates and bias the trained agent.

## Formula

```
scenario_uniqueness = count(within-reason pairs with verdict == distinct) / count(within-reason pairs)
```

Pairs across different contact reasons are not evaluated here (handled by Tag Coverage / Tagging Confidence).

## Pre-step

For each contact reason `R`:
- Collect all scenarios tagged to `R`.
- Enumerate all `(A, B)` pairs. If a reason has >8 scenarios, cap pairs at 28 random pairs (seeded) to keep volume tractable.

## Judge inputs

- `<ITEM_A>` = `{id, goal, persona, userContextFacts, criteria.names}`
- `<ITEM_B>` = same for scenario B

## Definition of "distinct"

Two scenarios are **distinct** if a trained agent would meaningfully need to handle them differently. Surface wording similarity is not overlap. Different persona *attributes* alone (same situation, different emotional tone) is NOT distinctness — collapse to one scenario with seeds.

## Output override

```json
{"verdict": "distinct" | "near_duplicate", "reason": "...", "overlap_examples": ["..."]}
```

## Anchors

> Examples span industries deliberately — generalize the *pattern* (would the agent handle them differently, or is the difference cosmetic / collapsible to a seed). Do not anchor on the specific vertical.

### distinct — Retail
A: goal="Refund a double-charged order", criteria={verifyDuplicateCharge, processRefund}
B: goal="Credit a shipping fee charged in error", criteria={verifyShipRecord, calculateCredit, processCredit}
Verdict: `distinct` — different trigger (duplicate charge vs incorrect fee) and different verification path.

### distinct — Healthcare
A: goal="Reschedule a cancelled appointment to a later date", criteria={lookupOriginal, offerSlots, confirmBooking}
B: goal="Cancel an appointment and refund the co-pay", criteria={lookupOriginal, cancelAppointment, processRefund}
Verdict: `distinct` — overlapping first step but entirely different downstream actions and outcome.

### near_duplicate — Transportation
A: goal="Reassign driver for a delayed pickup", persona.emotionalTone="frustrated"
B: goal="Delayed pickup — need a new driver", persona.emotionalTone="calm"
Verdict: `near_duplicate` — same goal, same flow; emotional-tone difference belongs in a seed, not a separate scenario.

## Report drill-down

List every `near_duplicate` as a **merge candidate**.
