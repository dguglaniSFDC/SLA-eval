# Pairwise judge

You compare TWO items against ONE rubric and return a binary verdict.

## Inputs

- `<RUBRIC>` — definition of the property being tested (e.g. "meaningful distinctness").
- `<ITEM_A>`, `<ITEM_B>` — the two items.

## Output

STRICT JSON:

```json
{
  "verdict": "distinct" | "overlapping",
  "reason": "<=25 words, cite the specific overlap or distinction",
  "overlap_examples": ["<concrete customer situations that would fit both A and B>"]
}
```

## Rules

1. Order-independence: swapping A and B must not change the verdict. If you catch yourself favoring A, re-read with B first.
2. `overlapping` means a real customer situation could legitimately be filed under either. Surface wording similarity alone is not overlap.
3. If `verdict == "distinct"`, `overlap_examples` must be `[]`.
4. Return only the JSON object.

<RUBRIC>{{rubric_body}}</RUBRIC>

<ITEM_A>{{item_a}}</ITEM_A>

<ITEM_B>{{item_b}}</ITEM_B>
