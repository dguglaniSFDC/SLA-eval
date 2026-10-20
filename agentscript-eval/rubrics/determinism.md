# Determinism (P1 — judge-backed)

**Judge template:** pointwise.
**Pass threshold:** 70%

## What's being measured

Among decision rules whose **conditions are known** (verified, tier, order age, status, plan, etc.), the percentage implemented as **deterministic AgentScript** (`if/else/run/transition/escalate/set`) rather than natural-language reasoning instructions.

## Pipeline

1. Collect every added decision rule across the diff. A decision rule = any criterion-derived branching logic encoded in the subagent instructions or body.
2. For each rule, classify its **condition type**:
   - **Known** — references `config.known_condition_signals` (verified, tier, status, plan, …) OR a scenario fact key.
   - **Open-ended** — judgment call, policy interpretation, tone-dependent.
3. Among **known-condition rules only**, classify its **encoding**:
   - **Deterministic** — expressed via `config.deterministic_verbs` in the AgentScript grammar.
   - **Natural language** — written as prose instructions, including `config.nl_reasoning_signals`.

## What counts as "deterministic encoding"

**The AgentScript grammar is narrow.** The instruction block (`instructions: ->`) is prose-only — bare identifiers, inline `run`, nested `if`, `else if`, and `&&` are rejected by the validator. Determinism is expressed exclusively on **action/transition definitions**, in these forms:

- `available when @variables.X==<value>` on an action or transition definition. Comparison operators: `==`, `!=`, `<=`, `>=`, `<`, `>`. Multiple conditions joined with `and`/`or` on a single line — never `&&`, never nested.
- `if @variables.X: transition to @subagent.Y` — a **single-line tail** on an action definition. One predicate, one branch, no `else`.

## What does NOT count — do not recommend any of these as a fix

- **Nothing inside `instructions: ->` counts.** The instruction block cannot contain `if`, `run <action>`, bare action names, or any control flow. It is prose only. Do not recommend lifting a predicate into instructions — the validator will reject it.
- **No `sets @variables.X` on actions.** Actions have only `label` and `description`; they cannot write variables as a side effect in this grammar. If a predicate depends on a variable, that variable has to be populated by some other mechanism outside the action definition.
- **No multi-branch `if/else if/else`.** The only `if` form is the single-line transition tail above. A three-way branch must become three separate action definitions, each with its own `available when`.
- **No nested `if` and no `&&`.** Use `and`/`or` on a single predicate line.
- **Renaming an action** to a verb like `confirmX`/`decideX` without a predicate does not make a rule deterministic.
- **Prose repetition.** Restating a policy in the instruction block alongside a gated action is redundant, not an improvement.

## Grammar-limit escape valve

Some branching rules exceed what one `available when` or one `if … transition` can express — for example, a four-way branch on a tier variable where each arm runs a different action with different parameter bindings. These rules are not scorable as deterministic within the current grammar. Classify them as:

- `encoding: "grammar_limit"` — the rule has a known predicate but the grammar cannot express the branching shape with a single gate. These are **excluded from the denominator** of the Determinism score and surfaced in a separate drill-down bucket called "Candidates for grammar extension."

### Unwritable-variable rule — also `grammar_limit`

A rule is also `grammar_limit` when the predicate it would need to test depends on an `@variables.X` that **nothing in the script writes to**. The input's `written_variables` field lists every variable that has a writer: either a `set @variables.X = @outputs.Y` on some action, or a `linked` declaration sourced from external context. These are the only variables available to a predicate.

If the only way to make a rule deterministic would be to gate on a variable not in `written_variables` (e.g., a user-stated payment method, tier, or free-form intent that no action captures), the rule is `grammar_limit`, not `natural_language`. The grammar has no primitive to extract a user utterance into a variable, so "add `available when @variables.X==Y`" is not an achievable fix — it is impossible, not merely absent.

Only recommend `available when @variables.X==Y` as a fix when `X` appears in `written_variables`. When writing the `reason` for a `natural_language` verdict, cite the specific `@variables.X` from `written_variables` that could be gated on.

The suggested fix in a `reason` field must only reference `available when`, `if … transition`, or `grammar_limit` — never `instructions_if`, never `run inside instructions`, never `sets`, never "add action X" as a standalone recommendation, and never gate on a variable not in `written_variables`.

## Formula

```
determinism = count(known-condition rules encoded deterministically) /
              count(known-condition rules whose shape is grammar-expressible)
```

Rules classified as `grammar_limit` are excluded from both numerator and denominator so the score reflects what the author could actually have done within the grammar, not what the grammar could in principle support.

## Why judged, not regex

Classifying `condition type` and `encoding type` requires reading the rule in context. A rule that says *"If the customer is verified, proceed; otherwise ask for ID"* could be a deterministic `if verified: run(...) else run(...)` block OR a prose paragraph telling the agent to think about it — only semantic reading tells.

## Output per rule (judge)

```json
{
  "condition_type": "known" | "open_ended",
  "encoding": "deterministic" | "natural_language" | "grammar_limit",
  "predicate_location": "action_available_when" | "action_if_tail" | "none",
  "reason": "<one sentence>"
}
```

**Hard constraints:**
- If `predicate_location` is `"none"`, `encoding` MUST be `"natural_language"` or `"grammar_limit"` — never `"deterministic"`.
- `predicate_location` may only be one of the two values above. The grammar has no `instructions_if` or `transition_when` form; those are not valid locations.
- If the rule's branching shape cannot be expressed with one `available when` predicate or one `if … transition` tail, set `encoding: "grammar_limit"` and explain why in `reason`.

## Report drill-down

- **Natural-language rules** — known-condition rules written as prose that could be lifted to `available when` or `if … transition`. Each entry pairs the judge's `reason` with a suggested fix drawn only from those two constructs.
- **Grammar-limit rules** — known-condition rules whose branching shape exceeds the grammar. Surfaced separately as "Candidates for grammar extension"; excluded from scoring.
- **Open-ended rules** — judgment calls / tone-dependent rules, reported for scenario-design feedback only.
