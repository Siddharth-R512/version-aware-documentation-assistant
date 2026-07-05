Migration from v1. 

Find things in v1 that are linked to v2. This is the place where things can go wrong because they are 2 different things maybe semantically but are linked based on pydantic contributions.

PLAN:
- CREATE corpus map: Describes what to include/exclude such as include py and markdown and exclude rust and related files. and explain why

- Chunk Schema: Build a pydantic model of what this chunk may look like.


**#1 L23...**
If u want to use v1 for any reason then in the import use pydantic.v1

**#2 L27...** A beta tool to migrate v1 to v2.
pip install bump-pydantic

> So if bump-pydantic exists, then why even created Version aware documentation assistant?
**Bump-pydantic is codemod not a knowledge system.** It mechanically rewrites the code patterns it recognizes. Eg, `.dict()` -> .`model_dump()`, converts `class Config` to `model_config`.
**But.....**
1. It cannot Answer questions ("When does my validator get a different value in v2?" or "What replaced `parse_obj_as`?")
2. It cannot Explain why something changed or what the behavioral differences are
3. It is **_Beta_** stage. Why? There are so many code changes & migration patterns from v1 to v2 that it cant safely auto-rewrite and requires human understanding.
4. It cannot help with version specific question at all! 

> This is a documentation assistant. Migration is one of 3 query types. Even for migration queries the person running bump pydantic still need to understand what the tool did and what fix it couldn't do

**Two ways this actually helps you:**
1. It's eval-set material. The bump-pydantic README/docs list the exact transformation rules it applies — that list is effectively a curated inventory of the most common v1→v2 changes. Mine it for eval questions.
2. It's a limitations-section line. In your README: "For mechanical code rewriting, bump-pydantic exists; this system addresses the understanding gap — why things changed, behavioral differences, and version-specific usage — which codemods can't." Acknowledging adjacent tools and articulating your distinct niche reads as maturity, not weakness.

#3 L54...
if u need to use v1 then use `pip install "pydantic ==1.*"`
V2 pydantic continues to provide v1 capabilities using `import pydantic.v1`
Eg,
`from pydantic.v1 import BaseModel`

#4 L70
Certain functions removed from v2. You can get it from `pydantic.v1` like `lenient_isinstance`.
`from pydantic.v1.utils import lenient_isinstance`

#5 L100 - 104
#6 L107 - 115

#7 L118...
Pydantic v2 provides `pydantic.v1` as a compatibility layer so old v1 can keep working after upgradation to v2
# Old (v1)
from pydantic import BaseModel
# Upgrade to v2 but keep v1 behavior
from pydantic.v1 import BaseModel
**Purpose: Upgrade package v1 → v2 without immediately rewriting all code.**

#8 L125 - L146

#9 L148 - L188
Some functions present in v1 is officially planned to be eliminated. Eg, `parse_raw` and `parse_file`
Use `model_validate_json` that works just like `parse_raw`.
Use `model_validate` after loading data. Use this since `from_orm` is gone.
`__eq__` method changed for v2.
Eg,
`#V1`
`class User(BaseModel):`
`   name: str`

here, User(name="Ana") == {"name":"Ana"}
Here `__eq__` works. Now v2, rules change. Refer L152-162

#10 L217
V2 has `model_dump_json` that is much better

#11 L255
In v1, `pydantic.generics.GenericModel` is no longer necessary & removed. It is like this in V2 `class MyGenericModel(BaseModel, Generic[T]): ...`

#12 L275
Arbitrary kwargs in v1 will now be passed to the `json_schema_extra` of V2.

#13 L283 - L291

#14 L297-L317
V2 brings some changes to dataclass behaviour.

#15 L321
v1 create a class called `Config` of the parent `BaseModel`. V2 now u have a class attribute called `model_config` , a dict.

#16 L344-L354

#17 L362