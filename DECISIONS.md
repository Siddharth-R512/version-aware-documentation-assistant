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
`INCLUDE` = list of `(root, version, glob_pattern)` tuples mirroring the corpus map one-to-one. Loud failure: any pattern matching zero files raises FileNotFoundError. `__init__.py` skipped uniformly in both versions. `migration.md` → version `"both"`. Result: 290 files (v1: 196, v2: 94).

### D10. Naive chunking: 1000 chars / 200 overlap, character-based
Deliberately dumb baseline — this is the "before" photo for Phase 3. Character-based (not word/token-based) for maximal simplicity. Skips pure-whitespace windows; breaks after the window that reaches EOF to avoid a duplicate pure-overlap tail chunk. Result: 3,248 chunks (v2: 2123, v1: 1062, both: 63; prose: 2737, changelog: 511).

### D11. chunk_type: only "prose" and "changelog" in v0
HISTORY.md → changelog; everything else → prose, including .py files. v0 doesn't claim to understand code; the Phase 3 AST parser earns the "code" label. (Option (a), locked.)

### D12. Chunk ID format: `{version}:{source_file}:{index:03d}`
`source_file` is worktree-relative posix path (portable, no absolute Windows paths in IDs). Zero-padding is 3 digits because files exceed 99 chunks (v2 main.py = 107); mixed-width indexes would break string sort and pin inconsistent IDs into Phase 2 ground truth.

### D13. Embedding stage: batches of ~100, pure function, no cache
~100 texts/call ≈ 25K tokens — comfortably under the 2,048-inputs-per-request cap and the ~community-observed ~300K-tokens-per-request ceiling; 3,248 chunks = 33 calls. Order verified per item (`item.index == j`) and in aggregate (`len(vectors) == len(chunks)`) because these vectors get pinned as Phase 2 ground truth. No retry/async/caching — a failed run costs 2 cents to redo. Persistence is Qdrant's job, not a second cache layer.

### D14. Embed bare chunk text only
No metadata prepended into the embedded string. Vector = for finding; payload = for filtering and citing. Metadata-enriched embedding is a legitimate technique but banned from the naive baseline; if it appears, it appears as a measured experiment.

### D15. Qdrant point IDs: uuid5(NAMESPACE_URL, chunk.id)
Qdrant requires int/UUID point IDs; chunk IDs are strings. uuid5 is a deterministic hash: same chunk ID → same point ID on every run → upsert overwrites in place → **idempotent re-ingest** (verified: two full runs, count stable at 3,248). uuid4/sequential ints rejected: random or order-dependent IDs duplicate the corpus on every re-run. The readable string `chunk.id` also lives in the payload — the UUID is Qdrant plumbing; the string ID is for humans and the eval harness.

### D16. Full chunk (including text) stored as payload
`model_dump()` of the whole Chunk. Qdrant is the single store; retrieval never touches the filesystem. Upserts batched (100/call, `wait=True`) to stay under payload-size limits and make post-write verification non-racy. Verification is **server-side** (`client.count(exact=True)`) — the local list says what was intended, the server says what landed.

### D17. Idempotency boundary (known edge)
uuid5 gives idempotency for a **frozen** corpus, not synchronization for a changing one. If a file shrank, high-index chunks would be orphaned (upsert never deletes). Doesn't apply here (worktrees are pinned), but chunker changes in Phase 3 change every ID — policy: `delete_collection` + full re-ingest (~2 cents) on any chunking change. Production answer at scale: content-hash IDs + tombstoning.

### D18. Loud failure over silent skip (design rule, applied twice)
FileNotFoundError on empty glob; assert (not `return None`) on chunk/vector length mismatch. Impossible states crash; expected states get handled.

### D19. Eval ground truth keyed by file+heading (amends earlier chunk ID decision)
Chunk IDs remain stable during ingestion but not for evaluations. Re-chunking in Phase 3 changes chunk boundaries breaking any ground truth keyed on chunk IDs. The eval set will now store file path + nearest Heading which is resolved to current chunk ID during run time, keeping eval strategies stable across chunking strategies and enabling fair comparisons.

### D20. `version="both"` counts as correct (1.0) for version precision
A `both` chunk cannot represent contamination. Version precision should measure only wrong-version retrieval Relevance is captured by `Hit@K` and `MRR` avoiding overlap between metrics.

### D21. P2 harness evaluates retrieval only; generation evaluation deferred
Phase 2 harness measures retrieval deterministically using chunk ID matching, avoiding LLM costs and variability However, eval questions are labeled now with generation-scoring metadata (e.g., required terms, deprecated terms answerability) so answer evaluation can be added in Phase 7 without relabeling.

### D22. Citation requirement deferred to Phase 7
Since citations concern answer generation rather than retrieval, implementation is deferred to Phase 7 and recorded to maintain design traceability.

### D23. Resolver rule: file exact-match + normalized heading containment + version filter
An evidence string `file :: heading` resolves to a chunk when: source_file matches exactly, AND the heading is contained in the joined header_path OR the chunk text (both sides lowercased, backticks stripped; file paths NOT normalized). P1 chunks have empty header_path, so text containment does all the work; P3's parser makes header_path primary. On top of that, a version filter: scope v1 accepts {v1, both}, v2 accepts {v2, both}, both/any accepts all. Without the filter, identical filenames across the two worktrees (e.g. `def construct` in both main.py files) put v1 chunks
into v2 ground-truth pools — the harness would literally reward contamination. Rejected: raw string match (backticks and Title Case in real headings killed 33/78 evidence strings before normalization).

### D24. Evidence-string conventions (learned from the audit)
- Where content is heading-less, evidence may be a distinctive single-line TEXT PHRASE. Phrases must not cross line breaks — chunk text has \n where rendered docs show spaces.
- Evidence must name the MOST SPECIFIC heading containing the answer. Single-word headings bloat pools via text containment (alias.md "Alias" resolved 18 chunks).
- Evidence must support THAT question's answer. Wrong-topic resolution is worse than a zero; deleting a dead string is fine — evidence lists have no quota.
- Audit-before-metrics rule: never compute metrics over silently-empty GT pools. `--audit` mode exists for this.

### D25. NA convention: empty string, never 0; NAs excluded from all averages
first_gt_rank on a miss is NA (there is no rank), but mrr on a miss is 0.0 (a miss is a real score, not missing data) — treating mrr as NA would inflate averages by dropping exactly the failures. Unanswerable items: all metrics NA, retrieval still logged (P7 abstention asset). A 0 where NA belongs poisons every downstream mean.

### D26. version_precision is defined only for scope v1/v2; NA for any AND both
(D20 clarification.) The scorer must agree with the resolver: wherever the resolver accepts all versions as valid evidence (scope any/both), there is no "correct version lane" to measure, so version_precision is NA. Caught live: the first implementation only NA'd "any"; a scope-both question then scored 0.0 because the acceptable set collapsed to {both} and punished perfectly valid v1/v2 chunks. The 0.0 was a plausible-looking fake finding — the version_agnostic-must-be-all-NA sanity check caught it before it reached the baseline writeup.

### D27. Harness imports the real retrieval; shaping lives in the harness
run.py imports retrieve() from src/retrieve.py — never a reimplementation (copies drift). retrieve() keeps returning full ScoredPoints because answer.py also consumes it; the harness's retrieve_top5() adapter extracts (id, version) tuples on its own side. The application isn't modified to suit the test harness.
Rejected: making retrieve() return tuples (breaks the other consumer).

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

Gate check — do the numbers reproduce the P1 hand-poked findings?
- F5 (reverse contamination): version_explicit_v1 is the headline — hit 0.000, precision 0.280. Every v1 question missed; top-5 dominated by v2 chunks. The 2:1 corpus imbalance prior, now measured instead of anecdotal.
- F1 (v2 contamination): version_explicit_v2 precision 0.756 — better than v1's 0.280 but still leaking (q001: v1|v1|v1 in ranks 3-5). Bidirectional, asymmetric.
- F2 (shim bait): q003 rank 1 = v2:pydantic/deprecated/class_validators.py:007, outranking the real docs chunk at rank 2. Invisible to version_precision (shim IS tagged v2) — visible in retrieved_ids, as designed. Second unplanted instance: q048 rank 1 = deprecated/copy_internals.py, on a miss.
- F3 (migration context): migration_diff hit 0.333 / MRR 0.170 — worst MRR of any answerable category. P6 routing lever.
- F4 (generation contradicts evidence): not measurable by this harness (D21). Parked to P7 with its metadata already in the golden set.
Verdict: gate rule was "if P1 looks good, the harness is wrong." P1 does not look good, in exactly the documented ways. Harness trusted; numbers are the floor.

Known measurement artifact (do NOT fix by widening pools): q001's pool resolves to serialization.md:002; retrieval hit neighbors :006/:007 — same file, right content, scored a miss because naive 1000-char chunking splits heading from prose. P1 resolution-via-text is a blunt instrument; the baseline is a floor. This artifact IS the argument for P3 AST chunking. Widening evidence to catch neighbors would be golden-set re-litigation.

Everything from P3 onward is compared against this table, one change at a time.
---

## Numbers (for README)
- Corpus: 290 files → 3,248 chunks (2:1 v2:v1 imbalance; 511 changelog chunks ≈ 16%)
- Full-corpus embed: ~33 API calls, ~$0.01–0.02 per ingest run
- Vectors: 1536 dims, cosine, one collection

## Watch-fors carried into hand-poking (Phase 1 exit)
1. **2:1 corpus imbalance** → unfiltered dense retrieval has a v2 prior; test contamination in BOTH directions ("asked v1 got v2" may be the common one).
2. **Changelog bulk** (16% of corpus, every API name appears there) → changelog chunks may crowd out docs chunks. If observed: documented failure with an obvious P6 lever.
3. **Live bait**: v2's deprecated v1-named shims (`dict()`, `json()`, `parse_obj()`) are chunked with version="v2" — prime contamination material.

---

## P2 hand-verification findings (before freezing)

- Fixed q029: the generator said parse_file was completely removed in v2. I grepped v2's main.py and found it still exists as a deprecated shim. Changed the answer to "also deprecated."
- Fixed q032: the original answer used populate_by_name, which was the v2.0 name. But v2.13.4's own rename map (_internal/_config.py, line 360) says the current name is validate_by_name, and the migration doc (line 345) mentions both. So the canonical terms now require both names. Note: my first fix updated the terms but forgot the gt_answer — another case of a fix not fully landing, caught on re-review.
- Resolved a contradiction: q018 said allow_mutation was removed, q028 said it was renamed. The source settles it..line 348 of _internal/_config.py lists it as a bare string in the removed-keys list, not as a rename pair. So it was removed. Rewrote q028.
- Close call worth remembering: the v2 worktree ships its own copy of pydantic/v1/ for backward compatibility. I checked Qdrant — zero chunks came from that folder, but only because our glob (pydantic/*.py) happens to be non-recursive. If it had been recursive, every eval number would have been sitting on wrongly-labeled chunks without us knowing.
- The generator's list of 10 questions it wasn't confident about turned up in golden_set_notes.md. It flagged q019, q022, and q047 — all three were already covered by our independent command-by-command verification.

## Parked for P7 (don't touch until then)

- How to score wrong terms: a good answer often needs to MENTION the old API just to say "don't use this anymore" (q001's own reference answer contains .dict()). A naive substring check would fail correct answers. The scorer has to tell the difference between "presented as the current way" and "mentioned as deprecated."
- The citation rule is still missing from answer.py's prompt (D22). Check the honesty rule while in there.

## FREEZE

The golden set is frozen at 50 items, all hand-verified. From this commit on, the question and answer text never changes. The only field that may be re-audited later is gt_evidence (after P3 re-chunking).

### P3 parking (from the audit)
- conversion_table.md is macro-templated junk ({{ placeholders }}, content injected at docs build time) — 1 empty chunk in corpus. Question for P3: exclude such files from ingestion?
- Accepted large-but-legitimate pools, done deliberating: config.md (8), v1 dataclasses (7).