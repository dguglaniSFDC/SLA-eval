# Describe Reason (bootstrap)

Not an evaluation rubric. Used by `--bootstrap-descriptions` to fill in empty descriptions when the user only supplied reason names.

**Judge template:** `pointwise`
**Scale:** none — the judge is asked to produce a one-line description, not a score.

## What's being measured

Nothing. This is a generation step, not a scoring step.

## Output override

Return a single key:

```json
{"description": "<one-line description grounded in the retrieved transcripts>"}
```

## Instructions to the judge

- You will see a reason **name** and the top-K retrieved transcripts for it.
- Write one sentence (≤25 words) that captures the customer situation this reason represents.
- Ground every claim in the evidence. If the evidence doesn't actually support the name, return `{"description": ""}` — the eval will later flag this reason as unsupported.
- Do NOT paraphrase the name back ("Billing Dispute means a dispute about billing"). Describe the situation: trigger, context, what the customer wants.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (ground in evidence, describe the situation, stay specific but not narrower than the data). Do not anchor on the specific vertical.

### Good — Retail
Name: `Return — Damaged in Transit`
Evidence: 3 transcripts about items arriving broken, customer wants replacement + prepaid return label.
Output: `{"description": "Customer received a damaged shipment and is requesting a replacement with a return label for the damaged item"}`

### Good — Healthcare (narrower than the name, grounded in evidence)
Name: `Appointment Change`
Evidence: 4 transcripts, all customers rescheduling to a later date due to travel; none cancelling outright.
Output: `{"description": "Customer requests to move an upcoming appointment to a later date, typically due to travel or scheduling conflict"}`

### Good — Transportation
Name: `Delayed Pickup`
Evidence: 3 transcripts of riders waiting beyond ETA, asking for status or a new driver assignment.
Output: `{"description": "Driver has not arrived by the quoted ETA; rider wants a status update or a reassigned driver"}`

### Empty — evidence doesn't support the name
Name: `Multi-Site Admin Access`
Evidence: 5 transcripts, all single-user password resets. No multi-site concept appears.
Output: `{"description": ""}`
