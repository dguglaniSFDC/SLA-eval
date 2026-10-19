# Routing Precision (P1 — static)

**Judge template:** none — label comparison.
**Pass threshold:** 85%

## What's being measured

On a focused set of **ambiguous, multi-intent, and out-of-scope** scenarios, the percentage routed to the correct subagent on the **first hop**.

Reported with the router type (e.g., `HyperClassifier`, `KeywordRouter`, `LLMRouter`) from the trace file so you can compare across experiments.

## Inputs

`--routing-trace` is JSONL, one object per scenario:
```json
{"scenario_id": "s003", "first_hop_subagent": "RefundAgent", "router_type": "HyperClassifier", "category": "ambiguous"}
```

- `category` is one of `ambiguous | multi_intent | out_of_scope | normal`. Only non-normal rows score; normal is reported but excluded.

Expected labels come from the scenarios file:
- A scenario's expected subagent is either `expectedSubagent` (if present) OR derived from its first tag by matching tag to subagent attribution (same attribution logic as use-case-focus).
- Out-of-scope scenarios expect `escalate` or `fallback` as the first hop; any other label is wrong.

## Formula

```
routing_precision = correct_first_hop / scored_rows
```

If no non-normal rows exist, SKIP with reason "routing trace contains no ambiguous/multi_intent/out_of_scope rows".

## Report drill-down

- Router type reported next to the score.
- Confusion rows: `scenario_id | expected | actual | category`.
- Breakdown by category (ambiguous vs multi-intent vs OOS accuracy).
