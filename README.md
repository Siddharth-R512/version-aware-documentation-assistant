# Version-Aware Documentation Assistant

**A RAG Pipeline over Pydantic's documentation that answers version specific questions (v1 & v2) without cross contamination and more importantly an evaluation suite that proves whether it actually does.**

> Every improvement in this project is majorly based on evaluation suite (a frozen golden set) tested on current phase. 

## The Problem

Pydantic V1 and V2 are incompatible major versions of the same library. V2 completely breaks backward compatibility meaning you existing pydantic code will crash and fail until you rewrite it manually. Almost every core function, configuration settings and validator decorator used in V1 have been renamed or rewritten in v2.

A naive RAG system over these versions answers v2 queries with v1 code (or vice versa) and the answer looks plausible because `model.dict()` was real once until it was replaced by `model.model_dump()`. This project measure that failure precisely then fixes it one change at a time.

## Current status

| Phase | What | Status |
|-------|------|--------|
| P0 | Scope, corpus, architecture decisions | ✅ Done |
| P1 | Deliberately naive baseline (1000-char chunks, dense-only retrieval) | ✅ Done |
| P2 | Golden eval set + deterministic retrieval harness + measured baseline | ✅ **Done** |
| P3 | Real chunking (3 parsers, AST-based for code) | ⏳ Next |
| P4 | Hybrid retrieval (BM25 + RRF) | Planned |
| P5 | Reranker | Planned |
| P6 | Query routing (version-specific / comparison / migration) | Planned |
| P7 | Generation quality + abstention scoring | Planned |

## Baseline results (Phase 1, measured by the Phase 2 harness)

Dense retrieval only, top-5, 50 hand-verified questions:

| Category | n | hit@5 | MRR | version precision |
|---|---|---|---|---|
| version_explicit_v1 | 5 | **0.000** | 0.000 | **0.280** |
| version_explicit_v2 | 10 | 0.444 | 0.278 | 0.756 |
| migration_diff | 10 | 0.333 | 0.170 | 0.622 |
| howto_usage | 10 | 0.333 | 0.204 | 0.657 |
| api_lookup | 5 | 0.750 | 0.750 | 0.650 |
| version_agnostic | 10 | 0.556 | 0.389 | NA |
| **ALL** | 50 | 0.400 | 0.275 | 0.618 |

### What do these numbers say:
- **Reverse Contamination is the highlight.** Every v1-scoped question missed; top-5 results were dominated by v2 chunks. Reason: corpus is 2:1 v2 heavy and unfiltered dense retrieval inherits that prior.
- **Contamination is bidirectional but asymmetric.** v2 questions leak v1 chunks too (precision = 0.756) just less severe.
- 

### What category means:
1. `version_explicit_v2`: 
Questions that explicitly name pydantic V2 in the phrasing (eg, in v2, how do I...). Each one has a well known, tempting v1 answer that a contaminated retrieval would produce. This is an effective test for version contamination because they explicitly specify version and leave no room for ambiguity. As a result, any reference to V1 API is an obvious failure.
The `wrong_terms` field carries deprecated equivalents, enabling incorrect version usage to be detected at a glance.

2. `version_explicit_v1`: __Same as version_explicit_v2__
If the system fails v2-scoped questions but passes these, contamination flows one way; if it fails both, version filtering is broken generally. This is the only category with no unanswerable trap, keeping the control clean.

3. `version_agnostic`:
Questions that name no version at all but whose answers genuinely differ between v1 and v2. A correct response should not assume a version. Instead, it should explain how the answer differs across versions. For example, saying "orm_mode does X" is correct for v1, but incomplete because v2 uses a different API. These questions test whether the model recognises when version context is necessary, even if the user does not ask for it explicitly. Unlike the other categories, `wrong_terms` is left empty because APIs from both versions can appear in a correct answer. Instead, grading checks that the response includes the canonical terms for both versions, ensuring the answer covers both v1 and v2.

4. `migration_diff`:
Explicity comparative questions: "What replaced X", "Does Y exist in V2?", "is Z still supportive?". The answer concetrate in migration guide (`migration.md`) that this category also functions as a retrieval test for that document specifically.

5. `howto_usage`: "How do I..." developer questions
This category evaluates overall answer quality rather than a specific version-contamination failure. The `wrong_terms` field captures common v1 APIs that a model might mistakenly use, while also identifying answers that work but omit the recommended or canonical approach.

6. `api_lookup`:
Questions about exact API signatures, supported parameters, or accepted decorator modes. The required information is often found in source code or type signatures rather than documentation. This category tests whether the system can extract and use such information instead of incorrectly responding that the answer is unavailable.

### Additionally..
Across these categories, **five questions** (one in **each category** except `v1_control`) **are intentionally unanswerable.** They sound plausible but cannot be answered from the corpus, testing whether the system abstains instead of hallucinating from related information.

## How the evaluation works
**Golden Set** -> 50 questions across 6 categories. Each of them hand verified against the actual source trees. The question and answer text never change again. 5 question are deliberately unanswerable - abstention bait.

**Ground truth survives re-chunking.** GT is keyed to `source_file::heading`, not chunk IDs and resolved to chunk IDs at runtime, never cached. Phase 3 will change the chunk boundary; the eval set won't care.

**Resolver with an audit mode.** Evidence resolution is exact file match + normalized heading containment + a version filter (without the filter, identical \ filenames across the two source trees would put v1 chunks into v2 ground-truth pools — the harness would literally contaminate itself). `--audit` verifies every evidence string resolves to real chunks *before* any metric is computed. First audit run: 17/45 items resolvable. Diagnosed as 3 patterns (not 33 bugs), fixed, re-audited to 45/45 — and caught 9 evidence strings the LLM generator had written from memory of what docs usually look like, rather than from the files.

**Deterministic, LLM-free scoring.** hit@5, MRR@5, and a custom **version precision** metric (fraction of top-5 in the correct version's lane; `both`-tagged chunks count as correct; NA for version-agnostic questions — a metric that doesn't apply reports NA, never a free 1.0 or a fake 0). NA is empty-string in the CSVs and excluded from every mean. The summary step asserts the NA plumbing holds — an assert that has already caught one real bug before it reached this README.

## Architecture (current)

```
pydantic-v1/ + pydantic-v2/ (git worktrees, pinned tags v1.10.26 / v2.13.4)
        │  290 files
        ▼
naive chunker (1000 chars / 200 overlap)          ← replaced in P3
        │  3,248 chunks, version-tagged v1|v2|both
        ▼
text-embedding-3-small → Qdrant (one collection, payload = full chunk)
        │
        ▼
dense top-k retrieval ──→ answer generation (gpt-4o-mini)
        │
        ▼
eval/run.py: resolve GT → retrieve → score → detail CSV + summary CSV
```

Framework-free by design.. no LangChain/LlamaIndex.

## Decision log

Every non-obvious choice is recorded in [`DECISIONS.md`](DECISIONS.md) as *decision → why → alternative rejected*