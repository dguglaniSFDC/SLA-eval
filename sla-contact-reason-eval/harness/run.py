"""Orchestrator: load inputs, run metrics, write report.

Usage:
    python run.py --input ./runs/2026-10-14 [--metric coverage] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

METRIC_ORDER = [
    ("coverage", "P0"),
    ("evidence_backing", "P0"),
    ("sibling_distinctness", "P1"),
]


def _slug(name: str) -> str:
    import re as _re
    s = _re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"r_{s}" or "r_unnamed"


def load_reasons(run_dir: Path) -> dict:
    """Accept reasons.txt (one per line), reasons.json (list of names), or taxonomy.json (full)."""
    tx = run_dir / "taxonomy.json"
    if tx.exists():
        data = json.loads(tx.read_text())
        for r in data.get("reasons", []):
            r.setdefault("id", _slug(r["name"]))
            r.setdefault("description", "")
            r.setdefault("parent_id", None)
        return data

    rj = run_dir / "reasons.json"
    rt = run_dir / "reasons.txt"
    if rj.exists():
        names = json.loads(rj.read_text())
    elif rt.exists():
        names = [line.strip() for line in rt.read_text().splitlines() if line.strip()]
    else:
        raise FileNotFoundError(
            f"Expected taxonomy.json, reasons.json, or reasons.txt in {run_dir}"
        )
    seen: set[str] = set()
    reasons = []
    for n in names:
        rid = _slug(n)
        base = rid
        i = 2
        while rid in seen:
            rid = f"{base}_{i}"
            i += 1
        seen.add(rid)
        reasons.append({"id": rid, "name": n, "description": "", "parent_id": None})
    return {"reasons": reasons}


def load_run(run_dir: Path):
    conversations = [json.loads(p.read_text()) for p in sorted((run_dir / "conversations").glob("*.json"))]
    taxonomy = load_reasons(run_dir)
    return conversations, taxonomy


def bootstrap_descriptions(taxonomy, conversations, judge, embedder, config):
    """Fill in empty reason descriptions by having the judge summarize retrieved transcripts."""
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    from judge import JudgeCall

    reasons = taxonomy["reasons"]
    needs = [r for r in reasons if not r.get("description")]
    if not needs:
        return taxonomy

    conv_texts = []
    for c in conversations:
        turns = c.get("turns", [])
        text = "\n".join(f"{t['role']}: {t['text']}" for t in turns)
        conv_texts.append(text[:2000])
    conv_emb = embedder(conv_texts)
    name_emb = embedder([r["name"] for r in needs])
    sim = cosine_similarity(name_emb, conv_emb)
    k = config["sampling"]["evidence_top_k"]

    for idx, r in enumerate(needs):
        top = np.argsort(-sim[idx])[:k]
        evidence = [{"id": conversations[i]["id"], "text": conv_texts[i]} for i in top]
        result = judge.call(JudgeCall(
            template="pointwise",
            rubric="describe-reason",
            inputs={
                "item_json": {"name": r["name"]},
                "evidence_block": evidence,
            },
        ))
        r["description"] = result.get("description", "").strip()
    return taxonomy


def make_embedder(config):
    """Return a callable: list[str] -> np.ndarray. Swap in your preferred provider."""
    import numpy as np
    try:
        import openai
        client = openai.OpenAI()
        model = config["model"]["embedder"]

        def embed(texts):
            resp = client.embeddings.create(model=model, input=texts)
            return np.array([d.embedding for d in resp.data])
        return embed
    except Exception:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return lambda texts: model.encode(texts, convert_to_numpy=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Run directory")
    parser.add_argument("--metric", help="Run only this metric")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no LLM calls")
    parser.add_argument("--bootstrap-descriptions", action="store_true",
                        help="If reasons have no descriptions, have the judge write them from retrieved transcripts first.")
    args = parser.parse_args()

    run_dir = Path(args.input).resolve()
    config = json.loads((SKILL_ROOT / "config.json").read_text())

    conversations, taxonomy = load_run(run_dir)

    if args.dry_run:
        pairs = sum(len(kids) * (len(kids) - 1) // 2
                    for kids in _by_parent(taxonomy).values() if len(kids) >= 2)
        print(f"Conversations: {len(conversations)}")
        print(f"Reasons: {len(taxonomy['reasons'])}  (leaves: {_leaf_count(taxonomy)})")
        print(f"Has parent_id (needed for Sibling Distinctness): "
              f"{'yes' if any(r.get('parent_id') for r in taxonomy['reasons']) else 'no — will skip'}")
        print("Planned LLM calls:")
        print(f"  coverage (extract+match) ~{min(config['sampling']['coverage_extract_n'], len(conversations)) + 40}")
        print(f"  evidence_backing ....... {_leaf_count(taxonomy)}")
        print(f"  sibling_distinctness ... {pairs}")
        return

    import anthropic
    from judge import Judge
    from metrics import coverage, evidence_backing, sibling_distinctness
    from report import write_report
    client = anthropic.Anthropic()
    cache_dir = (run_dir / config["cache"]["dir"]) if config["cache"]["judge_calls"] else None
    judge = Judge(
        client=client,
        model=config["model"]["judge"],
        cache_dir=cache_dir,
        temperature=float(config.get("temperature", 0.0)),
    )
    embedder = make_embedder(config)

    if args.bootstrap_descriptions:
        taxonomy = bootstrap_descriptions(taxonomy, conversations, judge, embedder, config)
        (run_dir / "taxonomy.bootstrapped.json").write_text(json.dumps(taxonomy, indent=2))

    results: dict[str, dict] = {}
    want = {args.metric} if args.metric else {m for m, _ in METRIC_ORDER}

    if "coverage" in want:
        score, details = coverage(conversations, taxonomy, judge, embedder, config)
        results["coverage"] = {"score": score, "details": details, "priority": "P0",
                                "threshold": config["thresholds"]["coverage"]}

    if "evidence_backing" in want:
        leaves = [r for r in taxonomy["reasons"] if r["id"] not in {x.get("parent_id") for x in taxonomy["reasons"]}]
        score, details = evidence_backing(leaves, conversations, judge, embedder, config)
        results["evidence_backing"] = {"score": score, "details": details, "priority": "P0",
                                        "threshold": config["thresholds"]["evidence_backing"]}

    if "sibling_distinctness" in want:
        has_parents = any(r.get("parent_id") for r in taxonomy["reasons"])
        if not has_parents:
            results["sibling_distinctness"] = {"score": 0.0, "details": {"skipped": True,
                "reason": "no parent_id on any reason — provide full taxonomy.json"},
                "priority": "P1", "threshold": config["thresholds"]["sibling_distinctness"]}
        else:
            score, details = sibling_distinctness(taxonomy, judge, config)
            results["sibling_distinctness"] = {"score": score, "details": details, "priority": "P1",
                                                "threshold": config["thresholds"]["sibling_distinctness"]}

    write_report(run_dir, results)
    print(f"Wrote {run_dir / 'report.md'}")


def _by_parent(taxonomy):
    by_parent: dict = {}
    for r in taxonomy["reasons"]:
        by_parent.setdefault(r.get("parent_id") or "__root__", []).append(r)
    return by_parent


def _leaf_count(taxonomy):
    parent_ids = {r.get("parent_id") for r in taxonomy["reasons"] if r.get("parent_id")}
    return sum(1 for r in taxonomy["reasons"] if r["id"] not in parent_ids)


if __name__ == "__main__":
    main()
