# Golden Eval Set Documentation — Pydantic v1/v2 RAG

50 questions (JSONL) probing 6 known failure modes of a dual-version Pydantic RAG pipeline. Quotas: version_explicit_v2 (10), version_explicit_v1 (5), version_agnostic (10), migration_diff (10), howto_usage (10), api_lookup (5). Five items are unanswerable traps: q010, q024, q033, q043, q050 — one per category except the v1 control group.

---

## Batch 1 — q001–q010 · version_explicit_v2

**What it tests:** Version contamination (failure mode 1) and prior-override (3). Every question names v2; every item has a tempting stale v1 answer listed in `wrong_terms`.

**Coverage:** The core v1→v2 method renames — `model_dump` / `model_dump_json` / `field_validator` / `model_validator` / `model_validate` / `model_validate_json` / `from_attributes` / `model_json_schema` / `model_fields` — each paired with its deprecated v1 counterpart (`.dict()`, `.json()`, `@validator`, `parse_obj`, `orm_mode`, `__fields__`, ...). Also includes "close but not canonical" traps like `dict(m)` (wrong-by-omission, failure mode 2).

**Trap (q010):** A pydantic-settings usage question (`env_prefix`) phrased as a v2 question. Nasty because v1's `docs/usage/settings.md` *does* document `env_prefix`, so retrieval surfaces confident-looking v1 chunks. Correct behavior: abstain.

**Convention set here:** Unanswerable items get `gt_version_scope: "any"`. No `wrong_term` substring-collides with a canonical term (verified per item).

---

## Batch 2 — q011–q020 · version_explicit_v1 (5) + version_agnostic (first 5)

**What it tests:**
- q011–q015: Control group + *reverse* contamination — v2 answers leaking into v1-scoped questions. `wrong_terms` hold the modern v2 API (`field_validator`, `model_dump`, `ConfigDict`). All 5 answerable.
- q016–q020: Silent version-scoping (failure mode 4). No version named, but the answer differs across versions; `gt_answer` explicitly states the scoping a good answer must include.

**Coverage:** v1 controls span `pre=True` validators, `orm_mode`/`from_orm`, `.dict(exclude_unset=)`, `allow_mutation`, `parse_raw`. Agnostic items cover `orm_mode` semantics, the `Optional`-without-default flip, immutability (`allow_mutation` vs `frozen`), int→str coercion removal, and `__root__` vs `RootModel`.

**Convention set here:** version_agnostic items have *empty* `wrong_terms` by design — both versions' APIs legitimately appear in a good answer; the check is "both canonical terms present," which forces dual-version framing.

**Flag:** q019 carries NEEDS_VERIFICATION (exact v2.13.4 coercion behavior) and uses the stem `"coerc"` as a term — confirm your checker accepts stems.

---

## Batch 3 — q021–q030 · version_agnostic (last 5) + migration_diff (first 5)

**What it tests:** Remaining scoping probes, then explicit "what changed" questions whose answers live in `docs/migration.md`.

**Coverage:** `Field(const=)` removal, union smart-mode vs left-to-right, `json_encoders` deprecation, `each_item` removal (agnostic); `BaseSettings` move, validator decorator replacements, `Config` → `ConfigDict`, `parse_raw`/`parse_file` fate, `construct` → `model_construct` (migration).

**Trap (q024):** SQLAlchemy `relationship()` / lazy-loading integration — third-party, out of corpus.

**Key deviation from spec:** migration_diff items have mostly *empty* `wrong_terms`, contra the original brief. Reason: these questions name the old API in the question itself, so any correct answer must repeat it — naive substring checking would fail every correct answer. Recommended: for this category, score on canonical-terms-present, or use an LLM judge for "old API presented as current."

**Boundary pair:** q026 (BaseSettings *removal* — answerable, it's in migration.md) vs q010 (settings *usage* — not). Tests both sides of the corpus line.

---

## Batch 4 — q031–q040 · migration_diff (last 5) + howto_usage (first 5)

**What it tests:** Remaining migration renames, then real "how do I" questions needing docs prose. `wrong_terms` resume being populated in howto_usage (questions don't name old APIs, so substring checks are safe again) — each trap is the v1 habit a parametric prior reaches for.

**Coverage:** `model_rebuild`, `populate_by_name`, `from_attributes`, `GetterDict` removal (migration); `mode='before'` validators, `field_serializer`, `validation_alias`/`AliasChoices`, `computed_field`, discriminated unions (howto).

**Trap (q033):** FastAPI internals question — the sharpest calibration trap in the set, because the corpus contains real `model_validate`/`from_orm` evidence that a miscalibrated system will stitch into a FastAPI claim it can't actually support.

**Note:** q040 (discriminated unions) is deliberately scoped "both" — landed in v1.9, so a good answer must not claim it's v2-only.

---

## Batch 5 — q041–q050 · howto_usage (last 5) + api_lookup (5)

**What it tests:** Remaining usage breadth, then the false-abstention probe (failure mode 5): api_lookup answers live primarily in *source signatures*, not docs prose. A system that abstains without a clean docs paragraph fails q046/q048 despite the answer being in corpus.

**Coverage:** strict mode, `TypeAdapter`, custom types via `Annotated`/`__get_pydantic_core_schema__`, pydantic dataclasses (howto); `field_validator` modes, `model_dump` kwargs, `model_copy` signature, `ValidationError` methods (api_lookup).

**Traps:** q043 (Docker secrets via pydantic-settings) and q050 (`SettingsConfigDict` params — extra hard because `env_file` *does* appear in v1 docs, inviting a stale answer instead of abstention).

**Convention:** For source-file evidence, "nearest heading" becomes the `def`/decorator name (e.g. `pydantic/main.py :: def model_dump`).

**Flag:** q047 carries NEEDS_VERIFICATION (whether `fallback`/`serialize_as_any` exist at exactly v2.13.4).

---

## Before freezing the set

1. Hand-verify the 10-item low-confidence checklist (delivered with batch 5), especially q047, q019, q022.
2. Grep both worktrees to confirm exact `gt_evidence` heading strings — paths are reliable, heading text is approximate.
3. Sanity check: 50 lines, quotas 10/5/10/10/10/5, exactly 5 `answerable: false`, no wrong-term/canonical-term substring collisions within an item.
4. Decide the migration_diff scoring policy (see Batch 3 deviation).