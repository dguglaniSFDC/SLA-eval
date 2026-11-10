# Sibling Distinctness (P1)

**Judge template:** `pairwise`
**Priority:** P1
**Pass threshold:** 85%

## What's being measured

Across all pairs of sibling reasons under the same parent, the fraction that are meaningfully distinct. This is a **taxonomy-quality** check — "do the labels mean different things to a human router?" — not a classifier-confusion check.

## Formula

```
sibling_distinctness = count(verdict == "distinct") / count(sibling pairs)
```

Pairs where one side is `under_defined` (see below) are **not** counted as distinct or overlapping — they're flagged separately as a labeling problem that needs to be fixed before the pair can be scored. Only pairs within the same parent are evaluated.

## Pre-step

For each parent category `P`:
- Enumerate all pairs `(A, B)` of its direct children.
- Skip when `|children| == 1`.

## Judge inputs

- `<RUBRIC>` = this file's definition + protocol
- `<ITEM_A>` = `{id, name, description}` for sibling A
- `<ITEM_B>` = `{id, name, description}` for sibling B

## Mandatory judging protocol

Follow these steps in order. Do not skip ahead.

### Step 1 — Articulate each label's scope IN ISOLATION

Before comparing A and B, write a one-line scope for each:
- `A_scope.includes` — what A covers (one phrase)
- `A_scope.excludes` — what A deliberately does NOT cover, even though it sounds like it might (one phrase)
- Same for B

If you cannot articulate **both** `includes` and `excludes` for a label in one sentence each — the label is too vague to score. Set `under_defined: "<label name>"` and stop. This is a **labeling problem, not a sibling-overlap problem**. Example: `case support` ("every support case") has an `includes` but no meaningful `excludes` — it's under-defined.

### Step 2 — Mutual-exclusion test (positive test for distinctness)

Produce TWO concrete customer tickets:
- `A_only_ticket`: fits A and **clearly does not** fit B (because it violates B's `excludes`)
- `B_only_ticket`: fits B and **clearly does not** fit A (because it violates A's `excludes`)

If you can produce both tickets, verdict is `distinct`. Stop.

If you cannot produce one or both, continue to Step 3.

### Step 3 — Handling-difference test (only if Step 2 fails)

Would a typical ticket for A be routed, worked, or resolved differently from a typical ticket for B? Cite the **handling difference**: who owns it, what tool they use, what resolution looks like.

- If handling differs materially → `distinct`.
- If handling is the same → `overlapping`.

### Step 4 — Rejection guards

Before emitting your verdict, check against these rejections:

- **Conjunction trap.** If your reasoning for `overlapping` is "one ticket could touch both areas" (e.g. "customer calls about status AND wants escalation"), that is NOT overlap. Multi-topic tickets touch multiple reasons; this does not make labels mean the same thing. If this is your reasoning, override to `distinct` (or use the Step-3 handling test).
- **Shared-vocabulary trap.** If your reasoning cites a word that appears in both labels (`access`, `workflow`, `case`, `data`, `support`, `security`) as the only evidence, that is not overlap. Override to `distinct`.
- **Hallucinated-straddle trap.** If you had to invent a contrived edge-case ticket to find overlap, that is not overlap. A real taxonomy has edge cases; that is not the question. Override to `distinct`.

## Output

STRICT JSON matching the pairwise template. The judge must populate:

```json
{
  "verdict": "distinct" | "overlapping",
  "reason": "<=25 words, cite the handling difference or the real overlap",
  "overlap_examples": ["..."],
  "A_scope": {"includes": "...", "excludes": "..."},
  "B_scope": {"includes": "...", "excludes": "..."},
  "mutually_exclusive_tickets": {"A_only": "...", "B_only": "..."},
  "under_defined": null | "<label name>"
}
```

If `under_defined` is non-null, the pair is not scored (not distinct, not overlapping). If `verdict == "distinct"`, `overlap_examples` must be `[]`.

## Anchors (recalibrated)

> Generalize the *pattern*, not the vertical.

### distinct — different handling, boundary is crisp (Retail)
A: `Returns > Damaged in Transit — package arrives broken`.
B: `Returns > Wrong Item Shipped — wrong SKU received`.
`A.excludes`: "any return where the item is the one ordered but functional." `B.excludes`: "any return where the correct SKU arrived but was damaged."
`A_only`: "FedEx dropped my box, screen cracked, I want a replacement." `B_only`: "Got a blue sweater, I ordered red, send me red."
Verdict: `distinct` (Step 2 passes).

### distinct — labels look similar, but excludes are crisp
A: `case status and follow-up — customer asking about case progress`.
B: `case routing and escalation — moving a case to the right team or higher tier`.
`A.excludes`: "any request to change ownership, priority, or team assignment." `B.excludes`: "any inbound 'what is the state of my case' with no reassignment ask."
`A_only`: "Just checking in — any update on my ticket?" `B_only`: "Please escalate this to a tier-2 engineer."
Verdict: `distinct` (Step 2 passes). Multi-topic tickets ("update AND escalate") do not count as overlap — they touch two reasons.

### overlapping — handling is actually the same
A: `Billing > Invoice Question`.
B: `Patient Accounts > Invoice Clarification`.
Both go to the same billing clerk with the same resolution. No `A.excludes` that B doesn't also exclude.
Verdict: `overlapping`.

### under_defined — not a sibling problem, a labeling problem
A: `case support — anything that opens a case`.
B: `application troubleshooting — fixing broken functionality`.
`A.excludes`: "none — all support interactions open a case." A has no boundary.
Verdict: `under_defined: "case support"`. Do not score this pair.

## Report drill-down

Three sections:
1. **Overlapping pairs** (passed strict test) — merge candidates with cited handling similarity.
2. **Under-defined labels** — labels whose scope couldn't be articulated. These are labeling problems to fix before the sibling score is meaningful.
3. **Distinct count** — summary of the majority.
