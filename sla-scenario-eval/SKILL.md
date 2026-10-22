---
name: sla-scenario-eval
description: Score an SLAgent DataPrep scenarios file against P0/P1 scenario-quality metrics. Expected per-scenario shape — goal, persona, userContextFacts, agentContextFacts, criteria, sampleSeeds, tags. Takes a contact-reason taxonomy (category, name), scenarios in that shape, and normalized transcripts. Use when the user says "evaluate scenarios", "score the scenario set", or "benchmark scenarios".
---

# SLA Scenario Evaluation

Scores one scenario set against eleven metrics. Expected per-scenario shape (see `examples/scenarios-sample.json`): `tags`, `goal`, `persona`, `userContextFacts`, `agentContextFacts`, `sampleSeeds`, `criteria`, `channel`.

| Priority | Metric | What it measures |
|---|---|---|
| P0 | **Tag Coverage** | % of taxonomy reasons with ≥1 scenario tagged to them |
| P0 | **Scenario Grounding** | % of scenarios whose goal/persona/facts + criteria match real conversations |
| P0 | **Conversation Coverage** | % of real conversations in the corpus represented by ≥1 scenario (inverse of grounding — catches long-tail customer behavior the scenario set never represents) |
| P0 | **Scenario Evaluability** | % of criteria that can be fairly passed from the scenario alone (static check, 5 block rules) |
| P0 | **Goal-Criteria Fit** | % of criteria whose descriptions describe a step that logically serves the scenario's goal (catches scenario↔criteria mismatches — criteria accidentally attached to the wrong scenario) |
| P0 | **Verification-Criteria Coverage** | % of sensitive scenarios (invoice/credit/case/unlink/permissions) with a verification-gate criterion |
| P0 | **Criteria Completeness** | Avg per-scenario completeness (tool invoked / outcome stated / verification honored) on a 0–3 scale |
| P0 | **Field Completeness Rate** | % of required fields (goal, persona, context facts, seeds, criteria, tags) that are actually populated |
| P1 | **Variation Coverage** | % of real-world situation variants represented by ≥1 scenario seed (experimental) |
| P1 | **Scenario Uniqueness** | % of within-reason scenario pairs that are meaningfully distinct |
| P1 | **Taxonomy Tagging Confidence** | Flags scenarios tagged with low confidence to the current reason |

## Inputs expected

```
<run>/
  scenarios.json              # list of scenarios in the expected shape
  reasons.csv | reasons.json  # (category, contact_reason) rows, OR same shapes as sla-contact-reason-eval
  conversations/              # normalized transcripts (use transcript-normalize)
```

### Reasons — accepted shapes

**1. CSV** (`reasons.csv`, header required):
```csv
category,contact_reason
<Category A>,<Reason 1>
<Category A>,<Reason 2>
<Category B>,<Reason 3>
```

**2. JSON list of `{category, name}`** (`reasons.json`):
```json
[{"category": "<Category A>", "name": "<Reason 1>"}, ...]
```

**3. Full taxonomy.json** — same shape `sla-contact-reason-eval` uses.

Scenario tags are matched against reasons using the `"<Category>::<Contact Reason>"` convention, falling back to case-insensitive name-only match.

### Which metrics run with what you have

| You have | Tag Cov | Grounding | Conv Cov | Evaluability | Goal-Crit Fit | Verif. Cov | Criteria Compl | Field Compl | Variation | Uniqueness | Tagging Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scenarios + reasons | ✓ | — | — | ✓ | — | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| + live judge | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| + transcripts | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Missing inputs → metric is marked SKIPPED. All judge rubrics live in `rubrics/`; swap one, re-run.

## Running it

```bash
# Dry-run (no LLM calls, shows plan + which metrics will skip)
python harness/run.py --input ./runs/<run-name> --dry-run

# Full
python harness/run.py --input ./runs/<run-name>

# Single metric
python harness/run.py --input ./runs/<run-name> --metric evaluability

# Static-only (no judge calls — just Field Completeness, Evaluability, Tag Coverage, Verification Coverage)
python harness/run.py --input ./runs/<run-name> --static-only
```

## Trigger phrases

- "evaluate scenarios at <path>"
- "score the scenario set"
- "benchmark scenarios"
- "run SLA scenario eval"

## Design principles

- **Static vs judge**: five metrics (Tag Coverage, Evaluability, Verification Coverage, Criteria Completeness, Field Completeness) run with zero LLM calls. Judge is only used where semantic reasoning is required (Grounding, Conversation Coverage, Goal-Criteria Fit, Variation, Uniqueness, Tagging Confidence).
- **Goal-Criteria Fit** uses the scenario's `goal` as ground truth and judges each criterion as `fit` / `out_of_scope` / `mis_attached` / `contradicts_goal`. Catches the pipeline bug where a well-written criterion is bolted onto the wrong scenario (e.g. a "retrieve order to support the price adjustment request" criterion attached to a cancel-refund scenario). See `rubrics/goal-criteria-fit.md`.
- **Conversation Coverage is the inverse of Grounding.** Grounding iterates scenarios → shortlists transcripts → asks "is this scenario real?". Coverage iterates conversations → shortlists scenarios → asks "is this conversation represented?". Both are needed: a scenario set that passes grounding at 100% can still cover <50% of the corpus if it only samples the easy cases. Threshold is intentionally lower (80% vs grounding's 90%) because the long tail is expected.
- **Evaluability has 5 explicit block rules** (listed in `rubrics/evaluability.md`). A sixth rule — tool-input/output field mismatch — reports as a warning, not a block.
- **Sensitive scenarios** are detected by regex over goal/criteria descriptions (configurable in `config.json → sensitive_patterns`). Verification-gate criteria are detected by regex over criterion name/description (`verification_patterns`).
- **Rubrics in markdown**, one judge template per shape (same `pointwise.md`/`pairwise.md`/`grounded-match.md` as `sla-contact-reason-eval`).

## Pairs with

- [`transcript-normalize`](../transcript-normalize/) — produces the `conversations/*.json` this skill reads.
- [`sla-contact-reason-eval`](../sla-contact-reason-eval/) — same reasons.json / taxonomy.json works for both.
