# sla-contact-reason-eval

Score an SLAgent DataPrep run's contact-reason taxonomy against three metrics using LLM-as-judge.

| Priority | Metric | What it measures |
|---|---|---|
| P0 | **Coverage** | % of intents in the corpus that have a matching taxonomy reason |
| P0 | **Evidence Backing** | % of reasons grounded in at least one real conversation |
| P1 | **Sibling Distinctness** | % of same-parent sibling pairs that are meaningfully distinct |

Scope note: this skill scores the *taxonomy*, not the pipeline's per-conversation picks. Precision / reproducibility of pipeline outputs is out of scope — grade those separately against a classifier run.

## Install

```bash
pip install -r ~/.claude/skills/sla-contact-reason-eval/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...        # optional — otherwise sentence-transformers is used locally
```

The skill lives at `~/.claude/skills/sla-contact-reason-eval/`. Claude Code loads it automatically.

## Inputs

Point `--input` at a directory with:

```
<run>/
  conversations/            # normalized transcripts (use transcript-normalize)
  reasons.txt | reasons.json | taxonomy.json
```

### Reasons — three accepted shapes

**1. Flat list of names** (`reasons.txt`):
```
<Reason 1>
<Reason 2>
<Reason 3>
```

**2. JSON list** (`reasons.json`):
```json
["<Reason 1>", "<Reason 2>"]
```

**3. Full taxonomy** (`taxonomy.json`) — only this unlocks Sibling Distinctness:
```json
{"reasons": [
  {"id": "r_01", "name": "<Child Reason>", "description": "...", "parent_id": "r_parent"},
  {"id": "r_parent", "name": "<Parent Category>", "description": "...", "parent_id": null}
]}
```

### What runs with what you have

| You have | Coverage | Evidence Backing | Sibling Distinctness |
|---|---|---|---|
| Reason names + transcripts | ✓ | ✓ | — |
| + full `taxonomy.json` with parents | ✓ | ✓ | ✓ |

Missing parent IDs → Sibling Distinctness is marked `SKIPPED` in the report; the rest still run.

## Preparing transcripts

Raw VTT/TXT/CSV must be normalized first. Use the companion skill:

```bash
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/raw-transcripts \
  --out ./runs/<run-name>/conversations
```

See [`../transcript-normalize/README.md`](../transcript-normalize/README.md).

## Usage

```bash
# Dry-run (no LLM calls, shows plan + which metrics will skip)
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py --input ./runs/<run-name> --dry-run

# Full run
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py --input ./runs/<run-name>

# Bootstrap descriptions when you only have names
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py --input ./runs/<run-name> --bootstrap-descriptions

# Single metric
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py --input ./runs/<run-name> --metric coverage
```

**Outputs** (written back into the run directory):
- `report.md` — summary table + per-metric drill-downs (missing intents, candidate removals, merge candidates)
- `scores.jsonl` — one row per metric for trending across runs
- `.cache/` — judge-call cache (keyed by rubric + inputs; delete to re-score)

## End-to-end example

```bash
# 1. Normalize raw Zoom VTTs
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/OneDrive_1_6-18-2026 \
  --out ./runs/<run-name>/conversations

# 2. Drop the reason list
cat > ./runs/<run-name>/reasons.txt <<EOF
<Reason 1>
<Reason 2>
<Reason 3>
EOF

# 3. Dry-run to confirm what will run
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py --input ./runs/<run-name> --dry-run

# 4. Score (bootstrap descriptions from retrieved transcripts first)
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py \
  --input ./runs/<run-name> --bootstrap-descriptions

# 5. Read the report
cat ./runs/<run-name>/report.md
```

## Design principles

- **Rubrics live in markdown** (`rubrics/*.md`). Each is self-contained: definition, scale, anchors. Edit a rubric, re-run — no Python changes.
- **One judge template per shape**: `pointwise.md`, `pairwise.md`, `grounded-match.md`. All metrics reuse these three.
- **Coverage stays blind** to the taxonomy during intent extraction — the whole point is catching what the pipeline missed.
- **Caching is content-addressed**: `sha256(template + rubric + inputs)`. Same inputs → cached result; change a rubric → fresh scoring.

## Files

```
sla-contact-reason-eval/
  SKILL.md                      # trigger phrases + overview (loaded by Claude Code)
  config.json                   # models, concurrency, sample sizes, thresholds
  requirements.txt
  harness/
    run.py                      # orchestrator — CLI entry point
    judge.py                    # single Claude caller + cache
    metrics.py                  # one function per metric
    report.py                   # writes report.md + scores.jsonl
  judges/
    pointwise.md                # judge-one-item template
    pairwise.md                 # compare-two-items template
    grounded-match.md           # query-vs-candidates template
  rubrics/
    coverage.md
    evidence-backing.md
    sibling-distinctness.md
    describe-reason.md          # used by --bootstrap-descriptions
```

## Pairs with

- [`transcript-normalize`](../transcript-normalize/) — produces the `conversations/*.json` files this skill reads.
