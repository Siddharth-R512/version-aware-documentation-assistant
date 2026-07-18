# The Harness File
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # ..\Sid-Projects\version-aware-document-assistant
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import COLLECTION_NAME, get_qdrant_client

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

if __name__ == "__main__":
    golden = load_golden('eval/golden.jsonl')
    # print(golden[:5])

    client = get_qdrant_client()

    resolved_chunks = fetch_all_chunks(client=client)
    # print(resolve_chunks)

    audit(golden=golden, chunks=resolved_chunks)

    # suspects = [
    #     "docs/concepts/serialization.md",
    #     "docs/migration.md",
    #     "docs/concepts/conversion_table.md",
    #     "docs/concepts/postponed_annotations.md",
    #     "docs/concepts/validators.md",
    #     "docs/errors/errors.md",
    # ]
    # for f in suspects:
    #     n = sum(1 for c in resolved_chunks if c.get("source_file") == f)
    #     print(f"{f}: {n} chunks in corpus")

    # for c in resolved_chunks:
    #     if c.get("source_file") == "docs/concepts/dataclasses.md" and c["id"].endswith(":000"):
    #         print(repr(c["text"][:400]))