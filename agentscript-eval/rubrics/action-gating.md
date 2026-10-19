# Action Gating (P1 — static)

**Judge template:** none — presence check.
**Pass threshold:** 90%

## What's being measured

Among added actions that have a **precondition**, the percentage gated with an `available_when` / `requires` / `guard` / `precondition` clause (or equivalent in the DSL).

## Precondition detection

An action has a precondition if ANY of the following hold:
1. Its verb is a sensitive-action verb (`refund, cancel, unlink, remove, delete, escalate, create case, update account, set permission`).
2. The scenario criterion that generated it mentions verification, confirmation, lookup, eligibility, or `requireToolCall == true` with explicit setup.
3. The action's inputs reference variables that other actions produce (requires-order-lookup pattern).

## Gating detection

An action is **gated** if its AgentScript definition contains any of:
- `available_when: <expr>`
- `requires: [...]`
- `guard: <expr>`
- `precondition: <expr>`
- an enclosing `if` block whose condition includes a scenario fact or verification flag

## Formula

```
action_gating = gated_actions_with_precondition / actions_with_precondition
```

Actions with no precondition are excluded from both numerator and denominator.

## Report drill-down

- Ungated preconditioned actions: subagent → action → the condition they SHOULD be gated on.
- Sensitive actions missing `available_when`: flagged specifically (highest-risk subset).
