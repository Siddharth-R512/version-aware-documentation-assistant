from qdrant_client import QdrantClient

COLLECTION_NAME = "pydantic-knowledge-base"
QDRANT_URL = "http://localhost:6333"

def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL)

def fetch_all_chunks(client=None) -> list[dict]:
    if not client:
        client = get_qdrant_client()
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

    assert len(points) == 3599, f"Expected 3599 chunks in Qdrant, found {len(points)}"
    return [p.payload for p in points]