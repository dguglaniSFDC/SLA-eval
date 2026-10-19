# Criteria Completeness (P0 — static)

**Judge template:** none — static heuristic.
**Pass threshold:** 85%

## What's being measured

Average per-scenario criterion-completeness score (0–3), normalized to a percentage.

Three sub-signals per criterion:
1. **Tool invoked** — `requireToolCall == true` has an attached `suggestedToolcalls` entry.
2. **Outcome stated** — criterion description contains an outcome verb (confirm, verify, resolve, send, process, create, update, remove, escalate, provide, explain, communicate, notify, offer, guide).
3. **Verification honored** — if the scenario is **sensitive** (see `verification_patterns` in config), at least one criterion in the scenario matches `verification_patterns`. Sub-signal applies at the scenario level; every criterion in a sensitive-but-ungated scenario loses this point.

## Formula

```
per_criterion_score = sum(subsignal_1, subsignal_2, subsignal_3)   # each 0 or 1
scenario_score     = mean(per_criterion_score across its criteria)
criteria_completeness = mean(scenario_score across scenarios) / 3
```

So a scenario where every criterion scores 3/3 reports 100%.

## Why average, not pass/fail

A single scenario with mostly-good criteria and one gap gets partial credit instead of being wholly blocked. Aggregating gives a smoother signal for taxonomy-wide quality.

## Report drill-down

- Scenarios with avg < 2.0: listed as **weak criteria**.
- Breakdown per sub-signal: how many scenarios failed tool-invoked / outcome / verification respectively.
