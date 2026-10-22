# Taxonomy Tagging Confidence (P1)

**Judge template:** `grounded-match`
**Pass threshold:** 70% of scenarios confidently tagged (confidence ≥ `tagging_confidence_floor`, default 0.60)

## What's being measured

Across all scenarios, the percentage **confidently tagged** to a single contact reason (confidence ≥ floor). The rest sit near a category boundary — e.g., a scenario tagged "Billing" at 52% confidence probably belongs in "Refunds". Low-confidence tags quietly pollute both categories' rollups: a scenario counted under Billing is also *not* counted under Refunds, so coverage, grounding, and uniqueness all drift against the wrong denominator.

Higher is better; this reads the same direction as every other metric in the scorecard.

## Formula

```
tagging_confidence = (# scenarios with top-candidate confidence ≥ floor) / (# scenarios)
```

Per scenario, the judge picks the best reason from the taxonomy — independent of the current tag — and returns a 0–1 confidence. Scenarios where the top pick differs from the current tag are also flagged as **mistag candidates** in the drill-down (orthogonal to the score, but important triage signal).

## Pre-step

Candidates = full list of `{category, name}` from the reason taxonomy.
Query = `scenario.goal + " | " + join(scenario.userContextFacts) + " | " + join(criterion names)`.

## Output override

```json
{
  "best_category": "...",
  "best_reason": "...",
  "confidence": 0.0-1.0,
  "current_tag": "<echo>",
  "mistag": true | false,
  "reason": "..."
}
```

- `mistag = (best_category != current_category OR best_reason != current_reason)` — surfaced in the drill-down, does not reduce the score on its own (a *confident* mistag is a different problem — fix the tag, not the scenario).
- `confidence < config.tagging_confidence_floor` → the scenario is a **boundary case** and does NOT count toward the score.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (is the current tag unambiguously the best, is a sibling clearly better, or is the scenario sitting on a boundary). Do not anchor on the specific vertical.

### confident, correct — Retail
Scenario goal: "Refund a double-charged order and confirm with the customer"
Current tag: "Billing::Duplicate Charge"
Judge pick: "Billing::Duplicate Charge", confidence=0.91
Output: `{"best_category": "Billing", "best_reason": "Duplicate Charge", "confidence": 0.91, "mistag": false, "reason": "canonical duplicate-charge refund flow"}`
Counts toward the score (confident), no boundary flag.

### confident mistag — Healthcare
Scenario goal: "Patient needs to move an appointment to a later date and update the reminder contact method"
Current tag: "Appointments::Cancellation"
Judge pick: "Appointments::Reschedule", confidence=0.84
Output: `{"best_category": "Appointments", "best_reason": "Reschedule", "confidence": 0.84, "mistag": true, "reason": "scenario preserves the appointment at a new date — reschedule, not cancellation"}`
Counts toward the score (confident), flagged for retag in the drill-down.

### boundary (low confidence) — Transportation
Scenario goal: "Rider wants ETA for a delayed pickup and asks what the policy is for cancellation fees"
Current tag: "Trip Issues::Delayed Pickup", confidence=0.52
Alternatives: "Policies::Cancellation Fee" (0.47)
Output: `{"confidence": 0.52, "mistag": false, "reason": "scenario spans both intents; split into two scenarios or pick the dominant intent"}`
Does NOT count toward the score; surfaced as a boundary case to split or re-scope.
