# Claude Code skills — SLAgent evaluation

Four skills for scoring SLAgent DataPrep output end-to-end: transcript prep, taxonomy quality, scenario quality, and training-output (AgentScript) quality.

| Skill | Purpose |
|---|---|
| [`transcript-normalize`](transcript-normalize/) | Convert raw VTT/TXT/JSON/CSV transcripts into the canonical `{id, turns:[{role, text}]}` shape. |
| [`sla-contact-reason-eval`](sla-contact-reason-eval/) | Score a contact-reason taxonomy against Coverage, Evidence Backing, and Sibling Distinctness. |
| [`sla-scenario-eval`](sla-scenario-eval/) | Score a scenarios file against eleven P0/P1 scenario-quality metrics. P0 (training-damage): conversation coverage, scenario grounding, evaluability, goal-criteria fit, criteria completeness, scenario uniqueness. P1 (polish): tag coverage, verification-criteria coverage, field completeness, variation coverage, tagging confidence. |
| [`agentscript-eval`](agentscript-eval/) | Diff a before/after AgentScript and score the added material against seven structural + semantic metrics (use-case ownership, determinism, overfitting / industry-tied, use-case focus, subagent substance, instruction substance, action gating). |

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
# Scenarios + reasons (+ optional transcripts, + optional second run)
python ~/.claude/skills/sla-scenario-eval/harness/run.py \
  --input ./runs/<run-name>
```

Inputs expected: `scenarios.json`, `reasons.csv` or `reasons.json`, `conversations/` (optional), `scenarios_run2.json` (optional, unlocks Reproducibility).

## Quickstart — AgentScript eval

```bash
python ~/.claude/skills/agentscript-eval/harness/run.py \
  --before ./scripts/before.txt \
  --after  ./scripts/after.txt \
  --scenarios ./scenarios.json \
  --reasons   ./reasons.csv \
  --out ./runs/<run-name>
```

`--before` / `--after` accept JSON, YAML, or raw DSL (`.txt`); the parser auto-detects. `--static-only` skips LLM-backed metrics (determinism, overfitting, instruction substance) and runs only the structural checks.

Each skill has its own README with full input shapes, options, and design notes.
