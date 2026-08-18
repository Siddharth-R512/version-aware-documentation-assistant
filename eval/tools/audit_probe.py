# import sys
# from pathlib import Path
# PROJECT_ROOT = Path(__file__).resolve().parents[1]   # ..\Sid-Projects\version-aware-document-assistant
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import COLLECTION_NAME, get_qdrant_client
# import json
# from eval.run import fetch_all_chunks, resolve_evidence  # whatever your resolver fn is named

# client = get_qdrant_client()
# chunks = fetch_all_chunks(client=client)

# golden = [json.loads(line) for line in open("eval/golden.jsonl", encoding="utf-8")]

# def show(qid):
#     item = next(g for g in golden if g["id"] == qid)
#     scope = item["gt_version_scope"]
    
#     print("=" * 80)
#     print(f"QUESTION [{qid}]: {item['question']}")
#     print("SCOPE:", scope)
    
#     # Do not pool sets. Iterate and print per evidence key.
#     for ev_string in item["gt_evidence"]:
#         print("\n" + "*" * 70)
#         print(f"EVIDENCE KEY: {ev_string}")
#         print("*" * 70)
        
#         resolved_chunk_ids = resolve_evidence(ev_string, chunks, scope)
        
#         if not resolved_chunk_ids:
#             print(">>> NO CHUNKS RESOLVED FOR THIS KEY <<<")
#             continue
            
#         for cid in resolved_chunk_ids:
#             c = next((ch for ch in chunks if ch["id"] == cid), None)
#             if c:
#                 print("-" * 70)
#                 print(f"RESOLVED: {cid} | version: {c['version']} | type: {c['chunk_type']}")
#                 print(c["text"][:200])

# qids = ["q046", "q013", "q026", "q001", "q003"]
# for i in qids:
#     show(i)

# target_cids = [
#     "v2::pydantic/functional_validators.py::field_validator::000",
#     "v2::pydantic/functional_validators.py::field_validator::001",
#     "v2::pydantic/functional_validators.py::field_validator::002",
#     "v2::pydantic/functional_validators.py::field_validator::003"
# ]

# print("DIAGNOSTIC: header_path and symbol_name for q046 code chunks")
# print("=" * 70)
# for cid in target_cids:
#     c = next((ch for ch in chunks if ch["id"] == cid), None)
#     if c:
#         print(f"ID:          {c['id']}")
#         print(f"header_path: {c.get('header_path', 'KEY NOT FOUND')}")
#         print(f"symbol_name: {c.get('symbol_name', 'KEY NOT FOUND')}")
#         print("-" * 70)

# import sys
# import csv
# import json
# from pathlib import Path

# # 1. Setup project path to import custom modules
# PROJECT_ROOT = Path(__file__).resolve().parents[1]   # Adjust if your script is in a different depth
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client
# from eval.run import fetch_all_chunks, resolve_evidence

# CSV_FILE_PATH = "eval/results/phase1_baseline.csv"  # <-- Update this to your actual CSV file name
# GOLDEN_JSONL_PATH = "eval/golden.jsonl"

# def main():
#     # 2. Parse the CSV file to get the old resolved counts (P1)
#     old_counts = {}
#     try:
#         with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 # Store the count as an integer, keyed by id
#                 old_counts[row['id']] = int(row['resolved_gt_count'])
#     except FileNotFoundError:
#         print(f"Error: Could not find CSV file at {CSV_FILE_PATH}")
#         return

#     # 3. Load chunks and golden set for the new computation (P3)
#     print("Fetching chunks from Qdrant... (This might take a moment)")
#     client = get_qdrant_client()
#     chunks = fetch_all_chunks(client=client)

#     golden = [json.loads(line) for line in open(GOLDEN_JSONL_PATH, encoding="utf-8")]

#     # 4. Process and print the comparison
#     print("\nID     | Old resolved count (P1) | New Resolved count (P3)")
#     print("-" * 58)

#     for item in golden:
#         qid = item["id"]
#         scope = item.get("gt_version_scope", "any")
        
#         # Calculate new resolved count (P3)
#         new_resolved_chunk_ids = set()
#         for ev_string in item.get("gt_evidence", []):
#             new_resolved_chunk_ids.update(resolve_evidence(ev_string, chunks, scope))
        
#         new_count = len(new_resolved_chunk_ids)
        
#         # Retrieve old count (P1) - default to 'N/A' if the ID wasn't in the CSV
#         old_count = old_counts.get(qid, "N/A")
        
#         # Print the formatted row
#         print(f"{qid:<6} | {old_count:<23} | {new_count}")

# if __name__ == "__main__":
#     main()


# import sys
# import json
# from pathlib import Path

# # Adjust pathing as necessary
# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client
# from eval.run import fetch_all_chunks

# # IMPORT YOUR RESOLVERS (Adjust import paths/names as needed)
# from eval.run import resolve_evidence_old  # The old version with the text branch
# from eval.run import resolve_evidence      # The new v2 version

# def main():
#     client = get_qdrant_client()
#     chunks = fetch_all_chunks(client=client)
#     golden = [json.loads(line) for line in open("eval/golden.jsonl", encoding="utf-8")]

#     print(f"{'ID':<6} | {'Old Resolver Count':<20} | {'New Resolver Count (v2)':<25} | {'Delta'}")
#     print("-" * 65)

#     zero_hit_list = []
    
#     for item in golden:
#         qid = item["id"]
#         scope = item.get("gt_version_scope", "any")
        
#         # Collect sets for both resolvers
#         old_set = set()
#         new_set = set()
        
#         try:
#             for ev in item.get("gt_evidence", []):
#                 old_set.update(resolve_evidence_old(ev, chunks, scope))
#                 new_set.update(resolve_evidence(ev, chunks, scope))
#         except ValueError as e:
#             print(f"{qid:<6} | {str(e)}")
#             continue

#         old_count = len(old_set)
#         new_count = len(new_set)
#         delta = new_count - old_count
        
#         # Formatting for easy reading
#         delta_str = str(delta) if delta == 0 else f"{delta}"
#         if new_count == 0 and old_count > 0:
#             zero_hit_list.append(qid)
            
#         print(f"{qid:<6} | {old_count:<20} | {new_count:<25} | {delta_str}")

#     print("\n" + "=" * 65)
#     print("WARNING: The following IDs dropped to ZERO chunks with the new resolver.")
#     print("These keys were being carried solely by text-mentions and must be re-pointed:")
#     print(", ".join(zero_hit_list) if zero_hit_list else "None! All GT keys are perfectly intact.")

# if __name__ == "__main__":
#     main()

# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client
# from eval.run import fetch_all_chunks, resolve_evidence

# client = get_qdrant_client()
# chunks = fetch_all_chunks(client=client)

# print("=== Checking q037: Serializers ===")
# q037_key = "docs/concepts/serialization.md :: Serializers"
# res = resolve_evidence(q037_key, chunks, "v2")

# found_target = False
# for cid in res:
#     c = next((ch for ch in chunks if ch["id"] == cid), None)
#     if c:
#         text_lower = c["text"].lower()
#         if "timestamp" in text_lower or "unix" in text_lower or "datetime" in text_lower:
#             print(f"\n[POTENTIAL MATCH] {cid}:")
#             print(c["text"][:600])
#             print("-" * 50)
#             found_target = True

# if not found_target:
#     print("\nWARNING: Searched all chunks under 'Serializers'. Could not find 'timestamp', 'unix', or 'datetime'.")
# print(f"Total chunks in pool: {len(res)}")

# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client
# from eval.run import fetch_all_chunks

# client = get_qdrant_client()
# chunks = fetch_all_chunks(client=client)

# print("=== Scanning corpus for q037 answer (unix/timestamp) ===")
# hit_count = 0
# for c in chunks:
#     # q037 is a v2 question, so filter out v1-only chunks
#     if c.get("version", "both") not in {"v2", "both"}:
#         continue
        
#     text_lower = c.get("text", "").lower()
#     if "timestamp" in text_lower or "unix" in text_lower:
#         hit_count += 1
#         print(f"\n[MATCH {hit_count}] ID: {c.get('id')}")
#         print(f"File: {c.get('source_file')}")
#         print(f"Header Path: {c.get('header_path')}")
#         print(c.get("text")[:400])
#         print("-" * 70)

# print(f"\nTotal corpus hits: {hit_count}")

# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client
# from eval.run import fetch_all_chunks, resolve_evidence

# client = get_qdrant_client()
# chunks = fetch_all_chunks(client=client)

# print("=== CLASS C: model_dump containment check ===")
# # Testing if BaseModel.model_dump sweeps BaseModel.model_dump_json
# dump_pool = resolve_evidence("pydantic/main.py :: BaseModel.model_dump", chunks, "v2")
# for cid in dump_pool:
#     print(f"Resolved: {cid}")

# print("\n=== CLASS D: strict_mode.md investigation ===")
# strict_chunks = [c for c in chunks if 'strict_mode' in c.get('source_file', '')]
# print(f"Total chunks containing 'strict_mode' in source_file: {len(strict_chunks)}")

# if strict_chunks:
#     print(f"Sample source_file verbatim: '{strict_chunks[0].get('source_file')}'")
#     print(f"Sample header_path: {strict_chunks[0].get('header_path')}")
# else:
#     print("CRITICAL: File 'strict_mode' is entirely missing from the chunked corpus.")


# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.config import get_qdrant_client, fetch_all_chunks

# client = get_qdrant_client()
# chunks = fetch_all_chunks(client=client)

# print("=== CLASS C: main.py headers ===")
# targets = ["def model_dump(", "def model_copy(", "def model_rebuild("]
# for c in chunks:
#     if c.get("source_file") == "pydantic/main.py":
#         text = c.get("text", "")
#         if any(t in text for t in targets):
#             print(f"ID: {c.get('id')} | Header path: {c.get('header_path')}")

# print("\n=== CLASS D: strict_mode.md headers ===")
# seen_headers = set()
# for c in chunks:
#     if c.get("source_file") == "docs/concepts/strict_mode.md":
#         hp = str(c.get("header_path"))
#         if hp not in seen_headers:
#             print(f"Header path: {hp}")
#             seen_headers.add(hp)

import sys
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_qdrant_client, fetch_all_chunks
from eval.run import resolve_evidence, load_golden
from src.bm25_index import build_bm25_index, tokenize_identifier_preserving


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qid",
        required=True,
        help="Question ID, e.g, q001"
    )
    args = parser.parse_args()

    client = get_qdrant_client()
    chunks = fetch_all_chunks(client=client)
    golden_path = PROJECT_ROOT / "eval" / "golden.jsonl"

    golden = load_golden(golden_path)
    item = next((g for g in golden if g["id"] == args.qid), None)
    if item is None:
        raise ValueError(f"QID NOT FOUND in golden.jsonl: {args.qid}")

    print("=" * 80)
    print(f"QID:      {args.qid}")
    print(f"QUESTION: {item['question']}")
    print(f"SCOPE:    {item['gt_version_scope']}")
    print("=" * 80)

    # ---- resolve, per key, never pooled ----
    resolved_evidence = {}
    for ev in item['gt_evidence']:
        resolved_evidence[ev] = resolve_evidence(
            ev, chunks=chunks, scope=item['gt_version_scope'], qid=args.qid
        )

    for ev, ids in resolved_evidence.items():
        print(f"\nEVIDENCE KEY: {ev}")
        print(f"  resolved: {len(ids)}")
        for cid in sorted(ids):
            print(f"    {cid}")

    # ---- index ----
    index = build_bm25_index(chunks=chunks)
    corpus_size = len(index.ids)

    idf_values = list(index.bm25.idf.values())
    print(f"\nIDF min: {min(idf_values):.6f}   IDF max: {max(idf_values):.6f}")
    print(f"CORPUS:  {corpus_size} chunks")

    # ---- score whole corpus, no exclusions, no cap ----
    question_tokens = tokenize_identifier_preserving(item['question'])
    print(f"\nTOKENS ({len(question_tokens)}, no dedupe): {question_tokens}")

    all_scores = index.bm25.get_scores(question_tokens)

    ranked = sorted(zip(index.ids, all_scores), key=lambda p: (-p[1], p[0]))
    rank_of = {cid: (i + 1, score) for i, (cid, score) in enumerate(ranked)}

    # position of each chunk_id in the parallel arrays
    pos_of = {cid: i for i, cid in enumerate(index.ids)}

    # per-unique-token score arrays, computed once
    term_scores = {}
    for tok in set(question_tokens):
        term_scores[tok] = index.bm25.get_scores([tok])

    # ---- report ----
    print("\n" + "=" * 80)
    print("BM25 REPORT (full corpus ranking, zero-scores included)")
    print("=" * 80)

    for ev, ids in resolved_evidence.items():
        print(f"\nEVIDENCE KEY: {ev}")
        if not ids:
            print("  >>> NO CHUNKS RESOLVED FOR THIS KEY <<<")
            continue

        for cid in sorted(ids, key=lambda c: rank_of[c][0]):
            rank, score = rank_of[cid]
            visible = (rank <= 50) and (score > 0)
            print("-" * 80)
            print(f"  {cid}")
            print(f"  rank {rank} of {corpus_size} | score {score:.4f} | pipeline_visible: {visible}")

            i = pos_of[cid]
            contribs = [(tok, term_scores[tok][i]) for tok in question_tokens]
            contribs.sort(key=lambda p: -p[1])

            for tok, c in contribs:
                print(f"      {tok:<24} {c:.4f}")

            s = sum(c for _, c in contribs)
            print(f"      {'SUM':<24} {s:.4f}   (total {score:.4f}, delta {s - score:+.6f})")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()