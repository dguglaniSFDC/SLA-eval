# Shape & Structural Stability (P0 — static)

**Judge template:** none — set comparison on parsed IR.
**Pass threshold:** 90%

## What's being measured

Across two training runs on the same scenario set, how similar the resulting AgentScripts are in **structure** (not wording).

Two sub-signals:
1. **Subagent-name overlap** — Jaccard similarity of the subagent-name set across the two runs.
2. **Action-set stability per shared subagent** — for each subagent name present in both runs, Jaccard of the set of action identifiers inside it.

## Formula

```
subagent_jaccard   = |names(run1) ∩ names(run2)| / |names(run1) ∪ names(run2)|
action_jaccard_sub = mean over shared subagents of
                       |actions(run1,sub) ∩ actions(run2,sub)| / |actions(run1,sub) ∪ actions(run2,sub)|
shape_stability    = 0.5 * subagent_jaccard + 0.5 * action_jaccard_sub
```

If zero subagents are shared, `action_jaccard_sub = 0`.

## Action identifier

`"<action_type>:<normalized_target>"` where:
- `action_type` is `run|lookup|verify|refund|...` (verb)
- `normalized_target` lowercases + strips scenario-specific IDs via `config.hardcode_marker_patterns`

Different runs tend to produce different literal arguments; normalization isolates structural stability from argument drift.

## Report drill-down

- `subagent_jaccard`, `action_jaccard_sub` separately.
- Lists: `only_in_run1`, `only_in_run2`, `shared`.
- Per shared subagent, the action-set Δ.
