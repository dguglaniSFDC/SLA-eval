# Overfitting / Hardcoding (P1 — static)

**Judge template:** none — regex over AgentScript body.
**Pass threshold:** 90%

## What's being measured

Among scenario-specific variables (order IDs, policy numbers, member IDs, appointment IDs, trip IDs, dollar amounts, dates, phone numbers, named individuals, verbatim quotes from scenario `sampleSeeds`), the percentage populated at **runtime** (as `${var}` / `{{slot}}` / fact references) rather than **hardcoded** from a scenario example.

## Detection

1. Collect every scenario's `sampleSeeds` values into a candidate-literal set.
2. For each literal in the AgentScript diff, check:
   - Does it match any seed value verbatim? → hardcoded
   - Does it match any `config.hardcode_marker_patterns` regex (e.g., `ORD-#`, `POL-#`, `MBR-#`, dollar amount, ISO date, 10+ digit number — tune per vertical)? → hardcoded
   - Is it inside a `${...}` / `{{...}}` / fact-reference wrapper? → templated (good)

## Formula

```
overfitting_score = 1 - (hardcoded_literals / (hardcoded_literals + templated_slots))
```

If the diff contains zero scenario-specific variables either way, score is `1.0` (vacuous pass, reported as such).

## Report drill-down

- Hardcoded literal → subagent → file location.
- Flagged: subagents with ≥3 hardcoded literals (likely training-set memorization).

## Illustrative examples (industry-agnostic)

> Examples span industries deliberately — the pattern (templated vs leaked literal) is what matters, not the specific identifier format.

- **Retail — hardcoded (bad):** `issueRefund(orderId="ORD-4471928", amount=129.99)` — order id and amount pulled verbatim from a seed.
- **Retail — templated (good):** `issueRefund(orderId=${customer.lastOrderId}, amount=${order.totalCharged})`.
- **Healthcare — hardcoded (bad):** `rescheduleAppointment(apptId="APT-55210", newDate="2026-10-30")`.
- **Healthcare — templated (good):** `rescheduleAppointment(apptId=${patient.upcomingAppointmentId}, newDate=${requestedDate})`.
- **Transportation — hardcoded (bad):** `adjustFare(tripId="TRP-998712", refundAmount=14.50)`.
- **Transportation — templated (good):** `adjustFare(tripId=${rider.activeTripId}, refundAmount=${surge.differential})`.
