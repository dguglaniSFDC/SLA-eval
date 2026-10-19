"""One function per metric. Each returns (score, details)."""
from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

from judge import Judge, JudgeCall


# ---------- helpers ----------

def _transcript_text(conversation: dict, max_chars: int = 12_000) -> str:
    turns = conversation.get("turns", [])
    text = "\n".join(f"[{i}] {t['role']}: {t['text']}" for i, t in enumerate(turns))
    return text[:max_chars]


def _parallel(fn, items, concurrency: int):
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(fn, item): item for item in items}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def _taxonomy_leaves(taxonomy: dict) -> list[dict]:
    reasons = taxonomy["reasons"]
    parent_ids = {r.get("parent_id") for r in reasons if r.get("parent_id")}
    return [r for r in reasons if r["id"] not in parent_ids]


# ---------- Coverage ----------

def coverage(conversations, taxonomy, judge: Judge, embedder, config) -> tuple[float, dict]:
    sample_n = min(config["sampling"]["coverage_extract_n"], len(conversations))
    sample = random.Random(43).sample(conversations, sample_n)

    def extract_one(conv):
        return judge.call(JudgeCall(
            template="pointwise",
            rubric="coverage",
            inputs={
                "item_json": {"transcript": _transcript_text(conv)},
                "evidence_block": "(no evidence — this is blind extraction)",
            },
        )) | {"conversation_id": conv["id"]}

    extracted = _parallel(extract_one, sample, config["concurrency"])
    descriptions = [e.get("one_line_description", "") for e in extracted]
    embeddings = embedder(descriptions)

    threshold = config["clustering"]["intent_sim_threshold"]
    clusterer = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - threshold,
        metric="cosine",
        linkage="average",
    )
    labels = clusterer.fit_predict(embeddings)

    reference_intents = []
    for cluster_id in set(labels):
        members = [extracted[i] for i, l in enumerate(labels) if l == cluster_id]
        center_idx = int(np.argmax(cosine_similarity(
            [embeddings[list(labels).index(cluster_id)]], embeddings).sum(axis=0)))
        medoid = members[0]
        reference_intents.append({
            "cluster_id": int(cluster_id),
            "intent_label": medoid.get("intent_label", ""),
            "one_line_description": medoid.get("one_line_description", ""),
            "support_count": len(members),
        })

    leaves = _taxonomy_leaves(taxonomy)
    candidates = [{"id": r["id"], "name": r["name"], "description": r["description"]} for r in leaves]

    def match_one(ri):
        result = judge.call(JudgeCall(
            template="grounded-match",
            rubric="coverage",
            inputs={
                "query": f"{ri['intent_label']} — {ri['one_line_description']}",
                "candidates_json": candidates,
                "constraints": "Match only to the deepest leaf whose description genuinely represents this intent. Reject surface-term matches.",
            },
        ))
        return {**ri, **result}

    matched = _parallel(match_one, reference_intents, config["concurrency"])
    yes = sum(1 for m in matched if m.get("match") == "yes")
    score = yes / len(matched) if matched else 0.0
    missing = [m for m in matched if m.get("match") == "no"]
    return score, {
        "reference_intent_count": len(reference_intents),
        "matched": yes,
        "missing_from_taxonomy": missing,
    }


# ---------- Evidence Backing ----------

def evidence_backing(reasons, conversations, judge: Judge, embedder, config) -> tuple[float, dict]:
    conv_texts = [_transcript_text(c, max_chars=2000) for c in conversations]
    conv_emb = embedder(conv_texts)
    reason_emb = embedder([f"{r['name']} — {r['description']}" for r in reasons])
    sim = cosine_similarity(reason_emb, conv_emb)
    k = config["sampling"]["evidence_top_k"]

    def eval_one(idx):
        r = reasons[idx]
        top_k_idx = np.argsort(-sim[idx])[:k]
        evidence = [{"id": conversations[i]["id"], "text": conv_texts[i]} for i in top_k_idx]
        verdict = judge.call(JudgeCall(
            template="pointwise",
            rubric="evidence-backing",
            inputs={
                "item_json": {"reason_id": r["id"], "name": r["name"], "description": r["description"]},
                "evidence_block": evidence,
            },
        ))
        return {"reason_id": r["id"], "name": r["name"], **verdict}

    results = _parallel(eval_one, list(range(len(reasons))), config["concurrency"])
    supported = sum(1 for r in results if r.get("score") == "supported")
    unsupported = [r for r in results if r.get("score") != "supported"]
    score = supported / len(results) if results else 0.0
    return score, {"total": len(results), "supported": supported, "candidate_removals": unsupported}


# ---------- Sibling Distinctness ----------

def sibling_distinctness(taxonomy, judge: Judge, config) -> tuple[float, dict]:
    reasons = taxonomy["reasons"]
    by_parent: dict[str, list[dict]] = {}
    for r in reasons:
        pid = r.get("parent_id") or "__root__"
        by_parent.setdefault(pid, []).append(r)

    pairs = []
    for pid, kids in by_parent.items():
        if len(kids) < 2:
            continue
        for a, b in combinations(kids, 2):
            pairs.append((pid, a, b))

    def eval_pair(entry):
        pid, a, b = entry
        verdict = judge.call(JudgeCall(
            template="pairwise",
            rubric="sibling-distinctness",
            inputs={
                "item_a": {"id": a["id"], "name": a["name"], "description": a["description"]},
                "item_b": {"id": b["id"], "name": b["name"], "description": b["description"]},
            },
        ))
        return {"parent_id": pid, "a_id": a["id"], "b_id": b["id"],
                "a_name": a["name"], "b_name": b["name"], **verdict}

    results = _parallel(eval_pair, pairs, config["concurrency"])
    distinct = sum(1 for r in results if r.get("verdict") == "distinct")
    overlapping = [r for r in results if r.get("verdict") == "overlapping"]
    score = distinct / len(results) if results else 1.0
    return score, {"pairs": len(results), "distinct": distinct, "merge_candidates": overlapping}
