# Determinism (P1 — judge-backed)

**Judge template:** pointwise.
**Pass threshold:** 70%

## What's being measured

Among decision rules whose **conditions are known** (verified, tier, order age, status, plan, etc.), the percentage implemented as **deterministic AgentScript** (`if/else/run/transition/escalate/set`) rather than natural-language reasoning instructions.

## Pipeline

1. Collect every added decision rule across the diff. A decision rule = any criterion-derived branching logic encoded in the subagent instructions or body.
2. For each rule, classify its **condition type**:
   - **Known** — references `config.known_condition_signals` (verified, tier, status, plan, …) OR a scenario fact key.
   - **Open-ended** — judgment call, policy interpretation, tone-dependent.
3. Among **known-condition rules only**, classify its **encoding**:
   - **Deterministic** — expressed via `config.deterministic_verbs` in the AgentScript grammar.
   - **Natural language** — written as prose instructions, including `config.nl_reasoning_signals`.

## Formula

```
determinism = count(known-condition rules encoded deterministically) /
              count(known-condition rules)
```

## Why judged, not regex

Classifying `condition type` and `encoding type` requires reading the rule in context. A rule that says *"If the customer is verified, proceed; otherwise ask for ID"* could be a deterministic `if verified: run(...) else run(...)` block OR a prose paragraph telling the agent to think about it — only semantic reading tells.

## Output per rule (judge)

```json
{
  "condition_type": "known" | "open_ended",
  "encoding": "deterministic" | "natural_language",
  "reason": "<one sentence>"
}
```

## Report drill-down

- Known-condition rules written as prose, listed with their subagent + rule text.
- Open-ended rules reported separately (not scored, but hint at scenario-design gaps).
