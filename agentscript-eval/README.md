# agentscript-eval

Evaluates AgentScript training output by diffing a **before** and **after** script and scoring the delta — what training added — against the scenarios that drove it. Nine metrics; six static (code-only), two judge-backed, one routing-trace-driven.

Pair with `sla-contact-reason-eval` (taxonomy quality) and `sla-scenario-eval` (scenario quality).

## When to invoke

Trigger phrases:
- "evaluate agentscript"
- "score agentscript training"
- "diff before/after agentscript"
- "run agentscript eval"

## Inputs

| Flag | Required | Purpose |
|---|---|---|
| `--before` | ✓ | AgentScript prior to training (JSON / YAML / raw DSL). |
| `--after` | ✓ | AgentScript after training. |
| `--scenarios` | ✓ | Scenarios used for training (`id, tags, goal, persona, userContextFacts, agentContextFacts, sampleSeeds, criteria`). |
| `--reasons` | — | Contact-reason taxonomy (CSV `category,contact_reason` or JSON). |
| `--after-run2` | — | Second training run on identical inputs; enables Shape Stability. |
| `--routing-trace` | — | JSONL with `{scenario_id, first_hop_subagent, router_type, category}`; enables Routing Precision. |
| `--static-only` | — | Skip judge-backed metrics (zero LLM cost). |
| `--dry-run` | — | Parse inputs, print counts, exit. |

## Metrics

| Priority | Metric | Judge? | Threshold |
|---|---|---|---|
| P0 | Shape & structural stability | — | 90% |
| P0 | Use-case ownership | optional pointwise | 90% |
| P1 | Determinism | ✓ pointwise | 70% |
| P1 | Overfitting / hardcoding | — | 90% |
| P1 | Use-case focus | — | 85% |
| P1 | Subagent substance | — | 85% |
| P1 | Instruction substance | ✓ pointwise | 80% |
| P1 | Routing precision | — | 85% |
| P1 | Action gating | — | 90% |

See `rubrics/*.md` for exact definitions.

## What gets scored

**Only the training delta.** `compute_diff(before, after)` extracts:
- fully-added subagents, and
- added actions + instructions inside modified subagents.

Pre-existing content is ignored for the delta-based metrics. Carved exceptions:
- Shape stability compares full after-scripts (needs `--after-run2`).
- Routing precision scores the whole post-training router against ambiguous / multi-intent / OOS rows in the trace.

## Which metrics run?

```
before + after + scenarios            → use_case_ownership, overfitting,
                                         use_case_focus, subagent_substance,
                                         action_gating
+ --after-run2                         → + shape_structural_stability
+ --routing-trace                      → + routing_precision
+ live judge (no --static-only)        → + determinism, instruction_substance
```

Missing input → SKIPPED, not FAIL.

## Install & run

```bash
cd ~/.claude/skills/agentscript-eval
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...                 # only when NOT --static-only

python3 harness/run.py \
  --before ./scripts/before.json \
  --after  ./scripts/after.json \
  --scenarios ./scenarios.json \
  --reasons   ./reasons.csv \
  --after-run2 ./scripts/after_run2.json \
  --routing-trace ./traces/routing.jsonl \
  --out ./runs/2026-10-16
```

Dry run with example fixtures (no API key, no deps):
```bash
python3 harness/run.py \
  --before examples/before.json \
  --after  examples/after.json \
  --scenarios examples/scenarios.json \
  --reasons   examples/reasons.csv \
  --static-only --out /tmp/agentscript-eval-out
```

Outputs:
- `report.md` — scores table + per-metric drill-downs.
- `scores.jsonl` — one JSON line per metric for downstream aggregation.

## Routing-trace schema

```jsonl
{"scenario_id": "s003", "first_hop_subagent": "RefundAgent", "router_type": "HyperClassifier", "category": "ambiguous"}
{"scenario_id": "s004", "first_hop_subagent": "escalate",    "router_type": "HyperClassifier", "category": "out_of_scope"}
```

`category` ∈ `{ambiguous, multi_intent, out_of_scope, normal}`. Only non-normal rows score. OOS rows expect `first_hop_subagent ∈ {escalate, fallback}`.

## Parser

Three ingestion paths, tried in order:
1. **JSON** — `{subagents: [...]}` / `{subagents: {name: {...}}}` / list of subagents / single-subagent object.
2. **YAML** — same structure. Uses `pyyaml` if installed, else attempts JSON fallback.
3. **DSL regex** — looks for `subagent <Name>` headers and lines starting with a known action verb; collects `instructions:` and `actions:` block equivalents.

If parsing fails the metrics SKIP with a loud warning — they never crash.

## File layout

```
agentscript-eval/
├── SKILL.md
├── README.md
├── config.json
├── requirements.txt
├── judges/        pointwise.md, pairwise.md
├── rubrics/       9 metric definitions
├── harness/       parser.py, diff.py, judge.py,
│                  static_metrics.py, judge_metrics.py,
│                  report.py, run.py
└── examples/      before.json, after.json, scenarios.json, reasons.csv
```

## Design principles

- **Diff-first.** Only grade what training wrote. Pre-existing subagents are ignored (reported in the diff summary).
- **Structural checks are static.** Shape stability, hardcoding, substance, focus, gating, routing-trace comparisons are all code-only.
- **Meaning checks are judged.** Determinism and instruction-substance need to tell `if verified → run(…)` from *"use your judgment to decide whether…"*; those two are pointwise LLM calls, cached by sha256(template+rubric+inputs).
- **Partial credit, not pass/fail.** Scores are percentages; the report applies thresholds for PASS/WARN/FAIL coloring.
- **Attribution is pluggable.** `--routing-trace` is the authoritative subagent→scenarios map; without it, fallback uses tag + name-token matching against the subagent body.
