import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieve import retrieve
from src.bm25_index import build_bm25_index, query_bm25
from src.config import fetch_all_chunks


def build_id_to_chunk_mapping(all_chunks):
    mapping = {}
    for chunk in all_chunks:
        mapping[chunk["id"]] = chunk
    
    return mapping

def rrf(dense_ranked, bm25_ranked, k=60):
    scores = {}
    for rank, doc_id in enumerate(dense_ranked, start=1):
        scores[doc_id] = scores.get(doc_id, 0) + 1/(k+rank)

    for rank, doc_id in enumerate(bm25_ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0) + 1/(k+rank)

    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))

def hybrid_retrieval(query: str,index, id_to_chunk:dict, dense_top_n:int=50, bm25_top_n:int=50, rrf_k:int=60, top_k:int=5):
    # 1. Dense retrieval
    points = retrieve(query, top_k=dense_top_n)
    dense_ranked = [str(doc.payload["id"]) for doc in points]

    # 2. BM25 Retrieval
    result_bm25 = query_bm25(index, query, bm25_top_n)
    bm25_ranked = [res[0] for res in result_bm25]

    # 3. Reciprocal rank fusion
    rrf_result = rrf(dense_ranked, bm25_ranked, rrf_k)

    final_result = []
    for doc_id, score in rrf_result[:top_k]:
        if doc_id not in id_to_chunk:
            raise KeyError(f"Index/Corpus mismatch: Chunk ID '{doc_id}' not found in the mapping")

        final_result.append({
            "score": score,
            "chunk": id_to_chunk[doc_id]
        })

    return final_result
        
def main():
    print("Fetching chunks from database...")
    all_chunks = fetch_all_chunks()
    
    print("Building BM25 index and ID mapping...")
    id_to_chunk = build_id_to_chunk_mapping(all_chunks)
    index = build_bm25_index(all_chunks)
    
    queries = [
        "what keyword args does model_dump take?",
        "how do I validate a nested Pydantic model?"
    ]
    
    for query in queries:
        print(f"\n--- Results for: '{query}' ---")
        
        results = hybrid_retrieval(
            query=query,
            index=index,
            id_to_chunk=id_to_chunk,
            dense_top_n=50,
            bm25_top_n=50,
            rrf_k=60,
            top_k=5
        )

        for rank, res in enumerate(results, start=1):
            print(f"[{rank}] Score: {res['score']:.4f} | ID: {res['id']}")
            print(f"Text snippet: {res['chunk']['text'][:100]}...\n")

if __name__ == "__main__":
    main()