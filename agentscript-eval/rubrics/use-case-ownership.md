# Use-Case Ownership (P0 — static)

**Judge template:** none.
**Pass threshold:** 90%

## What's being measured

Across scenarios, the percentage whose attributed subagent handles the flow **without delegating mid-way to another non-router subagent**.

Ownership is a single question: *did this subagent stay in charge of the flow, or did it punt to another subagent?* It is deliberately *not* a check that the subagent covers lookup / decision / action / confirmation phases — that would require guessing phases from action names, which is noisy and penalizes authors for cosmetic naming choices. `subagent_substance` and `instruction_substance` already cover whether a subagent has enough work in it.

## How it's computed

1. **Attribute** each scenario to the subagent that most of its criteria map to (shared `attrib` map from the harness).
2. For the attributed subagent, scan `body_text` for `transition to @subagent.<Name>` directives.
3. A directive is a **mid-flow handoff** iff its target subagent is neither:
   - the router (`agent_router`, `router`), nor
   - the subagent itself (self-loop).

   `@utils.escalate` is a terminal action and is **not** counted as a mid-flow handoff.
4. A scenario is **owned** iff the attributed subagent has zero mid-flow handoffs. Scenarios with no attributable subagent are flagged unowned and counted in the denominator.

## Formula

```
ownership = count(owned scenarios) / count(scored scenarios)
```

## Report drill-down

- Unowned scenarios list with the mid-flow handoff targets, so the author can see which subagent the flow bailed out to.
- Scenarios with no attributed subagent are listed separately with `reason: "no attributed subagent"`.
