# Reproducibility (P0)

**Judge template:** none — pure code
**Priority:** P0
**Pass threshold:** 90%

## What's being measured

Across two pipeline runs on the same conversation set, the percentage of conversations assigned the same contact reason both times.

## Formula

```
reproducibility = count(canon(a1[c]) == canon(a2[c])) / len(conversations)
```

Where `canon(reason_id)` canonicalizes reason IDs across runs — the pipeline may rename or restructure IDs between runs.

## Pre-step: cross-run reason canonicalization

- Embed `name + " — " + description` for every reason in run 1 and run 2.
- For each run-1 reason, find its nearest run-2 reason by cosine similarity.
- If `sim >= clustering.reason_canonicalization_threshold` (default 0.90), map them to the same canonical id.
- Reasons without a cross-run partner are treated as unique — any conversation assigned to such a reason counts as non-reproduced.

## Why no LLM

This is a count over structured data. Asking a judge adds noise and cost with no quality gain. The only semantic step (canonicalization) is handled by embeddings, which are more stable than a judge for near-identical descriptions.

## When skipped

If `assignments_run2.json` is missing, the metric is reported as `SKIPPED — second run not provided` and does not block overall PASS/FAIL. The report prompts the user to run the pipeline twice to enable this metric.

## Report drill-down

List up to 10 conversations where `a1 != a2` after canonicalization, with both assigned reasons shown. These are the pipeline's most unstable classification examples.
