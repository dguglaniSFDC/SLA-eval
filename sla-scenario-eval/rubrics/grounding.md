# Scenario Grounding (P0)

**Judge template:** `pointwise`
**Pass threshold:** 90%

## What's being measured

Across all scenarios, the percentage whose customer situation (goal, persona, context) AND evaluation criteria both match at least one real conversation in the corpus. Catches scenarios the pipeline invented or glued together from unrelated transcripts.

## Pre-step: retrieval

For each scenario, build a query from `goal + " | " + <top persona attributes> + " | " + <keys from userContextFacts>`. Retrieve top-K transcripts by cosine similarity. Pass those K to the judge.

## Output override

Return:

```json
{
  "score": "grounded" | "partial" | "ungrounded",
  "situation_match_id": "<transcript id or null>",
  "criteria_match_ids": ["<transcript id>", ...],
  "reason": "..."
}
```

- `grounded` — at least one retrieved transcript matches BOTH the customer situation (same goal, compatible persona, overlapping facts) AND the criteria (the criteria would plausibly fire on that transcript).
- `partial` — situation matches but criteria don't (or vice versa). Counts as 0.5 in the aggregate.
- `ungrounded` — no transcript matches, or matches are surface-term only.

### Strictness bar

Grounded ≠ "the transcripts discuss the same general topic as the scenario." Retrieval always returns the top-K transcripts, so a plausibly-topical shortlist is **always** present, even for fabricated scenarios. The rubric must be stricter than the retrieval layer.

A match counts as **grounded ONLY IF the retrieved transcript contains all of**:
1. **Same customer intent** — the caller is trying to accomplish the same specific outcome the scenario's goal describes (not just discussing the same subject area).
2. **Same action shape** — the agent performs (or attempts) the same kind of resolution the scenario's criteria describe (credit vs. invoice resend vs. status-only lookup are different shapes, even if all three involve "billing").
3. **Compatible facts** — persona, triggering event, and context facts can plausibly be instantiated from the transcript (not necessarily identical wording, but not contradicted by the transcript).

If the retrieved transcripts are **only topically adjacent** (same product, same team, same page of the UI) but no single transcript matches all three above, verdict is `ungrounded` or `partial` — not `grounded`. Prefer `ungrounded` over `grounded` when uncertain; false-positive grounding masks DataPrep fabrications.

**Specificity rules for the `reason` field:**
- Always cite the transcript id you relied on.
- Quote or paraphrase the specific customer intent from the transcript — don't restate the scenario goal.
- If no transcript cleanly matches, name the single closest candidate and say what's missing (e.g. "c_0412 is about invoice resend; scenario is about credit-note creation — different action shape").

## Anchors

> Examples span industries deliberately — generalize the *pattern* (both situation and criteria must line up with a real conversation). Do not anchor on the specific vertical.

### grounded — Retail
Scenario goal: "Issue a refund for an order that was double-charged."
Criteria: verify the duplicate charge, process the refund, confirm with the customer.
Evidence (3/5): transcripts where the customer reports two charges for one order and the agent walks through the refund flow.
Output: `{"score": "grounded", "situation_match_id": "c_0412", "criteria_match_ids": ["c_0412", "c_0507"], "reason": "transcript c_0412 reports a double-charged order and the agent completes the refund — matches goal + criteria"}`

### partial — Healthcare
Scenario goal: "Reschedule a cancelled appointment and attach it to the correct provider."
Criteria: look up original appointment, offer new slots, confirm provider assignment.
Evidence: transcripts show rescheduling, but the provider-assignment step never fires — agents just offer the next available slot regardless of provider.
Output: `{"score": "partial", "situation_match_id": "c_0211", "criteria_match_ids": [], "reason": "situation present; provider-assignment criterion never fires in retrieved transcripts"}`

### ungrounded — Transportation
Scenario goal: "Fleet manager configures per-driver vehicle restrictions across multiple depots."
Evidence: single-driver, single-vehicle account transcripts only.
Output: `{"score": "ungrounded", "situation_match_id": null, "criteria_match_ids": [], "reason": "no multi-depot/fleet restriction configuration in retrieved transcripts"}`
