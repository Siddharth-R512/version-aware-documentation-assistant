from qdrant_client import QdrantClient

COLLECTION_NAME = "pydantic-knowledge-base"

def get_qdrant_client():
    return QdrantClient(url="http://localhost:6333")