# Use-Case Focus (P1 — static)

**Judge template:** none — tag counting.
**Pass threshold:** 85%

## What's being measured

Among added subagents, the percentage whose scenarios all come from **one** contact reason.

## Attribution

Each added subagent is attributed the set of scenarios that routed to it during training:
1. If `--routing-trace` is provided, use its `first_hop_subagent` field.
2. Otherwise, attribute by name match: scenarios whose tag `<Category>::<Reason>` or scenario id appears in the subagent's `handles` / `scope` / instructions text.
3. Scenarios that can't be attributed to any added subagent are reported separately — they don't affect the score.

## Formula

```
reason_of(scenario) = first tag "<cat>::<reason>" or the reasons CSV match
single_reason(sub)  = len({reason_of(s) for s in scenarios(sub)}) == 1
use_case_focus      = count(single_reason subagents) / count(added subagents with ≥1 scenario)
```

Subagents with zero attributed scenarios are excluded from both numerator and denominator (reported separately).

## Report drill-down

- Subagents handling multiple reasons: listed with the reason split.
- Added subagents with no attributed scenarios (potentially dead code from training).

## Illustrative examples (industry-agnostic)

> Examples span industries deliberately — the pattern (one subagent → one reason vs one subagent → many) is what matters, not the specific vertical.

- **Retail — focused:** `RefundAgent` handles only `Billing::Duplicate Charge` scenarios (18 attributed, 1 reason). PASS.
- **Healthcare — focused:** `RescheduleAgent` handles only `Appointments::Reschedule` (9 attributed, 1 reason). PASS.
- **Transportation — unfocused:** `TripAgent` handles both `Trip Issues::Delayed Pickup` (12) AND `Policies::Cancellation Fee` (4). Two unrelated reasons under one subagent — the trained agent will confuse routing. Suggest splitting.
