from dotenv import load_dotenv
from openai import OpenAI
from pprint import pprint
from src.config import COLLECTION_NAME
load_dotenv()

from qdrant_client import QdrantClient

client_db = QdrantClient(url="http://localhost:6333")

def _get_client():
    return OpenAI()

def retrieve(query: str, top_k: int = 5):
    client = _get_client()
    response = client.embeddings.create(
        input=[query],
        model="text-embedding-3-small"
    )

    query_vector = response.data[0].embedding
    results = client_db.query_points(collection_name=COLLECTION_NAME, query=query_vector, limit=top_k)
    return results.points

if __name__=="__main__":
    query = "how do I convert a model to a dict in v2?"
    hits = retrieve(query)
    print(f"Hits object type {type(hits)}")
    for hit in hits:
        print(f"hit type: {type(hit)}")
        pprint(hit.model_dump())
