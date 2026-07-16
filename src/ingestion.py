import os
from typing import List, Tuple
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from schema import Chunk
from config import COLLECTION_NAME
import math
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import uuid

PROJECT_ROOT = Path(__file__).parents[1] # ....\version-aware-document-assistant

INCLUDE = [
    ("pydantic-v1", "v1", "docs/examples/*.py"),
    ("pydantic-v1", "v1", "docs/usage/*.md"),
    ("pydantic-v1", "v1", "docs/changelog.md"),
    ("pydantic-v1", "v1", "docs/datamodel_code_generator.md"),
    ("pydantic-v1", "v1", "docs/hypothesis_plugin.md"),
    ("pydantic-v1", "v1", "docs/index.md"),
    ("pydantic-v1", "v1", "docs/install.md"),
    ("pydantic-v1", "v1", "docs/mypy_plugin.md"),
    ("pydantic-v1", "v1", "docs/pycharm_plugin.md"),
    ("pydantic-v1", "v1", "docs/visual_studio_code.md"),
    ("pydantic-v1", "v1", "pydantic/*.py"),
    ("pydantic-v1", "v1", "HISTORY.md"), ####

    ("pydantic-v2", "v2", "docs/concepts/*.md"),
    ("pydantic-v2", "v2", "docs/errors/*.md"),
    ("pydantic-v2", "v2", "docs/examples/*.md"),
    ("pydantic-v2", "v2", "docs/integrations/*.md"),
    ("pydantic-v2", "v2", "docs/internals/*.md"),
    ("pydantic-v2", "v2", "docs/index.md"),
    ("pydantic-v2", "v2", "docs/install.md"),
    ("pydantic-v2", "v2", "docs/migration.md"),
    ("pydantic-v2", "v2", "docs/version-policy.md"),
    ("pydantic-v2", "v2", "docs/why.md"),
    ("pydantic-v2", "v2", "pydantic/deprecated/*.py"),
    ("pydantic-v2", "v2", "pydantic/experimental/*.py"),
    ("pydantic-v2", "v2", "pydantic/*.py"),
    ("pydantic-v2", "v2", "HISTORY.md"),
]
def load_paths():
    path_vers_list = []
    for root, vers, pattern in INCLUDE:
        matches = sorted((PROJECT_ROOT/root).glob(pattern))
        if not matches:
            raise FileNotFoundError(f"{root}/{pattern} is not in-line with corpus map. please check again.")
        kept = 0
        for f in matches:
            if f.name == "__init__.py":
                continue    
            v = "both" if f.name == "migration.md" else vers
            path_vers_list.append((v, f))
            kept += 1
        print(f"{root}/{pattern:40} -> {kept}")
    return path_vers_list

def chunk_file(loaded_files: list[tuple[str, Path]], chunk_size:int=1000, chunk_overlap:int=200) -> list[Chunk]:
    """
    loaded_files = [(v, f)]
    v --> v1, v2, or both
    f --> file path .md or .py

    chunk:
    id -> "{version}:{source_file}:{index}" .. index is chunk counter,
    text -> str,
    version -> v,
    release_label -> v1.10 or v2.13,
    chunk_type = prose (all chunks, for now),
    source_file -> f,
    header_path -> default -> [],
    symbol_name -> default -> None,
    linked_files -> default -> []

    return: List[Chunk]
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be < chunk_size")
    chunk_list = []
    stride = chunk_size - chunk_overlap
    
    print(f"No. of files to chunk = {len(loaded_files)}")
    for (v, f) in loaded_files:
        f = Path(f)
        version = v
        release_label = "v2.13" if v in ("v2", "both") else "v1.10"
        root = "pydantic-v1" if "pydantic-v1" in f.parts else "pydantic-v2"
        source_file = f.relative_to(PROJECT_ROOT / root).as_posix()
        text = f.read_text(encoding='utf-8')
        pos = 0
        index = 0
        while pos < len(text):
            window = text[pos:pos+chunk_size]
            if not window.strip():
                pos+=stride
                continue
            chunk_list.append(
                Chunk(
                    id=f"{version}:{source_file}:{index:03d}",
                    text=window,
                    version=version,
                    release_label=release_label,
                    chunk_type="changelog" if f.name == "HISTORY.md" else "prose",
                    source_file=source_file
                )
            )
            index +=1
            if pos + chunk_size >= len(text): # last window reached EOF.. a further window would be pure overlap
                break
            pos += stride
            
            # print(f"Created chunk {index} for file {source_file}")
        print(f"No. of chunks in file {source_file} = {index}")
    
    return chunk_list

def _get_client():
    return OpenAI()

def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    results = []
    batch_count = math.ceil(len(chunks)/100)
    client =_get_client()
    for i in range(0, len(chunks), 100):
        batch = chunks[i:i+100]
        text_batch = [c.text for c in batch]
        print(f"PROGRESS {i//100 + 1}/{batch_count}")
        print(f"CHUNKS to EMBEDDINGS {len(batch)} out of {len(chunks)}")
        response = client.embeddings.create(
            input=text_batch,
            model="text-embedding-3-small"
        )
        for j, item in enumerate(response.data):
            assert item.index == j
        results.extend(item.embedding for item in response.data)
    
    assert len(results) == len(chunks), f"{len(results)} vectors != {len(chunks)} chunks"
    return results

def upsert_chunks(chunks: list[Chunk], vectors: list[list[float]]) -> None:
    list_of_pointstructs = []
    assert len(chunks) == len(vectors), f"{len(chunks)} chunks != {len(vectors)} vectors"

    client = QdrantClient(url="http://localhost:6333")
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )

    for i, c in enumerate(chunks):
        list_of_pointstructs.append(PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.id)),
            vector=vectors[i],
            payload=c.model_dump()
        ))
    
    for i in range(0, len(list_of_pointstructs), 100):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=list_of_pointstructs[i:i+100],
            wait=True
        )
        print(f"Upsert batch {i//100 + 1}/{math.ceil(len(list_of_pointstructs)/100)}")
    server_count = client.count(collection_name=COLLECTION_NAME, exact=True).count

    print(f"points in collection: {server_count}")
    assert server_count == len(chunks), f"server has {server_count}, expected {len(chunks)}"

def main():    
    loaded_files = load_paths()
    print(f"Total files = {len(loaded_files)}")
    # print(loaded_files)
    chunks = chunk_file(loaded_files=loaded_files)
    # from collections import Counter

    # # --- per-version counts ---
    # print(f"TOTAL CHUNKS: {len(chunks)}")
    # print("Per-version:", Counter(c.version for c in chunks))
    # print("Per-type:   ", Counter(c.chunk_type for c in chunks))

    # # --- eyeball: one migration chunk (verify version='both') ---
    # mig = [c for c in chunks if c.source_file == "docs/migration.md"]
    # print(f"\nmigration.md chunks: {len(mig)}")
    # print(f"sample -> id={mig[0].id}  version={mig[0].version}")
    # print(mig[0].text[:400])

    # # --- eyeball: one v2 main.py chunk (see the ugly split) ---
    # mainpy = [c for c in chunks if c.source_file == "pydantic/main.py" and c.version == "v2"]
    # print(f"\nv2 main.py chunks: {len(mainpy)}")
    # print(mainpy[len(mainpy)//2].text[:600])   # middle of the file, mid-function odds high

    # # --- eyeball: adjacent-chunk overlap check ---
    # a, b = mig[0], mig[1]
    # print("overlap ok:", a.text[-200:] == b.text[:200])
    # print(f"\noverlap check: {a.id} tail == {b.id} head ?")
    # print("TAIL:", repr(a.text[-100:]))
    # print("HEAD:", repr(b.text[:100]))
    # for i in range(0, 4):
    #     print(chunks[i])
    #     print("\n"+"*"*30+"\n")
    print(f"TOTAL CHUNKS: {len(chunks)}")
    embed_list = embed_chunks(chunks=chunks)
    print(f"vectors: {len(embed_list)}, dims: {len(embed_list[0])}")

    print("PERFORMING Qdrant operations. UPSERT")
    upsert_chunks(chunks=chunks, vectors=embed_list)

if __name__ =="__main__":
    main()