# Verification-Criteria Coverage (P0 — static)

**Judge template:** none — regex over criterion name/description.
**Pass threshold:** 95%

## What's being measured

Across all **sensitive** scenarios, the percentage with at least one criterion that asserts the verification gate.

## Sensitive scenario detection

A scenario is sensitive if its goal OR any criterion description matches any of `config.sensitive_patterns` (default: invoice, credit, refund, charge, payment, case, ticket, order, policy, prescription, unlink, remove, delete, permission, access, cancel, escalat, reset password). Covers payments/billing, record-mutations, access changes, and escalations across industries — tune per vertical.

## Verification criterion detection

A criterion is a verification gate if its name OR description matches any of `config.verification_patterns` (default: verify, confirm, validate, authenticat, cross-reference, match, lookup, verification).

## Formula

```
verification_coverage = count(sensitive scenarios with >=1 verification criterion) / count(sensitive scenarios)
```

Scenarios not flagged sensitive are excluded from both numerator and denominator.

## Report drill-down

- **Ungated sensitive scenarios**: every sensitive scenario with no verification criterion. Listed with the matched sensitive keyword and the suggested verification criterion to add.
