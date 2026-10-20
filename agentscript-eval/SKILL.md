---
name: agentscript-eval
description: Evaluate AgentScript training by diffing a before/after script and scoring the added material against the training scenarios on 7 structural + semantic metrics.
---

# AgentScript Evaluation

Diffs **before** and **after** AgentScript, extracts what training added, and scores that delta against the scenarios that produced it.

## When to invoke

Trigger phrases:
- "evaluate agentscript"
- "score agentscript training"
- "diff before/after agentscript"
- "run agentscript eval"

Companions:
- `sla-contact-reason-eval` — scores the reason taxonomy
- `sla-scenario-eval` — scores scenarios against the taxonomy
- `transcript-normalize` — prep for conversation inputs (not required here)

## Inputs

- **`--before`** (required) — AgentScript before training. JSON, YAML, or raw DSL (`.ast`, `.txt`).
- **`--after`** (required) — AgentScript after training. Same format as `--before`.
- **`--scenarios`** (required) — scenarios driving the training (shape: `id, tags, goal, persona, userContextFacts, agentContextFacts, sampleSeeds, criteria, suggestedToolcalls?`).
- **`--reasons`** (required for use-case-focus) — contact-reason taxonomy (CSV or JSON).
- **`--static-only`** — skip judge-backed metrics.
- **`--dry-run`** — parse inputs, print counts, exit.

## Metrics

| Priority | Metric | Judge? | Threshold |
|---|---|---|---|
| P0 | Use-case ownership | optional pointwise | 90% |
| P1 | Determinism | ✓ pointwise | 70% |
| P1 | Overfitting / hardcoding | — | 90% |
| P1 | Use-case focus | — | 85% |
| P1 | Subagent substance | — | 85% |
| P1 | Instruction substance | ✓ pointwise | 80% |
| P1 | Action gating | — | 90% |

See `rubrics/*.md` for the exact definition of each.

## What gets evaluated

**Only the diff** — subagents / actions / instructions added or materially modified between `--before` and `--after`. Pre-existing content is ignored. If training also removed a subagent, that's reported but not scored.

## Which metrics run?

```
before + after + scenarios        → use_case_ownership, overfitting, use_case_focus,
                                     subagent_substance, action_gating
+ live judge (no --static-only)    → + determinism, instruction_substance,
                                       + judge-assisted ownership
```

Missing input → SKIPPED, not FAIL.

## Design principles

1. **Diff-first.** Pre-existing content is not training output; don't let it inflate or depress scores.
2. **Structural checks are static.** Hardcoding, substance, focus, gating are code-only.
3. **Meaning checks are judged.** Determinism (natural-language vs rule) and instruction-substance (decision rules present) need semantics; everything else is grammar.
4. **Partial credit over hard gates.** Scores are percentages; thresholds decide PASS/WARN/FAIL in the report.
5. **Pluggable parser.** JSON and YAML native; DSL via regex fallback; failing parse surfaces a loud SKIP, never a crash.
