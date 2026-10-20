# Subagent Substance (P1 — static)

**Judge template:** none — structural check.
**Pass threshold:** 85%

## What's being measured

Among added subagents, the percentage with:
- **≥5 non-trivial instruction lines**, AND
- **≥2 real actions** (any parsed action that isn't a handoff/transition), AND
- **not a pure pass-through** (does not match `config.passthrough_signals` as the dominant behavior)

## Definitions

- **Non-trivial instruction line**: a line in `instructions` / `prompt` / `system` with ≥4 words, not a header, not a bullet of a role name.
- **Real action**: any action in the parser's `actions` list whose `type` is not a handoff verb (`handoff`, `transition`, `route`, `delegate`, `transfer`). The parser has already classified blocks as actions by structure (DSL `actions:` block or a verb-prefixed line); the metric trusts that and only filters out transitions. There is no verb whitelist — authors routinely name actions `renewSubscription`, `LookupAccountService`, etc., and the metric should count those as real.
- **Pure pass-through**: ≥50% of the subagent's body is `handoff|transition|route|delegate|transfer` directives and the only non-handoff logic is identity verification.

## Formula

```
substance = count(subagents passing all three checks) / count(added subagents)
```

## Report drill-down

- Thin subagents (fail ≥1 check) listed with which checks failed and the actual counts.
- Pass-through subagents listed separately (they may be legitimate routers — human review signal).
