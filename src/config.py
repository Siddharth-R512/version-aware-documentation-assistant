from qdrant_client import QdrantClient

COLLECTION_NAME = "pydantic-knowledge-base"
QDRANT_URL = "http://localhost:6333"

def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL)