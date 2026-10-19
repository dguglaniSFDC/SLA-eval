# Taxonomy Tagging Confidence (P1)

**Judge template:** `grounded-match`
**Pass threshold:** 70% (floor — any score below `tagging_confidence_floor` is flagged, not scored)

## What's being measured

For each scenario, how confidently the current tag maps to its actual customer situation. Low-confidence tags indicate scenarios sitting on category boundaries — they pollute both categories' rollups downstream.

## Formula

```
tagging_confidence = mean(top_candidate_confidence)
```

Per scenario, the judge picks the best reason from the taxonomy, independent of the current tag, and returns a 0–1 confidence. Scenarios where the top pick differs from the current tag are flagged as **mistag candidates**.

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

- `mistag = (best_category != current_category OR best_reason != current_reason)`
- `confidence < config.tagging_confidence_floor` → surfaced as **boundary case** even when `mistag = false`.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (is the current tag unambiguously the best, is a sibling clearly better, or is the scenario sitting on a boundary). Do not anchor on the specific vertical.

### confident, correct — Retail
Scenario goal: "Refund a double-charged order and confirm with the customer"
Current tag: "Billing::Duplicate Charge"
Judge pick: "Billing::Duplicate Charge", confidence=0.91
Output: `{"best_category": "Billing", "best_reason": "Duplicate Charge", "confidence": 0.91, "mistag": false, "reason": "canonical duplicate-charge refund flow"}`

### mistag — Healthcare
Scenario goal: "Patient needs to move an appointment to a later date and update the reminder contact method"
Current tag: "Appointments::Cancellation"
Judge pick: "Appointments::Reschedule", confidence=0.84
Output: `{"best_category": "Appointments", "best_reason": "Reschedule", "confidence": 0.84, "mistag": true, "reason": "scenario preserves the appointment at a new date — reschedule, not cancellation"}`

### boundary (low confidence) — Transportation
Scenario goal: "Rider wants ETA for a delayed pickup and asks what the policy is for cancellation fees"
Current tag: "Trip Issues::Delayed Pickup", confidence=0.52
Alternatives: "Policies::Cancellation Fee" (0.47)
Output: `{"confidence": 0.52, "mistag": false, "reason": "scenario spans both intents; split into two scenarios or pick the dominant intent"}`
