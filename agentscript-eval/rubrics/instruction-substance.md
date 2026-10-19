# Instruction Substance (P1 — judge-backed)

**Judge template:** pointwise.
**Pass threshold:** 80%

## What's being measured

Across each added subagent, the percentage of **decision rules in the scenario criteria that routed to it** that are actually written into the subagent's instructions (as reasoning the agent should carry out), not just left to actions.

A subagent that calls an action (e.g., `issueRefund`, `rescheduleAppointment`, `reassignDriver`) but never explains in its instructions WHEN to call it has low instruction substance. Low instruction-substance → the agent is memorizing an action sequence rather than internalizing the policy.

## Pipeline

Per added subagent S:
1. Collect scenario criteria that routed to S (via attribution rules in use-case-focus).
2. For each criterion, judge:
   > "Is this decision rule reflected in the subagent's instructions as reasoning, or only as an action call?"
   Judge returns `{reflected: true|false, reason}`.
3. Count reflected / total.

## Formula

```
instruction_substance = sum(reflected rules across subagents) / sum(total rules across subagents)
```

## Why judged

An instruction can state the rule using different words than the criterion (criterion: "verify customer before refund"; instruction: "always confirm identity before touching the account"). Exact-match misses paraphrases; semantic match needs the judge.

## Anchors

> Examples span industries deliberately — generalize the *pattern* (is the decision rule written as reasoning the agent carries out, or only hidden inside an action call). Do not anchor on the specific vertical.

### reflected — Retail
Criterion: "Only issue a refund if the order was charged within the last 60 days."
Instruction excerpt: "Before refunding, check the order date. If the order is older than 60 days, decline and offer store credit instead."
Output: `{"reflected": true, "reason": "60-day cutoff and alternative are both stated as reasoning"}`

### reflected — Healthcare
Criterion: "Verify the patient's identity (date of birth + member ID) before releasing records."
Instruction excerpt: "Confirm identity by matching both the patient's date of birth and member ID. If either does not match, do not release records; transfer to member services."
Output: `{"reflected": true, "reason": "verification requirement and fallback behavior are stated"}`

### not reflected — Transportation (action without reasoning)
Criterion: "Only reassign a driver if the current driver is >10 minutes past ETA."
Instructions excerpt: no mention of the 10-minute threshold.
Actions: `reassignDriver(rideId)`.
Output: `{"reflected": false, "reason": "the 10-minute threshold exists only as behavior inside the action, never as policy in the instructions"}`

## Report drill-down

- Per subagent: reflected / total ratio.
- Specific criteria that were NOT reflected in the instructions, by subagent.
