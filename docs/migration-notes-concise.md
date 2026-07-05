# Pydantic v1 → v2 Migration Notes

Source: `pydantic-v2/docs/migration.md`. Every "X in v1 became Y in v2" pair, organized by category. These pairs are contamination checkpoints: if the RAG chatbot emits the **v1** column when asked about v2, that's contamination.

## BaseModel methods & attributes

| v1 | v2 |
| --- | --- |
| `__fields__` | `model_fields` |
| `__private_attributes__` | `__pydantic_private__` |
| `__validators__` | `__pydantic_validator__` |
| `construct()` | `model_construct()` |
| `copy()` | `model_copy()` |
| `dict()` | `model_dump()` |
| `schema() / schema_json()` | `model_json_schema()` |
| `json()` | `model_dump_json()` |
| `parse_obj()` | `model_validate()` |
| `parse_raw()` | `model_validate_json()` (deprecated; for other formats, load the data then `model_validate()`) |
| `parse_file()` | deprecated — load the data yourself, then `model_validate()` |
| `from_orm()` | `model_validate()` with `from_attributes=True` in model config |
| `update_forward_refs()` | `model_rebuild()` |
| `__root__` field ("custom root model") | `RootModel` class (note: no `arbitrary_types_allowed` support) |
| `json_encoders` config for custom serialization | `@field_serializer`, `@model_serializer`, `@computed_field` decorators |
| `GetterDict` | removed (implementation detail of `orm_mode`, which is gone) |

## Validators

| v1 | v2 |
| --- | --- |
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |
| `@validate_arguments` | `@validate_call` |
| `@validator(..., each_item=True)` | annotate the container's type argument, e.g. `list[Annotated[int, Field(ge=0)]]` |
| `@validator(..., always=True)` | `Field(validate_default=True)` (note: type validators also run on defaults now) |
| validator kwarg `config` (a class) | `info.config` via `ValidationInfo` (config is now a dict) |
| validator kwarg `field` (a `ModelField`) | `info.field_name` → index into `cls.model_fields` (`ModelField` no longer exists) |
| `allow_reuse=True` kwarg | no longer needed — just delete it |
| `__get_validators__` (custom types) | `__get_pydantic_core_schema__` |
| `__modify_schema__` (custom types) | `__get_pydantic_json_schema__` |

Behavior changes (not renames, but eval-relevant):
- `TypeError` raised inside a validator is **no longer** wrapped into a `ValidationError`.
- `@root_validator` (if still used, deprecated) must set `skip_on_failure=True` explicitly.
- `@model_validator` may receive a model **instance** (not a dict) e.g. during `validate_assignment`.

## Config

| v1 | v2 |
| --- | --- |
| `class Config:` inner class | `model_config` dict (class attribute / `ConfigDict`) |
| `allow_population_by_field_name` | `populate_by_name` (or `validate_by_name` from v2.11) |
| `anystr_lower` | `str_to_lower` |
| `anystr_strip_whitespace` | `str_strip_whitespace` |
| `anystr_upper` | `str_to_upper` |
| `keep_untouched` | `ignored_types` |
| `max_anystr_length` | `str_max_length` |
| `min_anystr_length` | `str_min_length` |
| `orm_mode` | `from_attributes` |
| `schema_extra` | `json_schema_extra` |
| `validate_all` | `validate_default` |
| `allow_mutation` | removed — use `frozen` (inverse meaning) |
| `smart_union` | removed — smart is now the default `union_mode` |
| `underscore_attrs_are_private` | removed — v2 always behaves as if `True` |
| removed with no direct replacement | `error_msg_templates`, `fields` (use `Annotated`), `getter_dict`, `json_loads`, `json_dumps`, `copy_on_model_validation`, `post_init_call` |

## Field()

| v1 | v2 |
| --- | --- |
| arbitrary extra kwargs → JSON schema | `json_schema_extra={...}` dict |
| `min_items` | `min_length` |
| `max_items` | `max_length` |
| `regex` | `pattern` |
| `allow_mutation` | `frozen` |
| `final` | `typing.Final` type hint |
| `const`, `unique_items` | removed |
| `alias` property returns field name when unset | returns `None` when unset |
| constraints pushed into generics, e.g. `list[str] = Field(pattern=...)` | annotate the element: `list[Annotated[str, Field(pattern=...)]]` |

## Generics, root types, ad-hoc validation

| v1 | v2 |
| --- | --- |
| `pydantic.generics.GenericModel` | removed — `class MyModel(BaseModel, Generic[T])` directly |
| `parse_obj_as` | `TypeAdapter(...).validate_python(...)` |
| `schema_of` | `TypeAdapter(...).json_schema()` |
| `parse_raw_as`, `parse_file_as` | removed (use `TypeAdapter` / `model_validate_json`) |
| dataclass `__pydantic_model__` | removed — wrap the dataclass in `TypeAdapter` |
| dataclass `__post_init_post_parse__` | removed — `__post_init__` now runs *after* validation |
| parent-model config applies to vanilla dataclass fields | `config=` parameter on `@pydantic.dataclasses.dataclass` |

## Constrained types

| v1 | v2 |
| --- | --- |
| `ConstrainedInt`, `ConstrainedFloat`, `ConstrainedStr`, `ConstrainedBytes`, `ConstrainedDate`, `ConstrainedDecimal`, `ConstrainedList`, `ConstrainedSet`, `ConstrainedFrozenSet` | `Annotated[<type>, Field(...)]`; for `ConstrainedStr` specifically, `StringConstraints` |

## Moved to other packages / modules

| v1 | v2 |
| --- | --- |
| `pydantic.BaseSettings` | `pydantic_settings.BaseSettings` (separate `pydantic-settings` package; `parse_env_var` classmethod removed — customise settings sources instead) |
| `pydantic.color` | `pydantic_extra_types.color` |
| `pydantic.types.PaymentCardBrand` | `pydantic_extra_types.PaymentCardBrand` |
| `pydantic.types.PaymentCardNumber` | `pydantic_extra_types.PaymentCardNumber` |
| `pydantic.utils.version_info` | `pydantic.version.version_info` |
| `pydantic.error_wrappers.ValidationError` | `pydantic.ValidationError` |
| `pydantic.utils.to_camel` | `pydantic.alias_generators.to_pascal` ⚠️ name shift! |
| `pydantic.utils.to_lower_camel` | `pydantic.alias_generators.to_camel` ⚠️ name shift! |
| `pydantic.PyObject` | `pydantic.ImportString` |

⚠️ The `to_camel` pair is a great trap question: v1's `to_camel` = v2's `to_pascal`, and v1's `to_lower_camel` = v2's `to_camel`.

## Deprecated and moved (still importable, new path)

| v1 | v2 |
| --- | --- |
| `pydantic.tools.schema_of` | `pydantic.deprecated.tools.schema_of` |
| `pydantic.tools.parse_obj_as` | `pydantic.deprecated.tools.parse_obj_as` |
| `pydantic.tools.schema_json_of` | `pydantic.deprecated.tools.schema_json_of` |
| `pydantic.json.pydantic_encoder` | `pydantic.deprecated.json.pydantic_encoder` |
| `pydantic.validate_arguments` / `pydantic.decorator.validate_arguments` | `pydantic.deprecated.decorator.validate_arguments` |
| `pydantic.json.custom_pydantic_encoder` | `pydantic.deprecated.json.custom_pydantic_encoder` |
| `pydantic.json.ENCODERS_BY_TYPE` | `pydantic.deprecated.json.ENCODERS_BY_TYPE` |
| `pydantic.json.timedelta_isoformat` | `pydantic.deprecated.json.timedelta_isoformat` |
| `pydantic.class_validators.validator` | `pydantic.deprecated.class_validators.validator` |
| `pydantic.class_validators.root_validator` | `pydantic.deprecated.class_validators.root_validator` |
| `pydantic.utils.deep_update` | `pydantic.v1.utils.deep_update` |
| `pydantic.utils.GetterDict` | `pydantic.v1.utils.GetterDict` |
| `pydantic.utils.lenient_issubclass` | `pydantic.v1.utils.lenient_issubclass` |
| `pydantic.utils.lenient_isinstance` | `pydantic.v1.utils.lenient_isinstance` |
| `pydantic.utils.is_valid_field` | `pydantic.v1.utils.is_valid_field` |
| `pydantic.utils.update_not_none` | `pydantic.v1.utils.update_not_none` |
| `pydantic.utils.import_string` | `pydantic.v1.utils.import_string` |
| `pydantic.utils.Representation` | `pydantic.v1.utils.Representation` |
| `pydantic.utils.ROOT_KEY` | `pydantic.v1.utils.ROOT_KEY` |
| `pydantic.utils.smart_deepcopy` | `pydantic.v1.utils.smart_deepcopy` |
| `pydantic.utils.sequence_like` | `pydantic.v1.utils.sequence_like` |

## Removed outright in v2 (no replacement — v2 answer is "gone")

Type aliases: `NoneBytes` (= `None | bytes`), `NoneStr` (= `None | str`), `NoneStrBytes`, `StrBytes` (= `str | bytes`), `Required`, `Protocol`, `JsonWrapper`, `pydantic.compiled`.

Functions/classes: `create_model_from_namedtuple`, `create_model_from_typeddict`, `dataclasses.create_pydantic_model_from_dataclass`, `dataclasses.make_dataclass_validator`, `dataclasses.set_validation`, `datetime_parse.parse_date/parse_time/parse_datetime/parse_duration`, `error_wrappers.ErrorWrapper`, `main.validate_model` / `pydantic.validate_model`, `networks.stricturl` / `pydantic.stricturl`, `parse_file_as`, `parse_raw_as`, `types.PyObject` (→ `ImportString`, see Moved), `config.get_config/inherit_config/prepare_config`, `typing.evaluate_forwardref` and ~35 other `pydantic.typing.*` helpers, `utils.ClassAttribute/almost_equal_floats/in_ipython/...` and other `pydantic.utils.*` helpers.

The entire `pydantic.errors.*` exception zoo (~90 classes: `IntegerError`, `MissingError`, `StrRegexError`, `UrlSchemeError`, etc.) is removed — v2 uses `pydantic_core.ValidationError` with error types like `int_from_float`, `string_type`.

## Behavior changes worth eval questions (not renames)

- **`Optional[str]` with no default is now REQUIRED** in v2 (v1 gave it an implicit `None` default). Same for bare `Any` — no implicit `None` default anymore.
- **Float → int coercion**: v1 accepted any float for `int` fields; v2 only accepts floats with zero fractional part (`10.0` ok, `10.2` → `ValidationError`).
- **Smart unions by default**: `Union[int, str]` with input `'1'` stays `'1'` in v2 (v1 coerced to `1`). Revert with `Field(union_mode='left_to_right')`.
- **Str coercion**: coercing `int`/`float`/`Decimal` to `str` is now disabled by default (`coerce_numbers_to_str` opts back in).
- **Dicts**: iterables of pairs no longer validate as `dict`.
- **Input types not preserved**: `Mapping[str, int]` fed a `Counter` returns a plain `dict` in v2 (preserved for `BaseModel` subclasses and dataclasses only).
- **Regex engine**: Python `re` → Rust regex crate (no lookarounds/backreferences; `regex_engine` config to revert).
- **Url types no longer inherit from `str`** — call `str(url)`; also, trailing slash appended when no path (`AnyUrl('https://google.com')` → `'https://google.com/'`).
- **Non-string JSON keys**: serialized via `str(key)` — v1's `.json()` gave `"null"` for a `None` key; v2's `model_dump_json()` gives `"None"`.
- **`model_dump_json()` output is compact** (no spaces after separators), unlike v1's `.json()` / plain `json.dumps()`.
- **Subclass serialization**: nested-field dumps include only fields declared on the annotated type (v1 dumped all subclass fields).
- **Model equality**: models never equal dicts anymore; private attributes and extras count toward `__eq__`.
- **`Decimal`** now serializes / appears in JSON schema as a string.
- **JSON schema** targets draft 2020-12; `Optional` fields advertise `null`; custom generation via `GenerateJsonSchema` subclass + `schema_generator=` kwarg.
- **Constructor args may be copied** during validation (matters for mutable inputs).
- Dataclass fields no longer accept tuples as input (use dicts); pydantic dataclasses no longer support `extra='allow'`.
- Dropped `email-validator<2.0.0` support.

## Escape hatches (for completeness)

- `pip install bump-pydantic` — automated migration tool.
- `from pydantic.v1 import BaseModel` — v1 API inside the v2 package (also available in `pydantic>=1.10.17`).
- mypy: enable `pydantic.mypy` (and `pydantic.v1.mypy` if using v1 features).