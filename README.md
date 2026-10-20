# Claude Code skills — SLAgent evaluation

Four skills for scoring SLAgent DataPrep output end-to-end: transcript prep, taxonomy quality, scenario quality, and training-output (AgentScript) quality.

| Skill | Purpose |
|---|---|
| [`transcript-normalize`](transcript-normalize/) | Convert raw VTT/TXT/JSON/CSV transcripts into the canonical `{id, turns:[{role, text}]}` shape. |
| [`sla-contact-reason-eval`](sla-contact-reason-eval/) | Score a contact-reason taxonomy against Coverage, Evidence Backing, and Sibling Distinctness. |
| [`sla-scenario-eval`](sla-scenario-eval/) | Score a scenarios file against nine P0/P1 scenario-quality metrics (tag coverage, grounding, evaluability, verification coverage, criteria completeness, field completeness, variation, uniqueness, tagging confidence). |
| [`agentscript-eval`](agentscript-eval/) | Diff a before/after AgentScript and score the added material against seven structural + semantic metrics (ownership, determinism, hardcoding, focus, substance, instruction substance, action gating). |

## Quickstart — taxonomy eval

```bash
# 1. Normalize raw transcripts
python ~/.claude/skills/transcript-normalize/normalize.py \
  --input ~/Downloads/raw-transcripts \
  --out ./runs/<run-name>/conversations

# 2. Drop a reason list next to conversations/
cat > ./runs/<run-name>/reasons.txt <<EOF
<Reason 1>
<Reason 2>
<Reason 3>
EOF

# 3. Score
pip install -r ~/.claude/skills/sla-contact-reason-eval/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python ~/.claude/skills/sla-contact-reason-eval/harness/run.py \
  --input ./runs/<run-name> --bootstrap-descriptions

# 4. Read the report
cat ./runs/<run-name>/report.md
```

## Quickstart — scenario eval

```bash
# Scenarios + reasons (+ optional transcripts)
python ~/.claude/skills/sla-scenario-eval/harness/run.py \
  --scenarios ./scenarios.json \
  --reasons ./reasons.csv \
  --transcripts ./conversations/ \
  --out ./runs/<run-name>
```

Inputs expected: `scenarios.json`, `reasons.csv` or `reasons.json`, `conversations/` (optional, unlocks the grounding metric).

## Quickstart — AgentScript eval

```bash
python ~/.claude/skills/agentscript-eval/harness/run.py \
  --before ./scripts/before.json \
  --after  ./scripts/after.json \
  --scenarios ./scenarios.json \
  --reasons   ./reasons.csv \
  --out ./runs/<run-name>
```

Optional: `--static-only` skips LLM calls.

Each skill has its own README with full input shapes, options, and design notes.
