---
name: sla-contact-reason-eval
description: Score an SLAgent DataPrep run's contact-reason taxonomy against three metrics (Coverage, Evidence Backing, Sibling Distinctness) using LLM-as-judge. Takes a list of contact-reason names (optionally with descriptions/parents) plus a folder of normalized transcripts. Use when the user says "benchmark contact reasons", "evaluate the taxonomy", "score reasons", or points at a run directory.
---

# SLA Contact Reason Evaluation

Scores one DataPrep run against three P0/P1 contact-reason metrics.

| Priority | Metric | What it measures |
|---|---|---|
| P0 | **Coverage** | % of intents found in the corpus that have a matching reason in the taxonomy |
| P0 | **Evidence Backing** | % of reasons grounded in at least one real conversation |
| P1 | **Sibling Distinctness** | % of same-parent sibling-reason pairs that are meaningfully distinct |

Note on scope: this skill scores the taxonomy itself, not the pipeline's per-conversation assignments. If you need to grade pipeline outputs (precision / reproducibility), run a classifier separately and compare its picks offline — those metrics are intentionally out of scope here.

## Inputs expected

A directory with:

```
<run>/
  conversations/            # normalized transcripts — see Preparing transcripts below
  reasons.txt | reasons.json | taxonomy.json
```

### Reasons input — three accepted shapes

**1. Flat list of names** (`reasons.txt`, one per line):
```
<Reason 1>
<Reason 2>
<Reason 3>
```

**2. Flat JSON list** (`reasons.json`):
```json
["<Reason 1>", "<Reason 2>", "<Reason 3>"]
```

**3. Full taxonomy** (`taxonomy.json`) — only this shape unlocks Sibling Distinctness:
```json
{"reasons": [
  {"id": "r_01", "name": "<Child Reason>", "description": "...", "parent_id": "r_parent"},
  {"id": "r_parent", "name": "<Parent Category>", "description": "...", "parent_id": null}
]}
```

The harness auto-generates slug IDs and empty descriptions when only names are provided. Evidence Backing works on names alone but gives sharper results with descriptions — pass `--bootstrap-descriptions` to have the judge write one-line descriptions from the top-K retrieved transcripts before scoring.

### Which metrics run with what you have

| You have | Coverage | Evidence Backing | Sibling Distinctness |
|---|---|---|---|
| Just reason names + transcripts | ✓ | ✓ | — |
| + full `taxonomy.json` with parents | ✓ | ✓ | ✓ |

Missing parent IDs → Sibling Distinctness is flagged as SKIPPED in the report; the rest still run.

## Preparing transcripts

Transcripts must be in canonical shape (one JSON per conversation):

```json
{"id": "<file-stem>", "turns": [{"role": "customer"|"agent"|"<name>", "text": "..."}]}
```

Raw VTT/TXT/JSON/CSV won't work directly. Use the companion [`transcript-normalize`](../transcript-normalize/SKILL.md) skill:

```bash
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/raw-transcripts \
  --out ./runs/<run-name>/conversations \
  --role-map ./rules.yaml
```

The rules file is where the user tells the normalizer "phone-number-shaped speakers are the customer, named speakers are the agent" (or any other mapping). Default behavior already does that for Zoom VTTs.

## What the skill does

1. Reads `config.json` (model, concurrency, sample sizes, thresholds).
2. Loads reasons (auto-expanding names → taxonomy shape with slug IDs).
3. Embeds all transcripts once; caches to `.cache/`.
4. Runs each applicable metric (see table above). Each is one Python handler + one rubric file + one of three judge templates (pointwise / pairwise / grounded-match).
5. Writes `report.md` (grouped P0/P1, PASS/WARN/FAIL per metric, drill-down for failures) + `scores.jsonl` (for trending).

## Running it

```bash
# Full run
python harness/run.py --input ./runs/<run-name>

# Have the judge write descriptions from retrieved transcripts before scoring
python harness/run.py --input ./runs/<run-name> --bootstrap-descriptions

# Single metric for iteration
python harness/run.py --input ./runs/<run-name> --metric coverage

# Dry-run (no LLM calls, just show plan + cost estimate)
python harness/run.py --input ./runs/<run-name> --dry-run
```

## Trigger phrases

- "benchmark contact reasons at <path>"
- "evaluate the taxonomy for <run>"
- "score reasons" / "score the contact-reason taxonomy"
- "run SLA contact-reason eval"

## Design principles

- **Rubrics live in markdown** (`rubrics/*.md`). Each is self-contained: definition, scale, anchors. Edit a rubric, re-run — no Python changes.
- **One judge template per shape**: `pointwise.md`, `pairwise.md`, `grounded-match.md`. All metrics reuse these three.
- **Coverage stays blind** to the taxonomy during intent extraction — the whole point is to catch what the pipeline missed.
- **Report writes the exact wording from the metric table** so readers trust the number.

## Pairs with

- [`transcript-normalize`](../transcript-normalize/SKILL.md) — produces the canonical `conversations/*.json` files this skill reads.

See `harness/run.py` for the orchestrator and `rubrics/` for each metric's rubric.
