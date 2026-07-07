import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parents[1] # ....\version-aware-document-assistant

INCLUDE = [
    ("pydantic-v1", "v1", "docs/examples/*.py"),
    ("pydantic-v1", "v1", "docs/usage/*.md"),
    ("pydantic-v1", "v1", "docs/changelog.md"),
    ("pydantic-v1", "v1", "docs/datamodel_code_generator.md"),
    ("pydantic-v1", "v1", "docs/hypothesis_plugin.md"),
    ("pydantic-v1", "v1", "docs/index.md"),
    ("pydantic-v1", "v1", "docs/install.md"),
    ("pydantic-v1", "v1", "docs/mypy_plugin.md"),
    ("pydantic-v1", "v1", "docs/pycharm_plugin.md"),
    ("pydantic-v1", "v1", "docs/visual_studio_code.md"),
    ("pydantic-v1", "v1", "pydantic/*.py"),
    ("pydantic-v1", "v1", "HISTORY.md"), ####

    ("pydantic-v2", "v2", "docs/concepts/*.md"),
    ("pydantic-v2", "v2", "docs/errors/*.md"),
    ("pydantic-v2", "v2", "docs/examples/*.md"),
    ("pydantic-v2", "v2", "docs/integrations/*.md"),
    ("pydantic-v2", "v2", "docs/internals/*.md"),
    ("pydantic-v2", "v2", "docs/index.md"),
    ("pydantic-v2", "v2", "docs/install.md"),
    ("pydantic-v2", "v2", "docs/migration.md"),
    ("pydantic-v2", "v2", "docs/version-policy.md"),
    ("pydantic-v2", "v2", "docs/why.md"),
    ("pydantic-v2", "v2", "pydantic/deprecated/*.py"),
    ("pydantic-v2", "v2", "pydantic/experimental/*.py"),
    ("pydantic-v2", "v2", "pydantic/*.py"),
    ("pydantic-v2", "v2", "HISTORY.md"),
]
def load_paths():
    path_vers_list = []
    for root, vers, pattern in INCLUDE:
        matches = sorted((PROJECT_ROOT/root).glob(pattern))
        if not matches:
            raise FileNotFoundError(f"{root}/{pattern} is not in-line with corpse map. please check again.")
        kept = 0
        for f in matches:
            if f.name == "__init__.py":
                continue    
            v = "both" if f.name == "migration.md" else vers
            path_vers_list.append((v, f))
            kept += 1
        print(f"{root}/{pattern:40} -> {kept}")
    return path_vers_list
    
lst = load_paths()
print(f"Total files = {len(lst)}")