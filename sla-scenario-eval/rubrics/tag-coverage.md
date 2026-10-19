# Tag Coverage (P0 — static)

**Judge template:** none — set-membership check.
**Pass threshold:** 85%

## What's being measured

Across all contact reasons in the taxonomy, the percentage with at least one scenario tagged to them.

## Formula

```
tag_coverage = count(reasons with >=1 scenario) / count(reasons)
```

## Tag matching

Scenarios tag as `"<Category>::<Contact Reason>"`. Match in this order:
1. Exact `"<Category>::<Reason>"` string match.
2. Case-insensitive match on both sides of `::`.
3. Name-only case-insensitive match (fallback when category is missing on either side).

A scenario can be tagged to multiple reasons; it counts for each.

## Report drill-down

- **Uncovered reasons**: list every reason with zero scenarios. Highest-leverage data-gap signal.
- **Oversampled reasons**: reasons with >5× the median scenario count (hint: skew in generation).
