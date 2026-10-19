# Evidence Backing (P0)

**Judge template:** `pointwise`
**Priority:** P0
**Pass threshold:** 90%

## What's being measured

Percentage of taxonomy reasons grounded in at least one real conversation. Catches reasons the pipeline invented but the corpus does not support.

## Formula

```
evidence_backing = count(reasons with score == supported) / count(reasons)
```

## Pre-step: retrieval

For each reason:
- Embed `reason.name + " — " + reason.description`.
- Retrieve top-`sampling.evidence_top_k` transcripts by cosine similarity.
- Pass those `k` transcripts (truncated to 2K tokens each) as `<EVIDENCE>` to the judge.

Asking the judge to search the full corpus is expensive and the judge will hallucinate matches. Pre-retrieval keeps the judgment tight.

## Judge inputs

- `<RUBRIC>` = this file's "What's being measured" + scale + anchors
- `<ITEM>` = `{reason_id, name, description, parent_name}`
- `<EVIDENCE>` = top-K retrieved transcripts with ids

## Scale

Binary.

- `supported` — at least one retrieved transcript genuinely represents the reason. "Genuinely" means a customer with this intent would have this transcript filed here.
- `unsupported` — no retrieved transcript matches, or matches are surface-term only.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (does a real customer situation ground this reason, or is it surface overlap / invented). Do not anchor on the specific vertical.

### supported — Retail
Reason: `Order Issues > Damaged on Arrival — package arrives broken, customer wants replacement`.
Evidence: 2 of 5 retrieved transcripts explicitly describe damaged shipments and request replacement.
Output: `{"score": "supported", "reason": "two transcripts explicitly report damaged shipments and request replacement", "evidence_ids": ["c_0421", "c_1104"]}`

### supported — Healthcare
Reason: `Appointments > Reschedule Request — patient needs to move an upcoming appointment`.
Evidence: 3 of 5 retrieved transcripts have the patient asking for a later date and the agent rebooking.
Output: `{"score": "supported", "reason": "three transcripts show patients rescheduling to a later date and the agent confirming the new slot", "evidence_ids": ["c_0211", "c_0732", "c_0889"]}`

### unsupported — Transportation (surface-match only)
Reason: `Account > Multi-Driver Fleet Access — fleet owner sets per-driver permissions`.
Evidence: 5 transcripts, all single-driver account access or password reset. The term "account" appears but no fleet/multi-driver concept.
Output: `{"score": "unsupported", "reason": "no transcript references multi-driver fleet setup; term-overlap only", "evidence_ids": []}`

### unsupported — Healthcare (invented concept)
Reason: `Records > Audit Trail Export Request`.
Evidence: 5 transcripts about records access but none about audit trail exports.
Output: `{"score": "unsupported", "reason": "records-access present but audit-trail-export concept absent from corpus", "evidence_ids": []}`

## Report drill-down

List every `unsupported` reason as a **candidate removal** finding. These are the highest-leverage taxonomy fixes.
