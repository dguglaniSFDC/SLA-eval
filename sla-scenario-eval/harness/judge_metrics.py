"""Judge-backed metrics — grounding, variation coverage, uniqueness, tagging confidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from judge import Judge, JudgeCall

MAX_PAIRS_PER_REASON = 28


# ---------- small retrieval helpers ----------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25ish_rank(query: str, docs: list[tuple[str, str]], k: int = 5) -> list[tuple[str, str]]:
    """Cheap keyword retrieval for grounding. docs is [(doc_id, text), ...]."""
    q_tokens = set(_tokenize(query))
    scored: list[tuple[float, tuple[str, str]]] = []
    for doc_id, text in docs:
        d_tokens = _tokenize(text)
        if not d_tokens:
            continue
        hits = sum(1 for t in d_tokens if t in q_tokens)
        if not hits:
            continue
        score = hits / (len(d_tokens) ** 0.5)
        scored.append((score, (doc_id, text)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]


# ---------- 1. Scenario Grounding ----------

def grounding(scenarios: list[dict], transcripts: dict[str, str], judge: Judge) -> dict[str, Any]:
    docs = [(tid, text) for tid, text in transcripts.items()]
    results = []
    bucket = {"grounded": 0, "partial": 0, "ungrounded": 0}

    for s in scenarios:
        sid = s.get("id") or "<unknown>"
        query = (
            (s.get("goal") or "") + " " +
            " ".join((c.get("description") or "") for c in s.get("criteria") or [])
        )
        shortlist = _bm25ish_rank(query, docs, k=5)
        if not shortlist:
            results.append({"scenario": sid, "verdict": "ungrounded", "reason": "no transcripts matched keywords"})
            bucket["ungrounded"] += 1
            continue
        evidence_block = "\n\n---\n\n".join(f"[{tid}]\n{text[:3000]}" for tid, text in shortlist)
        verdict = judge.call(JudgeCall(
            template="pointwise",
            rubric="grounding",
            inputs={"item_json": s, "evidence_block": evidence_block},
        ))
        v = str(verdict.get("score", "ungrounded")).lower()
        if v not in bucket:
            v = "ungrounded"
        bucket[v] += 1
        results.append({"scenario": sid, "verdict": v, "detail": verdict})

    total = sum(bucket.values())
    score = (bucket["grounded"] + 0.5 * bucket["partial"]) / total if total else 0.0
    return {"score": score, "buckets": bucket, "per_scenario": results}


# ---------- 1b. Conversation Coverage (inverse of grounding) ----------

def _scenario_index_text(s: dict) -> str:
    parts = [
        s.get("goal") or "",
        s.get("persona") or "",
        " ".join(str(v) for v in (s.get("userContextFacts") or {}).values()),
        " ".join(str(v) for v in (s.get("agentContextFacts") or {}).values()),
        " ".join((c.get("name") or "") for c in s.get("criteria") or []),
    ]
    return " ".join(parts)


def conversation_coverage(
    scenarios: list[dict], transcripts: dict[str, str], judge: Judge, k: int = 5
) -> dict[str, Any]:
    """For each conversation, judge whether any scenario covers its intent + flow.

    Inverse of `grounding`: that one asks "does each scenario trace to a conversation",
    this one asks "does each conversation trace to a scenario". Catches long-tail
    customer behavior the scenario set never represents.
    """
    scenario_docs = [(s.get("id") or f"scn_{i}", _scenario_index_text(s)) for i, s in enumerate(scenarios)]
    scenario_by_id = {sid: s for (sid, _), s in zip(scenario_docs, scenarios)}

    results: list[dict] = []
    bucket = {"covered": 0, "partial": 0, "uncovered": 0}
    uncovered_examples: list[dict] = []

    for tid, text in transcripts.items():
        query = text[:2000]
        shortlist = _bm25ish_rank(query, scenario_docs, k=k)
        if not shortlist:
            results.append({"conversation": tid, "verdict": "uncovered", "reason": "no scenario keyword overlap"})
            bucket["uncovered"] += 1
            uncovered_examples.append({"conversation": tid, "reason": "no keyword overlap"})
            continue

        candidates_block = "\n\n---\n\n".join(
            f"[{sid}]\n{json.dumps({'goal': scenario_by_id[sid].get('goal'), 'persona': scenario_by_id[sid].get('persona'), 'criteria': [c.get('name') for c in scenario_by_id[sid].get('criteria') or []]}, indent=2)}"
            for sid, _ in shortlist
        )

        verdict = judge.call(JudgeCall(
            template="pointwise",
            rubric="conversation-coverage",
            inputs={
                "item_json": {"conversation_id": tid, "transcript": text[:3000]},
                "evidence_block": "CANDIDATE SCENARIOS:\n\n" + candidates_block,
            },
        ))
        v = str(verdict.get("score", "uncovered")).lower()
        if v not in bucket:
            v = "uncovered"
        bucket[v] += 1
        row = {
            "conversation": tid,
            "verdict": v,
            "scenario_match_id": verdict.get("scenario_match_id"),
            "reason": verdict.get("reason", ""),
        }
        results.append(row)
        if v == "uncovered":
            uncovered_examples.append(row)

    total = sum(bucket.values())
    score = (bucket["covered"] + 0.5 * bucket["partial"]) / total if total else 0.0
    return {
        "score": score,
        "buckets": bucket,
        "n_total": total,
        "per_conversation": results,
        "uncovered_examples": uncovered_examples[:50],
    }


# ---------- 2. Uniqueness (pairwise, within-reason) ----------

def _bucket_by_reason(scenarios: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for s in scenarios:
        for t in s.get("tags") or []:
            buckets.setdefault(t, []).append(s)
    return buckets


def uniqueness(scenarios: list[dict], judge: Judge) -> dict[str, Any]:
    buckets = _bucket_by_reason(scenarios)
    distinct = 0
    near_dup = 0
    pairs: list[dict] = []

    for tag, items in buckets.items():
        n = len(items)
        if n < 2:
            continue
        all_pairs = [(items[i], items[j]) for i in range(n) for j in range(i + 1, n)]
        capped = all_pairs[:MAX_PAIRS_PER_REASON]
        for a, b in capped:
            verdict = judge.call(JudgeCall(
                template="pairwise",
                rubric="uniqueness",
                inputs={"item_a": a, "item_b": b},
            ))
            v = str(verdict.get("verdict", "distinct")).lower()
            if "near" in v or "duplicate" in v:
                near_dup += 1
                pairs.append({"tag": tag, "a": a.get("id"), "b": b.get("id"), "verdict": verdict})
            else:
                distinct += 1

    total = distinct + near_dup
    score = distinct / total if total else 1.0
    return {"score": score, "n_distinct": distinct, "n_near_duplicate": near_dup, "near_dup_examples": pairs[:50]}


# ---------- 3. Tagging Confidence (grounded-match) ----------

def tagging_confidence(
    scenarios: list[dict], reasons: list[dict], floor: float, judge: Judge
) -> dict[str, Any]:
    """% of scenarios confidently tagged to a single contact reason (confidence ≥ floor).

    A low-confidence tag means the scenario sits near a category boundary — it
    pollutes BOTH categories' rollups (counted under one, missing from the other),
    so coverage/grounding/uniqueness drift against the wrong denominator.
    """
    mistags = []
    boundary = []
    confidences: list[float] = []
    confident = 0

    reason_candidates = [
        {"id": f"{r.get('category','')}::{r.get('name') or r.get('contact_reason')}", "category": r.get("category"), "name": r.get("name") or r.get("contact_reason"), "description": r.get("description", "")}
        for r in reasons
    ]

    for s in scenarios:
        current_tags = s.get("tags") or []
        verdict = judge.call(JudgeCall(
            template="grounded-match",
            rubric="tagging-confidence",
            inputs={
                "query": {
                    "goal": s.get("goal"),
                    "criteria": [c.get("name") for c in s.get("criteria") or []],
                    "current_tags": current_tags,
                },
                "candidates_json": reason_candidates,
                "constraints": "Pick the single best reason regardless of current tag. Return {best_id, confidence, reason}.",
            },
        ))
        best_id = verdict.get("best_id") or ""
        conf = float(verdict.get("confidence", 0.0))
        confidences.append(conf)

        matches_current = any(
            best_id.strip().lower() == t.strip().lower() for t in current_tags
        )
        if conf >= floor:
            confident += 1
        else:
            boundary.append({"scenario": s.get("id"), "confidence": conf, "suggested": best_id})
        if not matches_current and current_tags:
            mistags.append({"scenario": s.get("id"), "current": current_tags, "suggested": best_id, "confidence": conf})

    denom = len(scenarios)
    score = confident / denom if denom else 1.0
    return {
        "score": score,
        "n_confident": confident,
        "n_total": denom,
        "mistags": mistags,
        "boundary_cases": boundary,
        "mean_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
    }


# ---------- 4. Goal-Criteria Fit (per-criterion attribution check) ----------

VALID_FIT_VERDICTS = {"fit", "out_of_scope", "mis_attached", "contradicts_goal"}


def goal_criteria_fit(scenarios: list[dict], judge: Judge) -> dict[str, Any]:
    total_criteria = 0
    fit_criteria = 0
    per_scenario: list[dict] = []
    flagged: list[dict] = []
    buckets = {"fit": 0, "out_of_scope": 0, "mis_attached": 0, "contradicts_goal": 0}

    for s in scenarios:
        sid = s.get("id") or "<unknown>"
        criteria = s.get("criteria") or []
        if not criteria:
            continue

        item = {
            "id": sid,
            "goal": s.get("goal"),
            "criteria": [{"name": c.get("name"), "description": c.get("description")} for c in criteria],
        }

        verdict = judge.call(JudgeCall(
            template="pointwise",
            rubric="goal-criteria-fit",
            inputs={"item_json": item, "evidence_block": "treat the goal as ground truth; evaluate each criterion"},
        ))

        verdicts = verdict.get("verdicts") or []
        n_fit_here = 0
        for v in verdicts:
            total_criteria += 1
            vlabel = str(v.get("verdict", "")).lower()
            if vlabel not in VALID_FIT_VERDICTS:
                vlabel = "fit"
            buckets[vlabel] = buckets.get(vlabel, 0) + 1
            if vlabel == "fit":
                fit_criteria += 1
                n_fit_here += 1
            else:
                flagged.append({
                    "scenario": sid,
                    "goal": s.get("goal"),
                    "criterion": v.get("name"),
                    "verdict": vlabel,
                    "reason": v.get("reason", ""),
                })

        per_scenario.append({"scenario": sid, "n_fit": n_fit_here, "n_total": len(verdicts) or len(criteria)})

    score = fit_criteria / total_criteria if total_criteria else 1.0
    return {
        "score": score,
        "n_fit": fit_criteria,
        "n_total": total_criteria,
        "buckets": buckets,
        "flagged": flagged,
        "per_scenario": per_scenario,
    }


# ---------- 5. Variation Coverage (experimental) ----------

def _simple_cluster(fingerprints: list[dict], threshold: float = 0.6) -> list[list[int]]:
    """Jaccard-based greedy clustering on `variant_axes` + `situation_summary` tokens."""
    clusters: list[list[int]] = []
    cluster_sets: list[set] = []
    for i, fp in enumerate(fingerprints):
        axes = fp.get("variant_axes") or []
        axes_strs = []
        for a in axes:
            if isinstance(a, str):
                axes_strs.append(a)
            elif isinstance(a, dict):
                axes_strs.append(" ".join(str(v) for v in a.values() if v))
            else:
                axes_strs.append(str(a))
        tokens = set(_tokenize(fp.get("situation_summary", "") + " " + " ".join(axes_strs)))
        placed = False
        for ci, cset in enumerate(cluster_sets):
            inter = len(tokens & cset)
            union = len(tokens | cset)
            if union and inter / union >= threshold:
                clusters[ci].append(i)
                cluster_sets[ci] = cset | tokens
                placed = True
                break
        if not placed:
            clusters.append([i])
            cluster_sets.append(tokens)
    return clusters


def variation_coverage(scenarios: list[dict], reasons: list[dict], judge: Judge) -> dict[str, Any]:
    by_reason: dict[str, list[dict]] = {}
    for s in scenarios:
        for t in s.get("tags") or []:
            by_reason.setdefault(t, []).append(s)

    report = []
    coverages = []
    for tag, items in by_reason.items():
        fingerprints = []
        for s in items:
            fp = judge.call(JudgeCall(
                template="pointwise",
                rubric="variation-coverage",
                inputs={"item_json": s, "evidence_block": "stage=blind-extract"},
            ))
            fingerprints.append(fp)
        clusters = _simple_cluster(fingerprints)
        cov = len(clusters) / max(1, len(items))
        coverages.append(cov)
        report.append({"tag": tag, "n_scenarios": len(items), "n_clusters": len(clusters), "coverage": cov})

    overall = sum(coverages) / len(coverages) if coverages else 0.0
    return {"score": overall, "per_tag": report, "note": "experimental; sensitive to the clustering threshold"}


