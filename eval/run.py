# The Harness File
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # ..\Sid-Projects\version-aware-document-assistant
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import COLLECTION_NAME, get_qdrant_client
from src.retrieve import retrieve

def _normalize(text: str) -> str:
    """Helper to remove markdown backticks and ignore case for heading matches."""
    return text.lower().replace("`", "")

def load_golden(path: str) -> list[dict]:
    """Read golden.jsonl. Assert 50 items - fail loud if the frozen file item count is not 50"""
    golden = []
    path_w = Path(path)

    with path_w.open("r", encoding='utf-8') as f:
        for line in f:
            if line.strip():
                golden.append(json.loads(line))

    assert len(golden) == 50, f"Expected 50 golden items. Found {len(golden)}. Frozen file modified?"
    return golden

def load_config(path: str) -> dict:
    path_w = Path(path)
    with path_w.open("r", encoding='utf-8') as f:
        return json.load(f)
    
def fetch_all_chunks(client) -> list[dict]:
    # client = get_qdrant_client()
    points, offset = [], None
    while True:
        batch, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        points.extend(batch)
        if offset is None:
            break

    assert len(points) == 3248, f"Expected 3248 chunks in Qdrant, found {len(points)}"
    return [p.payload for p in points]

def resolve_evidence(evidence: str, chunks: list[dict], scope: str) -> set[str]:
    """
    gt_evidence format convert into set of IDs
    file :: heading
    file exact match and heading in joined (header_path or text)
    """
    resolved_ids = set()
    parts = evidence.split('::')
    if len(parts) != 2:
        return resolved_ids
    
    target_file = parts[0].strip()
    target_heading = _normalize(parts[1].strip())  
    for chunk in chunks:
        if chunk.get("source_file") != target_file:
            continue
            
        # 2. Version Filter
        chunk_version = chunk.get("version", "both")
        if scope == "v1" and chunk_version not in {"v1", "both"}:
            continue
        if scope == "v2" and chunk_version not in {"v2", "both"}:
            continue

        header_path = chunk.get('header_path', [])
        if isinstance(header_path, list):
            joined_header = " > ".join(header_path)
        else:
            joined_header = str(header_path)
            
        text = chunk.get("text", "")

        # Normalize both sides before checking containment
        if target_heading in _normalize(joined_header) or target_heading in _normalize(text):
            resolved_ids.add(chunk.get("id"))

    return resolved_ids

def audit(golden: list[dict], chunks: list[dict]):
    """
    Per evidence: print resolved count. zero resolved strings are listed loudly at the end.
    Summary: N/45 answerable items fully resolvable and skip unanswerable items.
    """
    zero_count_strings = []
    answerable_count = 0
    fully_resolvable = 0
    
    for item in golden:
        if not item.get('answerable', True):
            continue
        
        answerable_count +=1
        item_fully_resolvable = True
        scope = item.get("gt_version_scope", "any")
        evidences = item.get('gt_evidence', [])
        for evidence in evidences:
            resolved = resolve_evidence(evidence=evidence, chunks=chunks, scope=scope)
            count = len(resolved)
            print(f"Evidence: '{evidence}' -> {count} chunks resolved")

            if count == 0:
                zero_count_strings.append(evidence)
                item_fully_resolvable = False

        if item_fully_resolvable and len(evidences) > 0:
            fully_resolvable += 1

    if zero_count_strings:
        print("\n" + "="*50)
        print("ZERO-COUNT EVIDENCE STRINGS (REQUIRES ATTENTION):")
        for ev in dict.fromkeys(zero_count_strings):
            print(f"  - {ev}")
        print("="*60 + "\n")
        
    print(f"Summary: {fully_resolvable}/{answerable_count} answerable items fully resolvable.")

def retrieve_top5(question: str, config: dict) -> list[tuple[str, str]]:
    """Call YOUR existing retrieval. Return [(chunk_id, version)] in rank order."""
    top_k = config.get("top_k", 5)
    
    # Call your real pipeline
    results = retrieve(question, top_k=top_k)
    
    # Extract id and version from the payload of the Qdrant points
    return [(str(doc.payload["id"]), str(doc.payload["version"])) for doc in results]

def build_gt_pools(golden: list[dict], chunks: list[dict]) -> dict[str, set[str]]:
    """Per question id: union of resolve_evidence over its gt_evidence list.
    Recomputed every run — never cached to disk (D19)."""
    pools = {}
    for item in golden:
        q_id = item["id"]
        pools[q_id] = set()
        scope = item.get("gt_version_scope", "any")
        
        # Unanswerable items simply have empty/no gt_evidence
        for evidence in item.get("gt_evidence", []):
            pools[q_id].update(resolve_evidence(evidence, chunks, scope))
            
    return pools

def score_question(item: dict, pool: set[str], retrieved: list[tuple[str, str]]) -> dict:
    """One golden item -> one CSV row dict. All metric logic lives here."""
    q_id = item["id"]
    category = item.get("category", "")
    gt_version_scope = item.get("gt_version_scope", "any")
    answerable = item.get("answerable", True)
    
    retrieved_ids = [r[0] for r in retrieved]
    retrieved_versions = [r[1] for r in retrieved]
    
    row = {
        "id": q_id,
        "category": category,
        "gt_version_scope": gt_version_scope,
        "answerable": answerable,
        "resolved_gt_count": len(pool),
        "retrieved_ids": "|".join(retrieved_ids),
        "retrieved_versions": "|".join(retrieved_versions),
        "hit_at_5": "",
        "first_gt_rank": "",
        "mrr": "",
        "version_precision": ""
    }
    
    # Unanswerable items skip metrics computation (metrics remain NA/empty string)
    if not answerable:
        return row
        
    # hit@5 and MRR
    hit = 0
    mrr = 0.0
    first_gt_rank = ""
    
    for i, (r_id, _) in enumerate(retrieved):
        if r_id in pool:
            hit = 1
            first_gt_rank = i + 1  # 1-indexed rank
            mrr = 1.0 / first_gt_rank
            break
            
    row["hit_at_5"] = hit
    row["first_gt_rank"] = first_gt_rank
    row["mrr"] = mrr
    
    # Version precision
    if gt_version_scope == "any":
        # Report as NA to prevent free 1.0s from inflating averages
        row["version_precision"] = ""  
    else:
        correct_version_count = 0
        for _, r_version in retrieved:
            if r_version in {gt_version_scope, "both"}:
                correct_version_count += 1
        row["version_precision"] = correct_version_count / len(retrieved) if retrieved else 0.0
        
    return row

if __name__ == "__main__":
    golden = load_golden('eval/golden.jsonl')
    client = get_qdrant_client()
    chunks = fetch_all_chunks(client=client)
    
    # Build the GT pools for all items
    gt_pools = build_gt_pools(golden, chunks)
    
    # Test scoring on the first item
    test_item = golden[0]
    test_config = {"top_k": 5}
    
    print(f"Question: {test_item['question']}")
    print(f"GT Scope: {test_item.get('gt_version_scope')}")
    print(f"GT Pool IDs: {gt_pools[test_item['id']]}\n")
    
    retrieved = retrieve_top5(test_item['question'], test_config)
    print("Retrieved tuples:")
    for i, r in enumerate(retrieved):
        print(f"  Rank {i+1}: {r}")
        
    row = score_question(test_item, gt_pools[test_item['id']], retrieved)
    print("\nScored Row Output:")
    for k, v in row.items():
        print(f"  {k}: {v}")
