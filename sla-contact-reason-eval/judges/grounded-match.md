# Grounded-match judge

You decide whether a QUERY concept matches any CANDIDATE in a provided list.

Used by Coverage (does this corpus-derived intent match any taxonomy reason?) and reused anywhere else a "does X appear in the list Y" judgment is needed.

## Inputs

- `<QUERY>` — the concept to match (e.g. an intent extracted from a transcript).
- `<CANDIDATES>` — JSON array of `{id, name, description}` entries.
- `<CONSTRAINTS>` — optional rules (e.g. "match only if candidate is a leaf", "prefer specific over generic").

## Output

STRICT JSON:

```json
{
  "match": "yes" | "no",
  "candidate_id": "<id from CANDIDATES, or null if match == no>",
  "confidence": "high" | "medium" | "low",
  "reason": "<=25 words"
}
```

## Rules

1. A `yes` requires the candidate's description to actually represent the query — not merely overlap on surface terms. "Billing question" does not match "Credit for duplicate scan".
2. If multiple candidates fit, pick the most specific one (deepest leaf).
3. `confidence: low` is a signal the taxonomy is ambiguous for this query — still return the best match but mark it.
4. If `match == "no"`, `candidate_id` must be `null`.
5. Return only the JSON object.

<QUERY>{{query}}</QUERY>

<CANDIDATES>{{candidates_json}}</CANDIDATES>

<CONSTRAINTS>{{constraints}}</CONSTRAINTS>
