# Grounded-match judge

Given a query, pick the single best candidate from the list — or declare no match.

## Rubric

{{rubric_body}}

## Query

{{query}}

## Candidates

```json
{{candidates_json}}
```

## Constraints

{{constraints}}

## Output

Return STRICT JSON only — no prose, no markdown fences. Keys defined by the rubric (default: `{match: yes|no, candidate_id, confidence, reason}`).
