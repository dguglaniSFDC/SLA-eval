# Use-Case Ownership (P0 — mostly static)

**Judge template:** optional pointwise for ambiguous boundary cases.
**Pass threshold:** 90%

## What's being measured

Across scenarios, the percentage whose **full flow** (lookup → decision → action → confirmation) is handled inside a **single subagent**, with no mid-flow handoff to another subagent.

A handoff is any `transition`, `handoff`, `delegate`, `route to`, or `transfer to` directive in the body of the subagent, occurring between the first lookup phase and the final confirmation phase.

## Phase classification

Each action is classified into one of {lookup, decision, action, confirmation} by `config.flow_phases` verb matching. An action matching multiple phases picks the first in the ordered list.

A scenario is **owned** if ALL of the following hold:
1. The scenario's criteria map onto actions found inside **one** subagent (name of subagent = the one most criteria map to).
2. That subagent contains at least one action in each of the four phases, OR explicitly skips a phase in a way the rubric allows (see Carve-outs).
3. No handoff directive appears between its first lookup action and its final confirmation action.

## Carve-outs

- Scenarios whose criteria themselves list only 2–3 phases (e.g., informational lookup with no "action" step) count as owned if the subagent covers the phases they do include.
- `escalate` is NOT a mid-flow handoff — it's a terminal action. A scenario that ends in `escalate` after lookup/decision/action is owned.

## Formula

```
ownership = count(owned scenarios) / count(scored scenarios)
```

Scenarios with no clear subagent match (0 criteria mappable to any added subagent) count as unowned and are flagged.

## Optional judge pass

For scenarios where phase classification is ambiguous (an action matched zero phase verbs), the judge is asked:
> "Does this subagent handle the full scenario flow end-to-end, or does it hand off midway?"
Judge returns `{owns: true|false, reason}`.

## Report drill-down

- Unowned scenarios list with the missing phase and/or the mid-flow handoff location.
- Scenarios split across multiple subagents (names listed).
