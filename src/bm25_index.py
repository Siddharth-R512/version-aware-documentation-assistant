import re
import json
from rank_bm25 import BM25Okapi
from typing import NamedTuple

from config import COLLECTION_NAME, fetch_all_chunks

class BM25Index(NamedTuple):
    ids: list[str]
    bm25: BM25Okapi
    chunks: list[dict]

def tokenize_identifier_preserving(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"[a-z0-9_]+", text.lower())

def build_bm25_index(chunks: list[dict]) -> BM25Index:
    assert len(chunks) == 3599, f"FATAL: EXPECTED 3599 chunks for BM25 but got only {len(chunks)}"

    ids = []
    tokenized_corpus = []
    empty_token_ids = []

    for chunk in chunks:
        chunk_id = chunk["id"]
        ids.append(chunk_id)
        text_content = chunk.get("text", "")
        tokens = tokenize_identifier_preserving(text_content)
        if not tokens:
            empty_token_ids.append(chunk_id)

        tokenized_corpus.append(tokens)

    if empty_token_ids:
        print(f"WARNING: Found {len(empty_token_ids)} chunks that tokenized to 0 tokens.")
        print(f"Offending IDs: {empty_token_ids}")

    print("Building BM25Okapi index over 3,599 text-only chunks...")
    return BM25Index(ids=ids, bm25=BM25Okapi(tokenized_corpus), chunks=chunks)

def query_bm25(index: BM25Index, query: str, n: int = 50) -> list[tuple[str, float, int]]:
    query_tokens = tokenize_identifier_preserving(query)
    scores = index.bm25.get_scores(query_tokens)

    # FIX 3: Filter out zero scores BEFORE slicing top-n, so 0.0 matches never enter RRF.
    scored_results = [
        (score, chunk_id) 
        for score, chunk_id in zip(scores, index.ids) 
        if score > 0.0
    ]
    
    # Sort by score descending
    scored_results.sort(key=lambda x: (-x[0], x[1]))

    # Slice top-n and format return payload
    top_results = []
    for rank, (score, chunk_id) in enumerate(scored_results[:n], start=1):
        top_results.append((chunk_id, score, rank))
        
    return top_results


def main():
    chunks = fetch_all_chunks()
    index = build_bm25_index(chunks=chunks)

    # Real question text: loaded from golden.jsonl, never hand-typed
    golden = {}
    with open("eval/golden.jsonl", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            golden[item["id"]] = item

    # Pool ids: verified via your id scan + audit log. Exact strings.
    PROBES = {
        "q047": [
            "v2::pydantic/main.py::BaseModel.model_dump::000",
            "v2::pydantic/main.py::BaseModel.model_dump_json::000",
            "v2::docs/concepts/serialization.md::Python mode::000",
            "v2::docs/concepts/serialization.md::Python mode::001",
        ],
        "q048": [
            "v2::pydantic/main.py::BaseModel.model_copy::000",
            "both::docs/migration.md::Changes to `pydantic.BaseModel`::000",
            "both::docs/migration.md::Changes to `pydantic.BaseModel`::001",
        ],
    }

    idx_of = {cid: i for i, cid in enumerate(index.ids)}

    for qid, target_ids in PROBES.items():
        question = golden[qid]["question"]
        q_tokens = tokenize_identifier_preserving(question)

        scores = index.bm25.get_scores(q_tokens)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], index.ids[i]))
        rank_of = {index.ids[i]: r for r, i in enumerate(order, start=1)}

        # Per-term scores: one get_scores call per unique query token
        per_term = {t: index.bm25.get_scores([t]) for t in set(q_tokens)}

        print(f"\n{'='*70}")
        print(f"{qid}: {question}")
        print(f"tokens: {q_tokens}")
        print(f"{'='*70}")

        for tid in target_ids:
            if tid not in idx_of:
                print(f"  !! NOT FOUND IN INDEX: {tid}")
                continue
            i = idx_of[tid]
            contribs = {t: per_term[t][i] for t in per_term if per_term[t][i] > 0}
            print(f"  {tid}")
            print(f"    rank: {rank_of[tid]}   total score: {scores[i]:.3f}")
            print(f"    term contributions: "
                  + ", ".join(f"{t}={s:.2f}" for t, s in
                              sorted(contribs.items(), key=lambda x: -x[1]))
                  if contribs else "    term contributions: NONE (no query term matches)")
            
if __name__ == "__main__":
    main()