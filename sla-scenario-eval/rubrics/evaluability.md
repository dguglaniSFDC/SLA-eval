# Scenario Evaluability (P0 — static)

**Judge template:** none — pure static check.
**Pass threshold:** 85%

## What's being measured

Across all criteria in all scenarios, the percentage that can be fairly passed by reading the scenario alone, without running the agent.

## Formula

```
evaluability = count(passable criteria) / count(total criteria)
```

A criterion is **blocked** (not passable) if ANY of these five rules fire:

### Block rules (hard — count against the score)

**a.** `requireToolCall == true` AND the scenario has no `suggestedToolcalls` entry defining that tool.
  - A tool with the same name attached to a *different* criterion counts (tools are scenario-scope, not criterion-scope).

**b.** Criterion description asks the agent to share information (price, status, cost, order number, policy number, appointment time, delivery ETA, coverage details, fee, availability, etc.) that is NOT present as a key in `agentContextFacts`.
  - Signal phrases: "provide", "communicate", "share", "explain", "offer", "inform", "notify".

**c.** Criterion description depends on a conditional ("if the retry fails", "if the item is out of stock", "when the appointment opens") that is NOT disambiguated by `agentContextFacts`, `userContextFacts`, or a `sampleSeeds` value.

**d.** Criterion asserts an event that happens AFTER the conversation ends and cannot be observed from the transcript (follow-up email receipt, callback day-of, technician's eventual arrival, package delivery confirmation).

**e.** The scenario has an empty `goal` (null or ""), empty `persona` (null), OR empty `userContextFacts` (`{}`).
  - All criteria in that scenario are blocked once; the scenario itself is flagged as **unanchored**.

### Warning rules (soft — reported but do not reduce the score)

**w1.** A `suggestedToolcall` input or output field name has no synonym match in `userContextFacts` / `agentContextFacts`.
  - Example: tool input `accountId` but facts have `customerAccountNumber`; or tool input `patientId` but facts have `memberNumber`. Reported as a hint — judge-independent static check.
  - Match uses lowercased substring overlap OR a configured synonym map (see `config.synonyms` if you add one).

## Report drill-down

For each blocked criterion:
- scenario id, criterion name, which block rule(s) fired, suggested fix.
Warnings grouped separately so the main table stays about blocks.
