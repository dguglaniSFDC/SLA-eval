# Scenario Reproducibility (P0 — mostly static)

**Judge template:** optional pairwise for near-miss confirmation.
**Pass threshold:** 95%

## What's being measured

Across two runs of the scenario generator on the same taxonomy, the percentage of scenarios that are **semantically identical** — same goal, same persona archetype, same essential facts, same criteria structure.

Different IDs are expected. Different wording is expected. We care about meaning stability.

## Pipeline

1. **Canonical fingerprint** per scenario:
   ```
   fingerprint = embed(
     goal + " | tags=" + sorted(tags) + " | persona=" + persona.attributes.archetype +
     " | goals=" + sorted(criterion.name for criterion in criteria) +
     " | facts=" + sorted(userContextFacts.keys) + "+" + sorted(agentContextFacts.keys)
   )
   ```
2. For each scenario in run1, find the top-1 fingerprint match in run2 by cosine similarity.
3. Threshold: `sim >= 0.90` → stable; `0.75 <= sim < 0.90` → judge-confirmed (optional, pairwise); `sim < 0.75` → unstable.

## Formula

```
reproducibility = count(stable) / count(run1 scenarios also present in run2 match space)
```

Scenarios with no plausible run2 counterpart (`sim < 0.75` AND judge says near_duplicate: no) count as unstable.

## Report drill-down

- Unstable scenarios list (run1 fingerprint ↔ nearest run2 fingerprint + sim).
- Scenarios present only in run1 or only in run2.
