# Conversation Coverage (P0)

**Judge template:** `pointwise`
**Pass threshold:** 80%

## What's being measured

Across all conversations in the corpus, the percentage represented by at least one scenario. A conversation is **covered** if some scenario's `goal` + `persona` + context facts plausibly describe its intent and flow.

This is the **inverse of Scenario Grounding**:

- Grounding asks: *"does every scenario trace to a real conversation?"* — catches fabricated scenarios.
- Coverage asks: *"does every real conversation trace to some scenario?"* — catches long-tail customer behavior the scenario set never represents.

A low coverage score means the scenario set is a thin sample of the corpus — training on it will underweight whatever the scenarios missed. The threshold is intentionally lower than grounding's (80% vs 90%) because the long tail is expected; the goal is to surface *how long* the tail is, not to drive it to zero.

## Pre-step: retrieval

For each conversation, build a query from its text (truncated to the first ~2000 chars for signal). Keyword-rank the scenario set — each scenario's indexable text is `goal + " " + persona + " " + userContextFacts + " " + agentContextFacts + " " + <criteria names>`. Pass the top-K scenarios to the judge alongside the conversation.

If the shortlist is empty (no keyword overlap at all), the verdict is `uncovered` without a judge call.

## Output override

Return:

```json
{
  "score": "covered" | "partial" | "uncovered",
  "scenario_match_id": "<scenario id or null>",
  "reason": "<one-line>"
}
```

- **`covered`** — at least one shortlisted scenario's goal + persona + context plausibly matches the conversation's intent and flow. Minor divergence on surface details is fine (different product, same shape).
- **`partial`** — a scenario matches the conversation's **intent** but misses significant structural elements (e.g. the conversation is a multi-step escalation and no scenario represents the escalation path). Counts as 0.5 in the aggregate.
- **`uncovered`** — no shortlisted scenario matches, or matches are surface-term only (same keyword, different flow).

## Judging guidance

- The conversation is ground truth. If no scenario covers it, that's the pipeline's failure to sample this part of the corpus.
- Don't require exact tag/reason alignment — a scenario tagged "Billing::Refund" can cover a conversation whose intent is "cancel + refund" even if the corpus labels it "Cancellations". The *intent and flow* match is what counts.
- Multi-intent conversations (customer asks about billing AND an unrelated shipping issue) are `covered` if any scenario matches *either* intent; `partial` if a scenario matches only the shorter/dominated intent.
- Conversations that are purely small talk / disconnected / out-of-domain are `uncovered` and that's fine — they shouldn't be in the corpus.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (does any scenario describe this conversation's intent + flow). Do not anchor on the specific vertical.

### covered — Retail

Conversation: Customer calls about an order that was double-charged, agent verifies the duplicate charge, issues a refund, confirms with the customer.
Shortlist includes a scenario with goal "Issue a refund for an order that was double-charged" and criteria for verify-duplicate / process-refund / confirm.
Output: `{"score": "covered", "scenario_match_id": "scn_refund_duplicate", "reason": "goal + three-step flow match"}`

### partial — Healthcare

Conversation: Patient reschedules a cancelled appointment, then the agent escalates to a scheduling supervisor because the preferred provider is on leave.
Shortlist includes a reschedule-cancelled-appointment scenario, but no scenario represents the escalation-to-supervisor path.
Output: `{"score": "partial", "scenario_match_id": "scn_reschedule_cancelled", "reason": "reschedule intent covered; supervisor-escalation flow is not represented"}`

### uncovered — Transportation

Conversation: Fleet manager configures per-driver vehicle restrictions across three depots in one call.
Shortlist includes only single-driver scenarios.
Output: `{"score": "uncovered", "scenario_match_id": null, "reason": "no multi-depot/fleet restriction configuration scenario"}`

### uncovered-but-ok — any industry

Conversation: 30 seconds of silence then the customer hangs up.
Output: `{"score": "uncovered", "scenario_match_id": null, "reason": "no substantive content; out-of-scope"}`
Note: in the drill-down, out-of-scope `uncovered` conversations are flagged separately so they don't inflate the "missing scenario" signal.
