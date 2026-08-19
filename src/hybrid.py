import re

def rrf(dense_ranked, bm25_ranked, k=60):
    scores = {}
    for rank, doc_id in enumerate(dense_ranked, start=1):
        scores[doc_id] = scores.get(doc_id, 0) + 1/(k+rank)

    for rank, doc_id in enumerate(bm25_ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0) + 1/(k+rank)

    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))

def main():
    res1 = rrf(dense_ranked=["a", "b", "c"], bm25_ranked=["c", "a", "d"], k=60)
    print(res1)
    print("="*50)
    res2 = rrf(dense_ranked=["z"], bm25_ranked=["a"], k=60)
    print(res2)
    print("="*50)
    res3 = rrf(dense_ranked=["a", "b"], bm25_ranked=[], k=60)
    print(res3)

if __name__=="__main__":
     main()