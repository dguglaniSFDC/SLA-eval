# agentscript-eval

Evaluates AgentScript training output by diffing a **before** and **after** script and scoring the delta — what training added — against the scenarios that drove it. Seven metrics; five static (code-only), two judge-backed.

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
| `--static-only` | — | Skip judge-backed metrics (zero LLM cost). |
| `--dry-run` | — | Parse inputs, print counts, exit. |

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

See `rubrics/*.md` for exact definitions.

## What gets scored

**Only the training delta.** `compute_diff(before, after)` extracts:
- fully-added subagents, and
- added actions + instructions inside modified subagents.

Pre-existing content is ignored.

## Which metrics run?

```
before + after + scenarios            → use_case_ownership, overfitting,
                                         use_case_focus, subagent_substance,
                                         action_gating
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
  --out ./runs/<run-name>
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
├── rubrics/       7 metric definitions
├── harness/       parser.py, diff.py, judge.py,
│                  static_metrics.py, judge_metrics.py,
│                  report.py, run.py
└── examples/      before.json, after.json, scenarios.json, reasons.csv
```

## Design principles

- **Diff-first.** Only grade what training wrote. Pre-existing subagents are ignored (reported in the diff summary).
- **Structural checks are static.** Hardcoding, substance, focus, gating are all code-only.
- **Meaning checks are judged.** Determinism and instruction-substance need to tell `if verified → run(…)` from *"use your judgment to decide whether…"*; those two are pointwise LLM calls, cached by sha256(template+rubric+inputs).
- **Partial credit, not pass/fail.** Scores are percentages; the report applies thresholds for PASS/WARN/FAIL coloring.
- **Attribution.** Scenarios are attributed to added subagents by tag + name-token matching against the subagent body.
