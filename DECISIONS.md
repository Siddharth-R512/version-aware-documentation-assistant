# Decision Log — Version-Aware Documentation Assistant

Format: decision -> why -> alternative rejected. War stories at the end.

---

## Phase 0 — Scope & Architecture

### D1. Corpus: Pydantic v1.10.26 and v2.13.4 via git worktrees
Two real, incompatible major versions of a widely used library — the version-contamination problem occurs naturally. Worktrees pin exact tags, so the corpus is frozen and reproducible. Folder layout: `pydantic-v1/`, `pydantic-v2/` inside the project root.

### D2. One Qdrant collection, not two (one per version)
Version lives in metadata (`version: v1 | v2 | both`), enabling filtered search within a single collection. Two collections would make comparison queries (which need both versions) require cross-collection merging, and would hard-code version into infrastructure instead of
data. Rejected: collection-per-version.

### D3. Storage: Qdrant via Docker (local, zero-config)
Payloads live next to vectors (no separate metadata store to keep in sync — the FAISS pain point), native payload filtering (needed for Phase 6 routing), persists to disk via volume mount. Known simplification: no auth in local mode — acceptable for local dev,
logged as such.

### D4. Models: text-embedding-3-small (1536 dims, cosine) + gpt-4o-mini
Cheap enough to re-ingest freely (~1–2 cents per full run); quality sufficient for a baseline. text-embedding-3-large (3072 dims, 6.5x price) rejected for Phase 1: it would change collection config, and "bigger model" is not the project's story — if evaluated later, it enters as a measured ablation against the Phase 2 harness, not a default.

### D5. Three query types drive the design
Version-specific (metadata filter), comparison (both versions, join on symbol_name), migration (migration guide + changelog first). The killer failure mode is **cross-version contamination**; the custom metric is **version precision**.

### D6. Chunk schema (src/schema.py)
`id`, `text`, `version` (Literal v1/v2/both), `release_label`, `chunk_type` (prose/code/changelog/migration), `source_file`, `header_path`, `symbol_name`, `linked_files`. Validator requires `symbol_name` on code chunks. Key distinctions: `version` is the filter key; `symbol_name` is the join key for comparison queries; `release_label` exists for display/citation (two different consumers).

### D7. Phase plan with a cut rule
P0 scope → P1 naive baseline → P2 eval set/harness → P3 real chunking (3 parsers, AST) → P4 hybrid BM25+RRF → P5 reranker → P6 query routing → P7 generation quality → P8 ship. If slipping: cut from the end, never P2 — the eval suite IS the portfolio. One change at a time from P2 onward, so every improvement has a measured before/after.

### D8. "Naive" applies to chunking/retrieval, NOT corpus selection
Corpus is identical across all phases. Re-litigated and re-confirmed: dropping .py files to save cost was rejected — full-code embedding costs ~$0.007, and a changing corpus breaks cross-phase comparability, Phase 2 ground truth, and the deprecated-shim bait.

---

## Phase 1 — Naive Ingest Pipeline

### D9. Data-driven include list
`INCLUDE` = list of `(root, version, glob_pattern)` tuples mirroring the corpus map
one-to-one. Loud failure: any pattern matching zero files raises FileNotFoundError.
`__init__.py` skipped uniformly in both versions. `migration.md` → version `"both"`.
Result: 290 files (v1: 196, v2: 94).

### D10. Naive chunking: 1000 chars / 200 overlap, character-based
Deliberately dumb baseline — this is the "before" photo for Phase 3. Character-based
(not word/token-based) for maximal simplicity. Skips pure-whitespace windows; breaks
after the window that reaches EOF to avoid a duplicate pure-overlap tail chunk.
Result: 3,248 chunks (v2: 2123, v1: 1062, both: 63; prose: 2737, changelog: 511).

### D11. chunk_type: only "prose" and "changelog" in v0
HISTORY.md → changelog; everything else → prose, including .py files. v0 doesn't claim
to understand code; the Phase 3 AST parser earns the "code" label. (Option (a), locked.)

### D12. Chunk ID format: `{version}:{source_file}:{index:03d}`
`source_file` is worktree-relative posix path (portable, no absolute Windows paths in IDs).
Zero-padding is 3 digits because files exceed 99 chunks (v2 main.py = 107); mixed-width
indexes would break string sort and pin inconsistent IDs into Phase 2 ground truth.

### D13. Embedding stage: batches of ~100, pure function, no cache
~100 texts/call ≈ 25K tokens — comfortably under the 2,048-inputs-per-request cap and the
~community-observed ~300K-tokens-per-request ceiling; 3,248 chunks = 33 calls. Order
verified per item (`item.index == j`) and in aggregate (`len(vectors) == len(chunks)`)
because these vectors get pinned as Phase 2 ground truth. No retry/async/caching — a
failed run costs 2 cents to redo. Persistence is Qdrant's job, not a second cache layer.

### D14. Embed bare chunk text only
No metadata prepended into the embedded string. Vector = for finding; payload = for
filtering and citing. Metadata-enriched embedding is a legitimate technique but banned
from the naive baseline; if it appears, it appears as a measured experiment.

### D15. Qdrant point IDs: uuid5(NAMESPACE_URL, chunk.id)
Qdrant requires int/UUID point IDs; chunk IDs are strings. uuid5 is a deterministic hash:
same chunk ID → same point ID on every run → upsert overwrites in place →
**idempotent re-ingest** (verified: two full runs, count stable at 3,248).
uuid4/sequential ints rejected: random or order-dependent IDs duplicate the corpus on
every re-run. The readable string `chunk.id` also lives in the payload — the UUID is
Qdrant plumbing; the string ID is for humans and the eval harness.

### D16. Full chunk (including text) stored as payload
`model_dump()` of the whole Chunk. Qdrant is the single store; retrieval never touches
the filesystem. Upserts batched (100/call, `wait=True`) to stay under payload-size limits
and make post-write verification non-racy. Verification is **server-side**
(`client.count(exact=True)`) — the local list says what was intended, the server says
what landed.

### D17. Idempotency boundary (known edge)
uuid5 gives idempotency for a **frozen** corpus, not synchronization for a changing one.
If a file shrank, high-index chunks would be orphaned (upsert never deletes). Doesn't
apply here (worktrees are pinned), but chunker changes in Phase 3 change every ID —
policy: `delete_collection` + full re-ingest (~2 cents) on any chunking change.
Production answer at scale: content-hash IDs + tombstoning.

### D18. Loud failure over silent skip (design rule, applied twice)
FileNotFoundError on empty glob; assert (not `return None`) on chunk/vector length
mismatch. Impossible states crash; expected states get handled.

### D19. Eval ground truth keyed by file+heading (amends earlier chunk ID decision)
Chunk IDs remain stable during ingestion but not for evaluations. Re-chunking in Phase 3 changes chunk boundaries, breaking any ground truth keyed on chunk IDs. The eval set will now store file path + nearest Heading which is resolved to current chunk ID during run time, keeping eval strategies stable across chunking strategies and enabling fair comparisons.

### D20. `version="both"` counts as correct (1.0) for version precision
A `both` chunk cannot represent contamination. Version precision should measure only wrong-version retrieval. Relevance is captured by `Hit@K` and `MRR` avoiding overlap between metrics.

### D21. P2 harness evaluates retrieval only; generation evaluation deferred
Phase 2 harness measures retrieval deterministically using chunk ID matching, avoiding LLM costs and variability. However, eval questions are labeled now with generation-scoring metadata (e.g., required terms, deprecated terms, answerability) so answer evaluation can be added in Phase 7 without relabeling.

### D22. Citation requirement deferred to Phase 7
Since citations concern answer generation rather than retrieval, implementation is deferred to Phase 7 and recorded to maintain design traceability.
---

## Numbers (for README)
- Corpus: 290 files → 3,248 chunks (2:1 v2:v1 imbalance; 511 changelog chunks ≈ 16%)
- Full-corpus embed: ~33 API calls, ~$0.01–0.02 per ingest run
- Vectors: 1536 dims, cosine, one collection

## Watch-fors carried into hand-poking (Phase 1 exit)
1. **2:1 corpus imbalance** → unfiltered dense retrieval has a v2 prior; test contamination
   in BOTH directions ("asked v1 got v2" may be the common one).
2. **Changelog bulk** (16% of corpus, every API name appears there) → changelog chunks may
   crowd out docs chunks. If observed: documented failure with an obvious P6 lever.
3. **Live bait**: v2's deprecated v1-named shims (`dict()`, `json()`, `parse_obj()`) are
   chunked with version="v2" — prime contamination material.

---

## P2 hand-verification findings (before freezing)

- Fixed q029: the generator said parse_file was completely removed in v2. I grepped
  v2's main.py and found it still exists as a deprecated shim. Changed the answer
  to "also deprecated."
- Fixed q032: the original answer used populate_by_name, which was the v2.0 name.
  But v2.13.4's own rename map (_internal/_config.py, line 360) says the current
  name is validate_by_name, and the migration doc (line 345) mentions both. So the
  canonical terms now require both names. Note: my first fix updated the terms but
  forgot the gt_answer — another case of a fix not fully landing, caught on re-review.
- Resolved a contradiction: q018 said allow_mutation was removed, q028 said it was
  renamed. The source settles it — line 348 of _internal/_config.py lists it as a
  bare string in the removed-keys list, not as a rename pair. So it was removed.
  Rewrote q028.
- Close call worth remembering: the v2 worktree ships its own copy of pydantic/v1/
  for backward compatibility. I checked Qdrant — zero chunks came from that folder,
  but only because our glob (pydantic/*.py) happens to be non-recursive. If it had
  been recursive, every eval number would have been sitting on wrongly-labeled chunks
  without us knowing.
- The generator's list of 10 questions it wasn't confident about turned up in
  golden_set_notes.md. It flagged q019, q022, and q047 — all three were already
  covered by our independent command-by-command verification.

## Parked for P7 (don't touch until then)

- How to score wrong terms: a good answer often needs to MENTION the old API just to
  say "don't use this anymore" (q001's own reference answer contains .dict()). A
  naive substring check would fail correct answers. The scorer has to tell the
  difference between "presented as the current way" and "mentioned as deprecated."
- The citation rule is still missing from answer.py's prompt (D22). Check the
  honesty rule while in there.

## FREEZE

The golden set is frozen at 50 items, all hand-verified. From this commit on, the
question and answer text never changes. The only field that may be re-audited later
is gt_evidence (after P3 re-chunking).
