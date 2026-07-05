# Corpus Map

Pydantic-v2/docs/migration.md: Every X in V1 became Y in V2. I have identified them based on category such as "BaseModel methods and attributes", "Validators", "Config", "Field()", "Generics, root types, ad-hoc validation", "Contrainst Types", & "Packages moved to other packages/modules", "Deprecated"

Markdown files point to example codes. It references those files. Here is an example.

```
└── 📁usage
    ├── dataclasses.md --> (12) files
    ├── devtools.md -->  (2)
    ├── exporting_models.md -->  (16)
    ├── model_config.md -->  (9)
    ├── models.md -->  (36)
    ├── mypy.md -->  (1)
    ├── postponed_annotations.md -->  (6)
    ├── rich_pydantic.png -->  (None)
    ├── rich.md -->  (None)
    ├── schema.md -->  (9)
    ├── settings.md -->  (7)
    ├── types.md -->  (32)
    ├── validation_decorator.md -->  (9)
    └── validators.md -->  (7)
```

| Parent | Dir | Include? Or no? notsure? |
|---|---|---|
| ./pydantic-v1 | 📁.github | NO |
| | 📁changes | NO |
| ./pydantic-v1/docs | 📁blog | NO |
| | 📁build | NO |
| | 📁examples (.py files all) | YES |
| | 📁extra (js, css, etc) | NO |
| | 📁img (png) | NO |
| | 📁theme | NO |
| | 📁usage (Only .md) | YES |
| | 📁usage (png) | NO |
| | .benchmarks_table.md | NO |
| | Changelog.md | YES |
| | datamodel_code_generator.md | YES |
| | PNG | NO |
| | hypothesis_plugin.md | YES |
| | Index.md | YES |
| | Install.md | YES |
| | SVG | NO |
| | mypy_plugin.md | YES |
| | pycharm_plugin.md | YES |
| | requirements.txt | NO |
| | visual_studio_code.md | YES |
| | Pydantic (all .py) | YES |
| ./pydantic-v1/pydantic | 📁v1 | NO |
| ./pydantic-v1 | 📁tests | NO |
| | .gitignore | NO |
| | .pre-commit-config.yaml | NO |
| | build-docs.sh | NO |
| | HISTORY.md | YES |
| | LICENSE | NO |
| | Makefile | NO |
| | MANIFEST.in | NO |
| | mkdocs.yml | NO |
| | pyproject.toml | NO |
| | README.md | NO |
| | requirements.txt | NO |
| | setup.cfg | NO |
| | setup.py | NO |
| ./pydantic-v2 | 📁.github | NO |
| | 📁.hyperlint | NO |
| ./pydantic-v2/docs | 📁api (all .md) | NO |
| | 📁badge | NO |
| | 📁concepts (all .md) | YES |
| | 📁errors (all .md) | YES |
| | 📁examples (all .md) | YES |
| | 📁extra (js, css) | NO |
| | 📁img (PNG) | NO |
| | 📁integrations (all .md) | YES |
| | 📁internals (all .md) | YES |
| | 📁logos (PNG) | NO |
| | 📁plugins (.py, html, toml) | NO |
| | 📁theme (html) | NO |
| | contributing.md | NO |
| | PNG | NO |
| | help_with_pydantic.md | NO |
| | index.md | YES |
| | install.md | YES |
| | SVG | NO |
| | migration.md | YES |
| | pydantic_people.md | NO |
| | version-policy.md | YES |
| | why.md | YES |
| ./pydantic-v2/pydantic | 📁_internal (.py) | NO |
| | 📁deprecated (.py) | YES |
| | 📁experimental (.py) | YES |
| | 📁plugin | NO |
| | 📁v1 | NO |
| | All python | YES |
| | 📁pydantic-core | NO |
| | 📁release | NO |
| | 📁tests | NO |
| | .git-blame-ignore-revs | NO |
| | .gitignore | NO |
| | .markdownlint.yaml | NO |
| | .pre-commit-config.yaml | NO |
| | .yamlfmt.yaml | NO |
| | build-docs.sh | NO |
| | CITATION.cff | NO |
| | HISTORY.md | YES |
| | LICENSE | NO |
| | Makefile | NO |
| | mkdocs.yml | NO |
| | pyproject.toml | NO |
| | README.md | NO |
| | update_v1.sh | NO |
| | uv.lock | NO |


## The model

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Chunk(BaseModel):
    id: str
    text: str
    version: Literal["v1", "v2", "both"]
    release_label: str                      # e.g. "v1.10", "v2.13"
    chunk_type: Literal["prose", "code", "changelog", "migration"]
    source_file: str                        # repo-relative path
    header_path: list[str] = Field(default_factory=list)
    symbol_name: Optional[str] = None
    linked_files: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def code_chunks_name_their_symbol(self):
        if self.chunk_type == "code" and not self.symbol_name:
            raise ValueError("code chunks must carry a symbol_name")
        return self
```

## Why each field exists

| Field | Why it exists |
|---|---|
| `id` | A deterministic identifier (e.g. `v2:docs/concepts/validators.md#field-validators:03`) so re-ingesting the corpus updates chunks in place instead of duplicating them. |
| `text` | The actual content that gets embedded and shown to the LLM — everything else is metadata about this. |
| `version` | The hard filter that makes version-specific answers possible: a v2 query retrieves only `version in {"v2", "both"}`, which is what guarantees `@field_validator` and `@validator` never bleed into each other. |
| `release_label` | The precise docs snapshot ("v2.13"), separate from the coarse `version` lineage, so the citation footer can say "Source: docs/concepts/validators.md, v2.13" without inventing it at answer time. |
| `chunk_type` | Routes retrieval by query intent: migration queries hit `migration` chunks first, comparison queries pull `prose`/`code` from both versions, and `changelog` chunks answer "when did X change." |
| `source_file` | The repo-relative path that anchors every citation and lets you label claims as documented (has a source) versus inferred (doesn't). |
| `header_path` | The markdown breadcrumb (e.g. `["Validators", "Field validators"]`) that gives a small chunk its surrounding context for both embedding quality and human-readable citations. |
| `symbol_name` | The API name a code chunk demonstrates (`field_validator`, `ConfigDict`), which is the join key for comparison answers: pair the v1 chunk and v2 chunk that share a concept. |
| `linked_files` | Preserves your corpus's structure where v1 markdown pages point at `docs/examples/*.py`, so at answer time a prose chunk can pull in the exact runnable example it references. |

## Design decisions worth writing down now

**`version` allows `"both"`.** `migration.md` lives in the v2 repo but is inherently about both versions. Tagging it `"both"` keeps the filter logic trivial (`version in {requested_version, "both"}`) instead of special-casing migration content inside the version filter. `chunk_type="migration"` still marks it for intent routing.

**`symbol_name` is the comparison join key.** For "how did model config change between v1 and v2," retrieval runs twice (once per version filter) and the answer builder pairs chunks by shared or mapped symbol names (`Config` ↔ `ConfigDict`). The migration guide's "X became Y" tables are the source for that mapping — worth extracting into a small lookup during ingestion, but the mapping is derived data, not a chunk field.

**Changelog chunks reuse the same shape.** A `HISTORY.md` entry becomes `chunk_type="changelog"` with `header_path` holding the release heading (e.g. `["v2.5.0"]`) and `release_label` set from that heading — no extra fields needed.

**What was deliberately left out.** No `embedding` field (storage concern, not schema concern — keep vectors in the index keyed by `id`); no `language` field (all included code is Python per your corpus map; add it only if you later ingest pydantic-core Rust); no `token_count` (computable, not authored).

## How the three query types consume this schema

Version-specific: filter `version`, answer, cite `source_file` + `release_label`. Comparison: two filtered retrievals joined on `symbol_name`, each side cited to its own `version`. Migration: retrieve `chunk_type="migration"` first, supplement with `version="v1"` and `version="v2"` chunks, and use presence/absence of a `source_file`-backed chunk to label each claim documented vs. inferred.

## Why: reasoning behind the include/exclude decisions

### Blanket rules (apply everywhere, both versions)

| Decision | Why |
|---|---|
| Exclude `tests/` | Test code demonstrates internal invariants, not user-facing usage; retrieving a `test_edge_cases.py` snippet as an "answer" would be misleading. |
| Exclude `.github/`, CI configs, dotfiles, `Makefile`, `build-docs.sh`, `mkdocs.yml`, lockfiles | Build/repo plumbing — zero documentation value, pure retrieval noise. |
| Exclude images, logos, css, js, html themes | Not text; nothing to embed. |
| Exclude `pyproject.toml`, `setup.py`, `requirements*.txt` | Dependency pins for building the library/docs, not answers to user questions. |
| Exclude `README.md` (both repos) | Marketing/landing content that duplicates `docs/index.md` with less structure; keeping both would create near-duplicate chunks competing in retrieval. |
| Include `HISTORY.md` (both repos) | The changelog is the ground truth for "when did X change" — feeds `chunk_type="changelog"`. |

### pydantic-v1 specifics

| Decision | Why |
|---|---|
| Include `docs/usage/*.md` | The core v1 prose documentation — the heart of the v1 corpus. |
| Include `docs/examples/*.py` (indexed separately, linked via `linked_files`) | v1 markdown *references* these files instead of embedding code; without them, prose chunks say "see example" with no code. Indexed as their own chunks rather than inlined, joined to prose by metadata. |
| Exclude `docs/blog/` | The two posts are v2 announcement essays sitting inside the v1 repo — indexing them as `version="v1"` is self-inflicted contamination. |
| Exclude `docs/build/` | Scripts that build the docs site (including the machinery that injects example files) — tooling, not documentation. |
| Exclude `changes/` | Changelog *fragments* + build script; the assembled history already lives in `HISTORY.md`, so including both duplicates content. |
| Include `mypy_plugin.md`, `pycharm_plugin.md`, `visual_studio_code.md`, `hypothesis_plugin.md`, `datamodel_code_generator.md` | Symmetry rule: v2's `docs/integrations/` covers the same tools and is included. Asymmetric coverage would make "does v1 have a mypy plugin?" retrieve only v2 content and imply the wrong answer. |
| Exclude `.benchmarks_table.md` | Auto-generated performance table; stale numbers, no conceptual content. |
| Include `pydantic/*.py` (top level) | Source docstrings are the v1 API reference — v1 has no `docs/api/` folder, so source is the only API-level documentation. |
| Exclude `pydantic/v1/` (inside the v1 repo) | Exclude pydantic/v1/ (inside the v1 repo) — a re-export shim layer (from pydantic.X import *) added in 1.10.17 for forward-compat with v2's pydantic.v1 import path. No docstrings or real content; indexing it adds pure noise. Verified via file-hash comparison: zero files match the real modules. |

### pydantic-v2 specifics

| Decision | Why |
|---|---|
| Include `docs/concepts/`, `docs/errors/`, `docs/examples/`, `docs/internals/` | The core v2 prose. Note `docs/examples/` here is real `.md` prose (unlike v1's `.py` example files — the two versions solved "examples" differently). |
| **Exclude `docs/api/`** | These files are mkdocstrings stubs (`::: pydantic.main.BaseModel`) — directives for the docs build system, nearly empty in the raw repo. Ingesting them yields garbage chunks whose whole text is a directive. API reference coverage comes from AST-parsing docstrings in `pydantic/**/*.py` instead. |
| Include `docs/integrations/` | User-facing "pydantic + tool X" guides; frequent real-world question territory (mypy, VS Code, hypothesis). |
| Include `migration.md` with `version="both"`, `chunk_type="migration"` | The single most valuable file for migration queries; tagged "both" because it is inherently about both versions despite living in the v2 repo. |
| Include `why.md`, `version-policy.md` | `why.md` explains the rationale for v2's redesign (directly useful for migration answers); `version-policy.md` defines what v1/v2 support actually means. |
| Exclude `pydantic_people.md`, `contributing.md`, `help_with_pydantic.md` | Community/contributor pages — no API content. |
| Exclude `docs/plugins/`, `docs/badge/`, `.hyperlint/` | Docs-site build machinery and lint configs. |
| **Exclude `pydantic/v1/`** | The vendored v1 compat layer inside the v2 package. Indexing it as `version="v2"` would be the project's namesake failure — v1 code labeled v2. The highest-stakes exclusion in the map. |
| **Exclude `pydantic/_internal/`** | ~30 files of private implementation (`_generate_schema.py` etc.). Users never call these; retrieving them produces answers that cite private APIs. The user-facing architecture story is already covered by `docs/internals/*.md`. Bonus hazard avoided: `_decorators_v1.py` is a contamination trap by filename alone. Logged as a scope cut — revisit if the assistant ever needs to answer contributor-level questions. |
| Include `pydantic/deprecated/` (tagged appropriately) | Deprecation shims are gold for migration answers ("`parse_obj_as` still importable but deprecated — use `TypeAdapter`"). Chunks must carry a deprecation signal so they're never presented as the recommended v2 way. |
| Include `pydantic/experimental/` | User-facing (people ask about `pipeline`); small. Risk accepted: answers may present unstable API as settled — mitigate at generation time if it shows up in eval failures. |
| Exclude `pydantic/plugin/` | Plugin *loader* plumbing, not documentation of user-facing behavior. |
| Exclude `pydantic-core/` | An entire vendored Rust engine — wrong language, implementation detail, would dwarf the docs corpus in raw size. |
| Exclude `release/` | Release automation scripts. |
| Include `pydantic/*.py` (top level, minus exclusions above) | v2 API reference via docstrings — same role as v1 source, and the replacement for the excluded `docs/api/` stubs. **Known trap (found empirically via grep): `main.py` line ~1323+ contains deprecated v1-named shims (`dict()`, `json()`, `parse_obj()`...). The AST parser must detect the deprecation decorator on these, or v2 chunks will recommend v1 method names — contamination generated from correctly-labeled v2 source.** |