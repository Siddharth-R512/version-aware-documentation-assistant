# EVAL - Harness Design Brief - `eval/run.py`

**Scope:** Retrieval only. Deterministic. Zero LLM calls. Generation score shifted to last phase of project (Phase-7). This harness answers exactly one question: given a pipeline, how good is the retrieval against the frozen golden set?

This document outlines the design of my evaluation harness and the reasoning behind the architectural decisions.

## 1. The Shape of Harness

The harness is a single loop over 3 distinct phases:
1. **Resolve:** Translates each items `gt_evidence` (file_path::header) into a list of current chunk IDs by querying Qdrant payloads. This makes D19 executable; ground truth will be durable for the changes made in pipeline in the coming phases. The harness translates whatever chunk IDs present right now. Golden set never changes. Resolution step produces different IDs.
2. **Retrieve:** Run each question through the pipeline under test and takes the top 5 results.
3. **Score:** Campares the retrieved IDs against the resolved GT IDs, computes metrics and writes to CSVs.

ONE RUN EQUALS ONE CONFIG

## 2. Dir Layout
```text
eval/
    golden.jsonl    # Frozen, the harness READS this but NEVER WRITES
    run.py    # the harness
    configs/
        phase1_baseline.json
    results/
        phase1_baseline.csv    # one row per Question
        phase1_baseline_summary.csv    # per category summary
    explained/
        golden_set_documentation.md
        harness_design.md
```

## 3. Config per Phase JSON

I am using a config file to compare runs and the question of "which settings produced this CSV" mus be answerable from the artifact alone, avoiding git archeology

Minimal shape:
```json
{
    "name": "phase_baseline",
    "top_k": 5,
    "retrieval": "dense"
}
```

**NOTE:** About ## 2. Dir layout: the naming of files is based of `config.json`'s `name` field.

Schema is small. As i move to next phases where i introduce other concepts like reranking, hybrid weights, etc.. the schema will grow to accommodate.

## 4. The Resolver (Heart of Harness)
The resolver is the bridge between the ground truth and the actual database. It takes `gt_evidence` and figures out exactly which chunk IDs it correspond to in Qdrant **right now**. A question's final ground truth set is simply the union of all chunk IDs its evidence strings resolve to.
**How it matches:**
- One `gt_evidence` string formatted as "`source_file :: heading`".
- Split on `::` once. The file must match the payload's source_file exactly. the heading part must match by **containment** within **either the payload's `header_path` OR the chunk's `text`**.
> Reason: In Phase 1's naive fixed size chunking, `header_path` is empty but the prose like headers or python definitions lives inside the chunk's `text`.
> In Phase 3, `header_path` will be non empty and will become the primary matcher while `text` serves as a safeguard. This creates one uniform rule that works across all phases without phase-specific conditional branching.
- **Risk Migration:** Containment raises false positives. I am accepting this risk; audit report will show resolve chunk counts, and a suspiciously high count is a signal to tighten evidence as `gt_evidence` is editable post-freeze.
**Output:** The set of chunk IDs whose payloads matched. A question's GT set is the union across all its evidence strings.

### Audit Mode
Running `python -m eval.run --audit` executes only the resolver over all 50 items and prints a report:

*   Lists every evidence string → how many chunks it resolved to.
*   Provides a loud, unmissable warning for every evidence string that resolved to ZERO chunks.
*   Summary line: *N/45 answerable items fully resolvable*.

This replaces manual heading-grepping and re-runs automatically whenever chunking strategies change. 
*   **Rule:** Audit before computing metrics. If the audit shows unresolved evidence, I will fix the evidence strings (legal) or knowingly accept the miss. I will **never compute metrics on top of silently-empty GT sets**, as an empty GT set makes `hit@5 = 0` look like a retrieval failure when it is actually a resolution failure.