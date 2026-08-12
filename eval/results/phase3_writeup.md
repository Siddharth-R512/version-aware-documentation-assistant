# Phase 3 Evaluation: Structural Chunking

## 1. Setup & Baseline:
**Phase 3 is fundamentally altered corpus structure**. The chunk count went from **3248 -> 3599**. Prose chunks reduced to 978 chunks as prose now represent only `.md` file (excluding `HISTORY.md`)

When i ran `--audit` over P3, it said "Summary: 45/45 answerable items fully resolvable." on the first run. This was a red flag because the P3 went through structural changes that ground truth headings inevitably break or shift. So the measurement instrument underwent rigorous repair.

This shifted the denominator for Phase 3 from 45 down to 44 scored items. To ensure an honest comparison, the baseline was recomputed over those exact 44 shared items (dropping the phantom q037). Below is the comparison of the final Phase 3 run against the shared-44 D28 baseline:

| Metric | P2 | P3 (final) | Δ |
| :--- | :--- | :--- | :--- |
| **hit@5** | 0.409 | 0.545 | +0.136 |
| **MRR** | 0.281 | 0.332 | +0.051 |
| **version precision** | 0.624 | 0.545 | −0.079 |

> This table supersedes D28 as the comparison target for Phase 4+.

## 2. Honest Remarks: Hit@5 and MRR
While a +0.136 jump in hit@5 looks good, it is inflated. Large document sections inflate the target pool under structural chunking, making hit@5 an overly generous metric. When a target pool grows to 20+ chunks, hitting any of them is considered a success. My data proves this: every query that gained a hit also had a larger resolution pool.

Because of this generosity, MRR (+0.051) is the honest headline. Retrieval quality improved, but the system still struggles to rank the absolute best chunk at the #1 spot.

## 3. What worked: COntext and migration
By grouping headings and list items together, structural chunking preserves narrative context. This was a massive win for `migration_diff` queries. They saw a staggering, MRR-backed gain of 0.170 → 0.444.

My specific prediction that "q001-class misses shrink" played out perfectly. Because the context is now unified under structural headings, `q001` (a `version_explicit_v2` serialization query) jumped from failing entirely to rank 1, successfully hitting `serialization.md :: Python mode`.

## 4. The Trade-offs: Code & Version Precision
- Version precision dropped (−0.079): The v1 share of v2-explicit retrievals rose from 32% to 41%. The intruder census shows the contamination is driven by prose twins (34 prose / 20 code / 4 changelog), led by v1 exporting_models.md (10 slots) and models.md (9 slots). Structural chunking made v1 sections topically concentrated, so they now heavily outcompete their v2 twins for v2 queries. The takeaway: chunking quality cannot fix version contamination—only routing can (Phase 6).

- API lookups dropped (0.750 -> 0.500): Dense vectors genuinely struggle to pinpoint exact-symbol code chunks buried in massive code blocks. This is proven by q047: its ground truth resolves correctly to the main.py symbol chunks, but they still miss the top-5 after the key repair. This is my named BM25 test case for Phase 4.

- The Standing Wound (v1-explicit): This category barely moved (0.000 → 0.200 hit@5, MRR 0.067). It remains a known blind spot and is explicitly carried forward to the next phases.

## 5. The Preamble Problem
I found out that document introductions (specifically text placed before the first Markdown heading) are actively polluting results. The parser tags these as [Preamble]. Because they contain high-level, generic summaries loaded with library keywords, dense retrieval over-ranks them, stealing 10% of the top-5 slots.


> The valuable takeway is how phase 3 caught the evaluation system its own flaw. An artificial "45/45" audit masked a chain of errors which accidently created the phantom `q037` question. By fixing the resolver and 9 dead keys, it is a clean 44/44 audit. Crucially, fixing the measurement tools only shifted the final MRR by 0.004, proving main conclusion were pretty solid.