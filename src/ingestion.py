import ast
import os
from typing import List, Tuple, Literal
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from schema import Chunk
from config import COLLECTION_NAME
from structures import Stack
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

def load_file_type(loaded_files: list[tuple[str, Path]], type: Literal[".md", ".py"]):
    path_vers_list_type = []
    for (v,f) in loaded_files:
        if f.name == "HISTORY.md":
            continue

        if f.suffix == type:
            path_vers_list_type.append((v,f))

    return path_vers_list_type


def chunk_file(loaded_files: list[tuple[str, Path]], chunk_size:int=1000) -> list[Chunk]:
    """
    Chunk .md files by heading structure.

    - One chunk per section (heading -> next heading), size-split at blank lines past chunk_size, never inside a code fence. 
    - header_path = live heading stack snapshot. 
    - ID = {version}::{source_file}::{leaf}::{occ:03d}, occ counts chunks per leaf. 
    - Heading-only chunks dropped. Zero overlap: structural boundaries replace P1's sliding window.

    """
    
    chunk_list = []
    load_md = load_file_type(loaded_files, type='.md')
    print(f"Number of files to chunk: {len(load_md)}")

    for (v,f) in load_md:
        f = Path(f)
        version = v
        release_label = "v2.13" if v in ("v2", "both") else "v1.10"
        root = "pydantic-v1" if "pydantic-v1" in f.parts else "pydantic-v2"
        source_file = f.relative_to(PROJECT_ROOT / root).as_posix()
        text = f.read_text(encoding='utf-8')

        header_stack = []
        current_content = []
        current_length = 0

        # ``` this symbol is the start and end of code in markdown
        in_fence = False

        occurrence_map = {}

        # Tracking metrics for the current file
        file_header_count = 0
        chunks_before_file = len(chunk_list)

        def flush_current_chunk():
            nonlocal current_content, current_length
            content_str = "\n".join(current_content).strip()
            if not content_str:
                current_content.clear()
                current_length = 0
                return

            if content_str.startswith("#") and len(content_str.splitlines()) == 1:
                current_content.clear()
                current_length = 0
                return

            path_snapshot = [title for level, title in header_stack]
            if not path_snapshot:
                path_snapshot = ["[Preamble]"]

            # Leaf kept raw (backticks/links intact): D23 resolver normalizes on
            # ITS side; normalizing here too would double-transform and break match.
            heading_leaf = path_snapshot[-1]
            occ = occurrence_map.get(heading_leaf, 0)

            chunk_list.append(Chunk(
                id=f"{version}::{source_file}::{heading_leaf}::{occ:03d}",
                text=content_str,
                version=version,
                release_label=release_label,
                chunk_type="prose",
                source_file=source_file,
                header_path=path_snapshot
            ))

            occurrence_map[heading_leaf] = occ + 1
            current_content.clear()
            current_length = 0

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence

            if not in_fence and stripped.startswith("#"):
                header_parts = stripped.split(" ", 1)
                hashes = header_parts[0]

                if all(char == "#" for char in hashes) and len(header_parts) > 1:
                    level = len(hashes)
                    header_title = header_parts[1].strip()

                    file_header_count += 1

                    if current_content:
                        flush_current_chunk()

                    while header_stack and header_stack[-1][0]>=level:
                        header_stack.pop()
                    header_stack.append((level, header_title))

            current_content.append(line)

            current_length += len(line) + 1
            if current_length >= chunk_size and not in_fence and not stripped:
                flush_current_chunk()

        flush_current_chunk()
        file_chunks_created = len(chunk_list) - chunks_before_file
        print(f"Processed: {source_file} | Headers found: {file_header_count} | Chunks created: {file_chunks_created}")
    return chunk_list

# def chunk_py_files(version: Literal["v1", "v2", "both"], path: Path, pro) -> list[Chunk]:
#     pass

def chunk_python_files(loaded_files: list[tuple[str, Path]]) -> list[Chunk]:
    py_vers_files = load_file_type(loaded_files=loaded_files, type='.py')
    chunk_py_list = []

    

    def true_start(node):
        return (
            min(d.lineno for d in node.decorator_list)
            if node.decorator_list
            else node.lineno
        )

    def slice_code(lines, start, end):
        return "\n".join(lines[start-1:end])


    for (v, f) in py_vers_files:
        f = Path(f)
        release_label = "v2.13" if v in {"v2", "both"} else "v1.10"
        root = "pydantic-v1" if "pydantic-v1" in f.parts else "pydantic-v2"
        source_file = f.relative_to(PROJECT_ROOT / root).as_posix()
        text = f.read_text(encoding='utf-8')
        lines = text.splitlines()

        tree = ast.parse(text)
        # print(ast.dump(tree, indent=4))

        DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
        TOP_TYPES = DEF_TYPES + (ast.ClassDef,)
        segment = []
        current_line = 1

        for node in tree.body:
            if not isinstance(node, TOP_TYPES):
                continue

            start = true_start(node)
            if current_line<start:
                if slice_code(lines, current_line, start-1).strip():
                    segment.append((
                        "[PREAMBLE]",
                        current_line,
                        start-1
                    ))

            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, DEF_TYPES)]

                if methods:
                    segment.append((
                        node.name,
                        start,
                        true_start(methods[0]) - 1
                    ))

                    for m in methods:
                        segment.append((
                            f"{node.name}.{m.name}",
                            true_start(m),
                            m.end_lineno
                        ))
                else:         
                    segment.append((
                        node.name,
                        start,
                        node.end_lineno
                    ))

            else:

                segment.append((
                    node.name,
                    start,
                    node.end_lineno
                ))

            current_line = node.end_lineno+1

        if current_line <= len(lines):
            if slice_code(lines, current_line, len(lines)).strip():
                segment.append((
                    "[PREAMBLE]",
                    current_line,
                    len(lines)
                ))

        print(segment)

    return chunk_py_list

    
    '''
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

    '''

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
    # loaded_files = load_paths()
    # print(f"Total files = {len(loaded_files)}")

    # Trial
    # file_path = PROJECT_ROOT / "pydantic-v2" / "docs" / "concepts" / "strict_mode.md"
    # files_to_process = [("v2", file_path)]

    # resulting_chunks = chunk_file(loaded_files=files_to_process)

    # for chunk in resulting_chunks:
    #     print(f"ID: {chunk.id}")
    #     print(f"Header Path: {chunk.header_path}")
    #     print(f"Text Length: {len(chunk.text)} characters")
    #     print("-" * 40)

    
    file_path = PROJECT_ROOT / "pydantic-v1" / "docs" / "examples" / "validation_decorator_async.py"
    # file_path = PROJECT_ROOT / "misc" / "sample2.py"
    files_to_process = [("v1", file_path)]

    chunks = chunk_python_files(files_to_process)
    print(chunks)

    # chunks = chunk_file(loaded_files=loaded_files, chunk_size=1000, chunk_overlap=200)
    # print(chunks)
    # print(loaded_files)
    # chunks = chunk_file(loaded_files=loaded_files)
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



    # print(f"TOTAL CHUNKS: {len(chunks)}")
    # embed_list = embed_chunks(chunks=chunks)
    # print(f"vectors: {len(embed_list)}, dims: {len(embed_list[0])}")

    # print("PERFORMING Qdrant operations. UPSERT")
    # upsert_chunks(chunks=chunks, vectors=embed_list)

if __name__ =="__main__":
    main()