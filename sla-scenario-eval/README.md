# sla-scenario-eval

Evaluates SLAgent DataPrep scenarios against a contact-reason taxonomy on 11 SLA metrics.

Pair with `sla-contact-reason-eval` (which scores the taxonomy itself) and `transcript-normalize` (which normalizes raw call transcripts into the shape this skill ingests).

## When to invoke

Trigger phrases:
- "evaluate scenarios against contact reasons"
- "score scenario quality on SLAs"
- "run scenario eval"

## Inputs

- **`--scenarios`** (required) — scenarios file. JSON list OR `{"scenarios": [...]}`. Each scenario has `id, tags, goal, persona, userContextFacts, agentContextFacts, sampleSeeds, criteria, suggestedToolcalls?, channel`.
- **`--reasons`** (required) — contact-reason taxonomy. CSV with `category,contact_reason` headers OR JSON (`[{category, name, description?}, ...]`).
- **`--transcripts`** (optional) — directory of normalized transcripts (`.txt`, `.md`, `.json`). Required for the grounding metric; skipped otherwise.
- **`--static-only`** — skip judge-backed metrics.
- **`--dry-run`** — validate inputs and exit.

## Metrics

| Priority | Metric | Judge? | Threshold |
|---|---|---|---|
| P0 | Tag coverage | — | 85% |
| P0 | Scenario grounding | ✓ pointwise | 90% |
| P0 | Conversation coverage (inverse of grounding) | ✓ pointwise | 80% |
| P0 | Scenario evaluability | — (5 block rules) | 85% |
| P0 | Goal-criteria fit (scenario↔criteria mismatches) | ✓ pointwise | 85% |
| P0 | Verification-criteria coverage | — | 95% |
| P0 | Criteria completeness (0–3 scale) | — | 85% |
| P0 | Field completeness rate | — | 95% |
| P1 | Variation coverage (experimental) | ✓ two-stage | 85% |
| P1 | Scenario uniqueness (within-reason) | ✓ pairwise | 90% |
| P1 | Taxonomy tagging confidence | ✓ grounded-match | 70% |

See `rubrics/*.md` for exact definitions.

## Which metrics run?

```
scenarios + reasons                        → tag_coverage, evaluability, verification_coverage,
                                             criteria_completeness, field_completeness
+ --transcripts                            → + scenario_grounding, conversation_coverage
+ live judge (no --static-only)            → + goal_criteria_fit, uniqueness,
                                             variation_coverage, tagging_confidence
```

Anything missing reports SKIPPED, not FAIL.

## Install

```bash
cd ~/.claude/skills/sla-scenario-eval
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

Zero-dependency path: `--static-only --dry-run` works without installing anything.

## Run

```bash
python3 harness/run.py \
  --scenarios ./scenarios.json \
  --reasons ./reasons.csv \
  --transcripts ./conversations/ \
  --out ./runs/<run-name>
```

Outputs:
- `report.md` — table of scores + per-metric drill-downs.
- `scores.jsonl` — one JSON line per metric for downstream aggregation.

## File layout

```
sla-scenario-eval/
├── SKILL.md
├── README.md
├── config.json
├── requirements.txt
├── judges/
│   ├── pointwise.md
│   ├── pairwise.md
│   └── grounded-match.md
├── rubrics/
│   ├── tag-coverage.md
│   ├── grounding.md
│   ├── conversation-coverage.md
│   ├── evaluability.md
│   ├── goal-criteria-fit.md
│   ├── verification-coverage.md
│   ├── criteria-completeness.md
│   ├── field-completeness.md
│   ├── variation-coverage.md
│   ├── uniqueness.md
│   └── tagging-confidence.md
└── harness/
    ├── judge.py
    ├── static_metrics.py
    ├── judge_metrics.py
    ├── report.py
    └── run.py
```

## Design notes

- **Static metrics are code-only.** No LLM for structural checks (tag coverage, evaluability block rules, verification regex, field completeness, criteria 0–3 score).
- **Judge calls are cached** by sha256 of (template + rubric + inputs). Safe to rerun.
- **Within-reason uniqueness pairs cap at 28/reason** so the judge bill scales linearly, not quadratically.
- **Variation coverage is experimental.** Two-stage: blind extract `{situation_summary, variant_axes}`, Jaccard-cluster, report cluster count per reason. Threshold-sensitive — read the drill-down, not just the score.
