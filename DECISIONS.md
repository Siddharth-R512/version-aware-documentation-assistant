# Decision log - Version Aware Documentation Assistant

Format: decision -> why -> alternative rejected. War stories at the end.



## Phase 0: Scope & Architecture

### D1. Corpus: Pydantic v1.10.26 and v2.13.4 via git worktrees
Two real, incompatible major versions of Pydantic -> Here the version-contamination problem occurs naturally. Worktrees pin exact tags, so the corpus is frozen and reproducible. Folder layout: `pydantic-v1`, `pydantic-v2` inside the project root.

### D2. ONE Qdrant collection, NOT 2 (one by version)
Version lives in metadata `version: v1 | v2 | both` enabling filtered search within a single collection. 2 collections would make comparison queries (which need both versions) require cross collection merging and would hard code version into infrastructure instead of data. Rejected: collection-per-version.

### D3. Storage: Qdrant via Docker (Local, zero config)
Payloads are stored alongside vectors, eliminating the need for a separate metadata store to keep in sync (a limitation encountered with FAISS). Qdrant also provides native payload filtering which is required in _phase 6: query routing_ and persists data through volume mount. For simplicity, local setup runs without auth - acceptable for dev, logged as such.

### D4. Models: text-embedding-3-small (1536 dims, cosine) + gpt-4o-mini
Cheap enough to re-ingest freely (1-2 cents per full run); quality sufficient for a baseline. text-embedding-3-large (3072 dims, 6.5x price) rejected for Phase 1: it would change collection config and more importantly, the project's focus is on evaluating retrieval pipeline rather than demonstrating gains from large embedding model.

### D5. Query Types Driving the Design
3 primary query types: version specific (metadata filter), comparison (both versions, join on symbol name) and migration (migration guide + changelog). The biggest challenge is **cross-version contamination**. The evaluation introduces **version precision** as a custom metric alongside standard retrieval metrics

### D6. Chunk Schema (`src/schema.py`)
`id`, `text`, `version` (Literal v1/v2/both), `release_label`, `chunk_type` (Literal prose/code/changelog/migration), `source_file`, `header_path`, `symbol_name`, `linked_files`. Validator (`@model_validator`) requires `symbol_names` on code chunks. Key distinctions: `version` is the filter key; `symbol_name` is the join jey for comparison queries; `release_label` exists for display/citation.

### D7. Phase plan with a cut rule
P0 scope -> P1 naive baseline -> P2 eval set/harness -> P3 real chunking (3 parsers, AST) -> P4 hybrid BM25 + RRF -> P5 reranker -> P6 query routing -> P7 generation quality -> P8 ship. If slowed down, cut from the end, never P2. 

### D8. Naive applies to chunking/retrival. NOT corpus selection
Corpus is identical across all phases to ensure fair comparisons of retrieval approaches. The option of excluding `.py` files to reduce embedding costs was considered but rejected as the embedding the complete codebase costs < 1 cent. Altering corpus between phases would compromise cross-phase comparability, invalidate phase 2 ground truth and remove the deprecated API shim that are intentionally included to evaluate version aware retrieval.

---

## Phase 1: Naive Ingest Pipeline
`INCLUDE` is the list of `(root, version, glob_pattern)` tuples that mirror the corpus map one-to-one. Each pattern must match at least 1 file; otherwise `FileNotFoundError` is raised to fail loudly. `__init__.py` is excluded consistently acoss both versions while `migration.md` is assigned the `version` = `"both"`. Result: 290 files (v1: 196, v2: 94).

### D10. Naive Chunking: 1000 chars / 200 overlap, character-based
A deliberatly dumb baseline serving as "before" snapshot for phase 3. Chunking uses fixed 1000 characters windows with a 200 char overlap (not word/token based) to keep the implementation as simple as possible. Skips pure-whitespace windows; breaks after the window that reaches EOF to avoid a duplicate pure-overlap tail chunk. Result: 3,248 chunks (v2: 2123, v1: 1062, both: 63; prose: 2737, changelog: 511).

### D11. chunk_type: only "prose" and "changelog" in v0
HISTORY.md -> changelog; everthing else -> prose including .py files. v0 doesnt claim to understand code; the phase 3 AST parser ears the "code" label.

### D12. Chunk ID format: `{version}:{source_file}:{index:03d}`
`source_file` is worktree-relative posix path, ensuring IDs remaining portable and do not embed absolute windows path. Chunk indices are zero padded to 3 digits because some file exceed 99 chunks (v2 `main.py` = 107). Without consistent zero-padding, string sorting would produce an incorrect order and introduce unstable IDs into the Phase 2 ground-truth dataset.

### D13. Embedding stage: batches of ~100, pure function, no cache
Embeddings are generated in batches of ~100 texts (~25k tokens), comfortably below the 2,048-input limit and the community-observed ~300k-token request ceiling. For 3,248 chunks, this requires 33 API calls. Embedding order is verified per batch (`item.index == j`) and overall (`len(vectors) == len(chunks)`), as these vectors form the Phase 2 ground truth. Retries, async processing, and caching are intentionally omitted—a rerun costs only about 2 cents, and persistence is handled by Qdrant.  

### D14. Embed Chunk Text Only
Only the chunk text is embedded; metadata is stored separately in the Qdrant payload. Embeddings are used solely for semantic retrieval, while payload fields support filtering and source attribution. Although enriching embeddings with metadata is a valid retrieval strategy, it is intentionally excluded from the naive baseline to isolate the effects of the retrieval pipeline. If evaluated, it will be introduced as a controlled experiment rather than part of the default configuration.

### D15. Deterministic Qdrant Point IDs
Qdrant requires each point to have an integer or UUID identifier whereas chunk IDs are stored as strings. To ensure deterministic IDs, the point ID is generated using `uuid5(NAMESPACE_URL, chunk.id)`, producing the same UUID for the same chunk across different ingestion run. This make re-ingestion **idempotent**: Repeated upserts overwrite existing points instead of creating duplicates (erified across three full ingestion runs, with the collection remaining at 3,248 points). Alternatives such as `uuid4` or sequential integers are rejected because they generate random or order-dependent identifiers, causing duplicate entries on repeated ingestions. The original, human-readable chunk.id is also stored in the payload for debugging and evaluation, while the UUID serves solely as Qdrant's internal point identifier.

### D16. Full chunk (including text) stored as payload
`model_dump()` of the whole Chunk. Qdrant is the single store; retrieval never touches the filesystem. Upserts batched (100/call, `wait=True`) to stay under payload-size limits and make post-write verification non-racy. Verification is **server-side** (`client.count(exact=True)`) — the local list says what was intended, the server says what landed.

### D17. Idempotency boundary (known edge)
uuid5 gives idempotency for a **frozen** corpus, not synchronization for a changing one. If a file shrank, high-index chunks would be orphaned (upsert never deletes). Doesn't apply here (worktrees are pinned), but chunker changes in Phase 3 change every ID — policy: `delete_collection` + full re-ingest (~2 cents) on any chunking change. Production answer at scale: content-hash IDs + tombstoning.

### D18. Fail Fast on Invalid States
The pipeline is designed to fail loudly rather than silently skip errors. A `FileNotFoundError` is raised for an empty corpus, and assertions catch chunk/vector count mismatches. Expected conditions are handled explicitly; impossible states terminate execution.

### D19. Stable Evaluation References
While chunk IDs remain stable during ingestion, they change whenever the corpus is re-chunked. To keep evaluations comparable across chunking strategies, ground truth is stored as file path + nearest heading, which is resolved to the current chunk ID at runtime. This preserves evaluation stability without depending on chunk boundaries.

### D20. Treat `version="both"` as Correct for Version Precision
Chunks labelled `version="both"` are counted as correct, as they cannot represent cross-version contamination. Version precision measures only wrong-version retrieval, while relevance is evaluated separately using Hit@K and MRR, keeping the metrics independent.

### D21. Phase 2 Evaluates Retrieval Only
The phase 2 harness evaluates retrieval deterministically using chunk ID matching, avoiding LLM costs and output variability. Evaluation questions are nevertheless annotated with generation metadata (e.g., required terms, deprecated terms, answerability) so answer evaluation can be added in Phase 7 without relabelling.

### D22. Citation Support Deferred to Phase 7
Citation generation is deferred to Phase 7 because it evaluates answer generation rather than retrieval. This decision is documented to maintain design traceability.

### D23. Resolver Rile: exact file match + normalized heading/text + version filter
Evidence (`source_file::heading`) is resolved to chunks by matching the file path exactly and locating the heading within either `header_path` or the chunk text after lowering and removing backticks. `Phase 1` relies on text matching because `header_path` is empty, while Phase 3 primarily uses the `header_path`. A version fiter is then applied to prevent chunks from one worktree from being matched against the other, avoiding false positives caused by identical filenames. Rejected: Raw string matching proved too brittle due to formatting differences.

### D24. Evidence-string conventions (from the audit)
- Use a distinctive single-line text phrase only when no heading exists. Phrases must stay on one line, as chunk text preserves line breaks.
- Choose the most specific heading that contains the answer. Broad headings can match many unrelated chunks.
- Every evidence string should directly support the target question. It's better to remove an incorrect evidence string than keep a misleading one.
- Always run an `--audit` before computing metrics to catch empty ground-truth pools instead of silently evaluating them.

### D25. NA convention: empty string but never 0; NAs are excluded from every average.
- The rule for a miss: `first_gt_rank` is NA, but mrr is 0.0. These look inconsistent but they are not. There's genuinely no such thing as "Rank of chunk that never showed up", so NA is the honest value for rank. A miss on the other hand is the real score -> the retriever tried and failed and that failure should count. If we marked MRR as NA on misses the averaging step would quietly drop every failures and only the average the successes making retrieval look better than it is. 
- Unanswerable items get NA across the board though I still log what was retrieved. 
- A 0 where NA belongs poisons every downstream mean.

### D26. version_precision is defined only for scope v1/v2; NA for "any" AND "both"
The scorer must agree with the resolver: when resolver accepts all versions as valid (Scope any/both), there is no correct version lane left to measure, So version precision has to be NA. I caught this the hard way. My first implementation only NA'd any and a scope-both questions promptly scored 0.0 because the acceptable set shrank to {both}, penalising perfectly valid v1/v2 chunks. That 0.0 read like a genuine finding. The version agnostic questions MUST BE ALL "NA" before baseline summary to written.

### D27. Harness imports the real retrieval; shaping lives in the harness
`run.py` imports `retrieve()` directly from `src/retrieve.py` - never reimplemented, because copies drift out of sync. Beside I am testing the retrival itself. There isn't a point if I recreate a retriever inside harness. `retrieve()` returns full point structure. But in test harness I require only tuples as `(id, version)`. So I created a harness's `retrieve_top5()` adapter that extracts the tuple of original return value of `retrieve()`. Rejected alternative: making `retrieve()` return tuples directly. That would break the other consumer.

### D28. Phase 2 baseline: measured, gate passed, P2 COMPLETE

Config: phase1_baseline (dense, top_k=5). 50 items, 45 scored.

| category            | n  | hit@5 | MRR   | ver_precision |
|---------------------|----|-------|-------|---------------|
| api_lookup          | 5  | 0.750 | 0.750 | 0.650         |
| howto_usage         | 10 | 0.333 | 0.204 | 0.657         |
| migration_diff      | 10 | 0.333 | 0.170 | 0.622         |
| version_agnostic    | 10 | 0.556 | 0.389 | NA            |
| version_explicit_v1 | 5  | 0.000 | 0.000 | 0.280         |
| version_explicit_v2 | 10 | 0.444 | 0.278 | 0.756         |
| ALL                 | 50 | 0.400 | 0.275 | 0.618         |

Gate check -> do the numbers reproduce my P1 hand-poked findings?
- F5 (reverse contamination): the headline. version_explicit_v1 at hit 0.000, precision 0.280 — every v1 question missed, top-5 flooded with v2. The 2:1 corpus imbalance, now measured.
- F1 (v2 contamination): v2 precision 0.756 — better than v1's 0.280 but still leaking (q001: v1|v1|v1 at ranks 3-5). Bidirectional, asymmetric.
- F2 (shim bait): q003 rank 1 is the deprecated class_validators.py shim, beating the real docs at rank 2. Invisible to version_precision (shim is tagged v2), visible in retrieved_ids — as designed. Second unplanted instance: q048.
- F3 (migration context): migration_diff MRR 0.170, worst of any answerable category. The P6 routing lever.
- F4: not measurable here (D21); parked to P7, metadata already in the golden set.

Verdict: my gate rule was "if P1 suddenly looks good, the harness is wrong." It doesn't — it fails in exactly the documented ways. Harness trusted; numbers are the floor.

Known artifact, deliberately not fixed: q001 resolves to serialization.md:002 but retrieval hit neighbors :006/:007 — right content, scored a miss because 1000-char chunking splits heading from prose. That's the argument *for* P3 AST chunking; widening pools to catch neighbors would be golden-set re-litigation.

Everything from P3 onward is compared against this table, one change at a time.

## Numbers (for README)
- Corpus: 290 files → 3,248 chunks (2:1 v2:v1 imbalance; 511 changelog chunks ≈ 16%)
- Full-corpus embed: ~33 API calls, ~$0.01–0.02 per ingest run
- Vectors: 1536 dims, cosine, one collection

## Watch-fors carried into hand-poking (Phase 1 exit)

1. **2:1 corpus imbalance** → unfiltered dense retrieval has a built-in v2 prior. I need to test contamination in BOTH directions — "asked v1, got v2" is probably the common failure.
2. **Changelog bulk** (16% of the corpus, and every API name appears in it) → changelog chunks may crowd out docs chunks. If I see it happening, that's a documented failure with an obvious P6 lever.
3. **Live bait**: v2 ships deprecated v1-named shims (`dict()`, `json()`, `parse_obj()`) that get chunked with version="v2" — prime contamination material.

---

## P2 hand-verification findings (before freezing)

- Fixed q029: the generator claimed parse_file was completely removed in v2. I grepped v2's main.py and it still exists as a deprecated shim. Changed the answer to "also deprecated."
- Fixed q032: the original answer used populate_by_name, which was the v2.0 name. But v2.13.4's own rename map (_internal/_config.py, line 360) says the current name is validate_by_name, and the migration doc (line 345) mentions both — so the canonical terms now require both names. Worth noting: my first fix updated the terms but forgot the gt_answer. Another case of a fix not fully landing, caught on re-review.
- Resolved a contradiction: q018 said allow_mutation was removed, q028 said it was renamed. The source settles it — line 348 of _internal/_config.py lists it as a bare string in the removed-keys list, not a rename pair. So: removed. Rewrote q028.
- A close call worth remembering: the v2 worktree ships its own copy of pydantic/v1/ for backward compatibility. I checked Qdrant — zero chunks came from that folder, but only because my glob (pydantic/*.py) happens to be non-recursive. Had it been recursive, every eval number would have been sitting on wrongly-labeled chunks and I'd never have known.
- The generator's list of 10 questions it wasn't confident about turned up in golden_set_notes.md. It flagged q019, q022, and q047 — all three were already covered by my independent command-by-command verification.

## Parked for P7 (don't touch until then)

- How to score wrong terms: a good answer often needs to MENTION the old API just to say "don't use this anymore" — q001's own reference answer contains .dict(). A naive substring check would fail correct answers. The scorer has to distinguish "presented as the current way" from "mentioned as deprecated."
- The citation rule is still missing from answer.py's prompt (D22). Check the honesty rule while I'm in there.

## FREEZE

The golden set is frozen at 50 items, all hand-verified. From this commit on, the question and answer text never changes. The only field I may re-audit later is gt_evidence (after P3 re-chunking).

### P3 parking (from the audit)

- conversion_table.md is macro-templated junk ({{ placeholders }}, content injected at docs build time) — it produced 1 empty chunk in the corpus. Question for P3: should files like this be excluded from ingestion?
- Large-but-legitimate pools I've accepted and am done deliberating on: config.md (8), v1 dataclasses (7).

## Phase 3: Markdown, Python AST and changelog Parsers

### D29. Ingestion exclusion list: explicit named list, never a heuristic

Excluded from ingestion:
- All single-line mkdocstrings stubs (files whose entire content is a `::: module.path` directive)
- conversion_table.md (macro-templated `{{ placeholders }}`, content injected at docs build time — produced an empty chunk in P1)
- .benchmarks_table.md (hidden-dotted, generated file)
- pydantic-v1\docs\changelog.md — a 1-line include shell (`{!.changelog.md!}`) pointing at a build-time file that doesn't exist in the checkout; parsing it yields one junk chunk. The real v1 changelog input is pydantic-v1\HISTORY.md at the worktree root (1,337 lines, confirmed) — which is also Parser 3's actual v1 input source.

Why a named list and not a filter rule: a heuristic like "skip files under N chars" can silently eat legitimate docs. A hardcoded list is dumb but auditable — anyone can read exactly what was excluded and why.

Nothing of value is lost by dropping the stubs. Their "content" is auto-generated at docs-build time from the Python source, and Parser 2 (AST) chunks that same source directly — so the real content enters the index through the code lane, with symbol_name attached, which is strictly better than a template directive string.

### D30. Exclude the v2 announcement files from v1 ingestion

What: pydantic-v2.md (951 lines) and pydantic-v2-alpha.md (199 lines) — the v2 announcement/plan posts, published in the v1 docs era — are excluded from ingestion.

Why: their content-version contradicts their metadata-version by the documents' own nature. These are ~1,150 lines describing v2 APIs (model_dump, field_validator, the new config system) that live in the v1 worktree, so every chunk from them gets tagged version: v1 while the text teaches v2. That's contamination baked in at ingestion, not a retrieval failure: a correctly v1-filtered retrieval (v1 → {v1, both}) can legitimately serve a chunk whose content is v2. The worktree rule ("worktree source is the tag, period") is right for 288 files and wrong for exactly these 2, because these 2 are the only files whose subject is the other version.

The boundary line (for the inevitable "why not migration.md too?"): migration.md is about the transition and is tagged both by my earlier decision — its content and metadata agree. The announcement files have no both lane in the v1 worktree; their content and metadata disagree. That's the line.

Pre-registered hypothesis (written before measuring): these two files are prime suspects in the version_explicit_v1 baseline disaster (hit 0.000, precision 0.280), but suspects, not proven culprits — the 2:1 corpus prior is a co-defendant. Proof comes from the P3 re-run: if that row moves meaningfully after exclusion, the mechanism is confirmed; if it barely moves, the corpus prior was the dominant cause. Either outcome is a finding.

### D31. Second pre-registered hypothesis: migration_diff starvation

Parallel to D30's hypothesis, registered before the P3 re-run so it counts. If P1's ingestion only walked docs/, then HISTORY.md was never indexed — and migration questions were starved of exactly the "what changed in vX.Y" evidence they need, which would explain migration_diff's weak baseline (hit 0.333, MRR 0.170, the worst MRR of any answerable category).

Same structure as D30: suspect, not proven culprit. The P3 re-run is the judge — if migration_diff moves meaningfully once HISTORY.md enters via Parser 3, the starvation mechanism is confirmed; if it doesn't, the cause lies elsewhere (chunking, routing, or the P6 lever). Either outcome is a finding, and both hypotheses are committed in writing before measurement.

### D32: v2 HISTORY.md contains v1.x/v0.x release entries (first at line 2536)
Ingested as-is, tagged v2 per worktree rule (Option B, q003-shim treatment). PRE-REGISTERED SUSPECT: v2-tagged v1.x changelog chunks may hurt ver_prec on version_explicit_v1 / migration_diff. P3 baseline re-run is judge. D30's exclusion precedent considered and declined: duplicate-count check deferred, revisit at audit if suspect fires.

### D33. Collection DELETION in a separate dir

Took precaution of accidental deletion of collection by moving into another directory (scripts/danger_delete_collection.py). This cannot be imported elsewhere. When 'I CONFIRM' typed, this deletes the collection entirely.

### D34. ConfigDict (v2, 9,615 tok) exceeds embed cap; embed input truncated at 8,000 tokens, full text preserved in payload;