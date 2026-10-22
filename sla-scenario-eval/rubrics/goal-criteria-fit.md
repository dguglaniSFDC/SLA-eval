# Goal-Criteria Fit (P0)

**Judge template:** `pointwise`
**Pass threshold:** 85%

## What's being measured

For each criterion in a scenario, whether its **description** describes a necessary step toward the scenario's **goal**. Catches the pipeline bug where a well-written criterion is attached to the wrong scenario (e.g. a "retrieve order to support the price adjustment request" criterion bolted onto a cancel-refund scenario).

The scenario's `goal` is treated as **ground truth** — it comes from the UI and is not on trial. Only criteria are evaluated.

## Score

Score = `fit` criteria / total criteria across all scenarios. A criterion that reasonably serves the goal — including implied prerequisites (e.g. identity verification before mutating an order, retrieving an order before modifying it) — counts as `fit`.

## Output override

Return:

```json
{
  "scenario": "<id>",
  "goal": "<verbatim>",
  "verdicts": [
    {
      "name": "<criterion name>",
      "verdict": "fit" | "out_of_scope" | "mis_attached" | "contradicts_goal",
      "reason": "<one-line explanation>"
    }
  ]
}
```

Verdict definitions:

- **`fit`** — the criterion description describes a step that logically serves the goal, including implied prerequisites.
- **`out_of_scope`** — the criterion goes beyond the goal (e.g. "Place order" on an availability-inquiry goal). The step is coherent but exceeds what the goal asks for.
- **`mis_attached`** — the criterion description references actions, entities, or outcomes that belong to a different scenario (e.g. "retrieve order to support the price adjustment request" on a cancel-refund goal).
- **`contradicts_goal`** — the criterion name says one thing but the description does another, or the description directly contradicts the goal (e.g. criterion named "Confirm shipping address" whose description actually updates it).

## Judging guidance

- The goal is ground truth. Even if the goal doesn't explicitly mention "order," a price-match request on a purchased item implies order lookup — that counts as `fit`.
- Verb matters. "Confirm" ≠ "Update." If the name says one and the description says the other, that's `contradicts_goal`.
- Boilerplate phrases that *fit the goal* are `fit`. Boilerplate phrases that reference a different goal are `mis_attached`.
- Triplicate criteria (3× the same step) count as 2 extra `mis_attached` verdicts — only one copy is `fit`.

## Anchors

### fit — Retail price match
Goal: *Get help matching a recently lower product price after the item became more expensive.*
Criterion: "Verify identity — Verify the customer's identity using the provided account and order details before changing the order."
Verdict: `fit` — a price match on a placed order IS an order modification; identity verification is a necessary prerequisite.

### mis_attached — Retail cancel + refund
Goal: *Cancel the unshipped order and receive a refund for the full amount.*
Criterion: "Retrieve order — Retrieve the customer's order using the provided order identifier to support the price adjustment request."
Verdict: `mis_attached` — there is no price adjustment in this scenario; the description was authored for a price-match flow.

### contradicts_goal — Retail shipment-date correction
Goal: *Confirm and correct the shipment date after being told the shipment date had changed.*
Criterion: "Update order — Update the order with the requested new shipping address and communicate that the address was updated."
Verdict: `contradicts_goal` — the goal is about shipment date; the criterion description is about shipping address.

### out_of_scope — Retail availability inquiry
Goal: *Find out whether the requested boots are available in the desired style and size.*
Criterion: "Place order — Place the order for the requested item and communicate the order confirmation to the customer."
Verdict: `out_of_scope` — the goal is explicitly an inquiry ("find out whether"); placing an order exceeds the goal's scope.

### fit — Technical Support 2FA recovery
Goal: *Regain account access after losing the phone used for two-factor authentication.*
Criterion: "Verify identity (alt) — Verify the customer's identity using alternative information when the registered phone is unavailable."
Verdict: `fit` — alternate identity verification is a necessary first step when the registered 2FA device is unavailable.
