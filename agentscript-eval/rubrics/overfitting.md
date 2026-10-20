# Overfitting / Industry-Tied (P1 — judge-backed)

**Judge template:** pointwise.
**Pass threshold:** 90%

## What's being measured

Whether a subagent is **portable across industries**, or whether its prose, action references, or variable names reveal a specific vertical that would prevent it from being reused in another domain.

The failure mode this metric guards against: a subagent trained on retail scenarios leaks retail-specific entities (order IDs, product SKUs, store terms) into its instructions, so it can't be dropped into healthcare or telecom without a rewrite. A well-written subagent should use **generic nouns** — "customer", "account", "subscription", "order", "request", "verification" — not **industry-specific nouns** — "patient", "prescription", "policyholder", "VIN", "SKU", "appointment slot".

This is a semantic check, not a shape check. A dollar amount in guardrail prose ("never refund $0") is fine. The word "copay" is not.

## What counts as an industry marker

Any of the following, if they'd only make sense in one vertical:

- **Named brands or companies** mentioned verbatim (`Netflix`, `Comcast`, `USAA`).
- **Vertical-specific entity nouns**: `patient`, `policyholder`, `claimant`, `rider`, `member`, `beneficiary`, `cardholder`, `enrollee` — used as a role name (not just appearing once in example prose).
- **Vertical-specific resources**: `prescription`, `claim`, `appointment`, `trip`, `policy`, `plan`, `premium`, `copay`, `deductible`, `VIN`, `SKU`, `MRN`.
- **Regulatory or compliance terms** that only apply to one industry: `HIPAA`, `PHI`, `FINRA`, `SOX`, `TILA`, `KYC`.
- **Action names** that reference vertical resources: `LookupPolicyholder`, `RenewPrescription`, `AdjustFare`.

Not industry markers (ignore these):

- Generic verbs: `verify`, `confirm`, `refund`, `cancel`, `update`, `send`.
- Generic nouns: `customer`, `account`, `order`, `subscription`, `payment`, `request`, `agent`.
- Dollar amounts, dates, IDs in example prose — those are examples of values, not industry signals.
- The subagent's own name (even if it says `SubscriptionManagement`, that's just the subagent's identity).

## How to judge

1. Read the subagent's instructions, action references, and body text.
2. Can you tell what industry this subagent is from? If no → **industry_generic = true**.
3. If yes, note the inferred industry and the specific words/phrases that gave it away.
4. Err on the side of marking generic when the markers are weak or ambiguous — the metric is for catching clear leakage, not borderline nouns.

## Output

Return JSON with these fields:

```json
{
  "industry_generic": true | false,
  "inferred_industry": "retail" | "healthcare" | "telecom" | "insurance" | "...",
  "industry_markers": ["list", "of", "exact", "phrases", "found"],
  "reason": "one-sentence explanation"
}
```

- `industry_generic` is `true` iff the subagent could be reused in a different industry without any wording changes.
- `inferred_industry` is empty string if `industry_generic` is `true`.
- `industry_markers` is empty list if `industry_generic` is `true`.

## Report drill-down

- Industry-tied subagents listed with inferred industry and markers.
- Score = fraction of added subagents the judge marks generic.
