---
name: sla-scenario-eval
description: Score an SLAgent DataPrep scenarios file against P0/P1 scenario-quality metrics. Expected per-scenario shape — goal, persona, userContextFacts, agentContextFacts, criteria, sampleSeeds, tags. Takes a contact-reason taxonomy (category, name), scenarios in that shape, and normalized transcripts. Use when the user says "evaluate scenarios", "score the scenario set", or "benchmark scenarios".
---

# SLA Scenario Evaluation

Scores one scenario set against eleven metrics. Expected per-scenario shape (see `examples/scenarios-sample.json`): `tags`, `goal`, `persona`, `userContextFacts`, `agentContextFacts`, `sampleSeeds`, `criteria`, `channel`.

P0 catches "this will break training"; P1 catches "this has rough edges but is usable".

| Priority | Metric | What it measures |
|---|---|---|
| P0 | **Conversation coverage** | % of conversations in the corpus represented by ≥1 scenario (goal + persona + context facts match the conversation's intent and flow). Catches scenario sets that only sample the easy half of the corpus. |
| P0 | **Scenario grounding** | % of scenarios whose customer situation (goal, persona, context) AND evaluation criteria both match real conversations. Catches fabricated scenarios. |
| P0 | **Scenario evaluability** | % of criteria that can be fairly passed from the scenario alone (static check, 5 block rules — see rubric). Tool input/output field mismatches report as warnings, not blocks. |
| P0 | **Goal-criteria fit** | % of criteria whose descriptions describe a step that logically serves the scenario's goal. Goal is ground truth; criteria are judged `fit` / `out_of_scope` / `mis_attached` / `contradicts_goal`. Catches criteria accidentally attached to the wrong scenario. |
| P0 | **Criteria completeness** | Avg per-scenario completeness for criteria (tool invoked / outcome stated / verification honored where applicable) on a 0–3 scale normalized to a percentage. |
| P0 | **Scenario uniqueness** | % of within-reason scenario pairs that are meaningfully distinct. A set padded with near-duplicates trains on a smaller, more biased corpus than the headline count suggests. |
| P1 | **Tag coverage** | % of taxonomy reasons with ≥1 scenario tagged to them. |
| P1 | **Verification-criteria coverage** | % of sensitive scenarios (invoice/credit/case/unlink/permissions) with a verification-gate criterion. |
| P1 | **Field completeness rate** | % of required fields (goal, persona, context facts, seeds, criteria, tags) that are actually populated — not just technically present with an empty list. |
| P1 | **Variation coverage** | % of distinct real-world situations (e.g., with/without photo, customer tier) represented by ≥1 scenario seed. |
| P1 | **Taxonomy tagging confidence** | % of scenarios confidently tagged to a single contact reason (confidence ≥ floor). The rest sit near a category boundary — low-confidence tags pollute both categories' rollups, so coverage, grounding, and uniqueness drift against the wrong denominator. |

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

| You have | Conv Cov | Grounding | Evaluability | Goal-Crit Fit | Criteria Compl | Uniqueness | Tag Cov | Verif Cov | Field Compl | Variation | Tagging Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scenarios + reasons | — | — | ✓ | — | ✓ | — | ✓ | ✓ | ✓ | — | — |
| + live judge | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
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

# Static-only (no judge calls — just Evaluability, Criteria completeness, Tag coverage, Verification coverage, Field completeness)
python harness/run.py --input ./runs/<run-name> --static-only
```

## Trigger phrases

- "evaluate scenarios at <path>"
- "score the scenario set"
- "benchmark scenarios"
- "run SLA scenario eval"

## Design principles

- **P0 = training-damage; P1 = polish.** A P0 failure means the scenario set will hurt training (fabricated, mis-attached, unjudgeable, under-sampled, duplicative). A P1 failure means the set has rough edges but is still usable.
- **Static vs judge**: five metrics (Tag coverage, Evaluability, Verification coverage, Criteria completeness, Field completeness) run with zero LLM calls. Judge is used where semantic reasoning is required (Grounding, Conversation coverage, Goal-criteria fit, Scenario uniqueness, Variation coverage, Tagging confidence).
- **Goal-criteria fit** uses the scenario's `goal` as ground truth and judges each criterion as `fit` / `out_of_scope` / `mis_attached` / `contradicts_goal`. Catches the pipeline bug where a well-written criterion is bolted onto the wrong scenario (e.g. a "retrieve order to support the price adjustment request" criterion attached to a cancel-refund scenario). See `rubrics/goal-criteria-fit.md`.
- **Conversation coverage is the inverse of Grounding.** Grounding iterates scenarios → shortlists transcripts → asks "is this scenario real?". Coverage iterates conversations → shortlists scenarios → asks "is this conversation represented?". Both are needed: a scenario set that passes grounding at 100% can still cover <50% of the corpus if it only samples the easy cases. Threshold is intentionally lower (80% vs grounding's 90%) because the long tail is expected.
- **Evaluability has 5 explicit block rules** (listed in `rubrics/evaluability.md`). A sixth rule — tool-input/output field mismatch — reports as a warning, not a block.
- **Sensitive scenarios** are detected by regex over goal/criteria descriptions (configurable in `config.json → sensitive_patterns`). Verification-gate criteria are detected by regex over criterion name/description (`verification_patterns`).
- **Rubrics in markdown**, one judge template per shape (same `pointwise.md`/`pairwise.md`/`grounded-match.md` as `sla-contact-reason-eval`).

## Pairs with

- [`transcript-normalize`](../transcript-normalize/) — produces the `conversations/*.json` this skill reads.
- [`sla-contact-reason-eval`](../sla-contact-reason-eval/) — same reasons.json / taxonomy.json works for both.
