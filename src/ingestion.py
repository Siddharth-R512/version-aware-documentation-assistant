import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parents[1] #C:\Users\siddh\Documents\Sid-Projects\version-aware-document-assistant

def load_path(root_dir: list[str]):
    """
    # v1, /docs -> /examples, /usage, changelog.md, datamodel_code_generator.md, hypothesis_plugin.md, index.md, install.md, mypy_plugin.md, visual_studio_code.md
    # v1, /pydantic (only .py files)
    # v1, HISTORY.md

    # v2, /docs -> /concepts, /errors, /examples, /integrations, /internals, index.md, install.md, migration.md, version-policy.md, why.md
    # v2, /pydantic -> (all .py files in ./pydantic), /deprecated, /experimental
    # v2, HISTORY.md
    """
    path_vers_list = [] # [("pydantic-v1", "v1", "path itself")]
    root1 = root_dir[0]
    version_root = PROJECT_ROOT/root1
    v1_example_dir = version_root/"docs"/"examples"
    count = 0 
    for file in v1_example_dir.glob("*.py"):
        path_vers_list.append(
            (
                root1,
                "v1",
                file.relative_to(PROJECT_ROOT)
            )
        )

        count+=1
    example_count = count
    print(f"Number of {root1}/examples/*.py = {example_count}") 
    # =======================================================
    v1_usage_dir = version_root/"docs"/"usage"
    for file in v1_usage_dir.glob("*.md"):
        path_vers_list.append(
            (
                root1,
                "v1",
                file.relative_to(PROJECT_ROOT)
            )
        )
        count+=1

    usage_count = count - example_count
    print(f"Number of {root1}/usage/*.md = {usage_count}")
    # =======================================================
    v1_rest_files = ["changelog.md","datamodel_code_generator.md","hypothesis_plugin.md","index.md","install.md","mypy_plugin.md","pycharm_plugin.md","visual_studio_code.md"]
    for f in v1_rest_files:
        file = version_root/"docs"/f
        assert file.exists(), f"missing: {file}"
        path_vers_list.append(
            (
                root1,
                "v1",
                file.relative_to(PROJECT_ROOT)
            )
        )
        count +=1
    rest_count = count - usage_count - example_count
    print(f"Number of remaining files to be included under {root1} = {rest_count}")
    # =======================================================
    v1_pydantic = version_root/"pydantic"
    v1_py_count = 0
    for file in v1_pydantic.glob("*.py"):
        path_vers_list.append(
            (
                root1,
                "v1",
                file.relative_to(PROJECT_ROOT)
            )
        )
        v1_py_count += 1
    print(f"Number of {root1}/pydantic/*.py = {v1_py_count}")
    # =======================================================
    file = version_root / "HISTORY.md"
    assert file.exists(), f"missing: {file}"
    path_vers_list.append(
        (
            root1,
            "v1",
            file.relative_to(PROJECT_ROOT)
        )
    )
    print(f"Number of {str(file.relative_to(PROJECT_ROOT))} = 1")
    # =======================================================
    # =======================================================
    print("")
    root2 = root_dir[1]
    version_root2 = PROJECT_ROOT/root2
    v2_docs_dirs = ["concepts","errors","examples","integrations","internals"]
    for dir_name in v2_docs_dirs:
        docs_dir = version_root2/"docs"/dir_name
        dir_count = 0

        for file in docs_dir.glob("*.md"):
            path_vers_list.append(
                (
                    root2,
                    "v2",
                    file.relative_to(PROJECT_ROOT)
                )
            )
            dir_count += 1
        print(f"Number of {root2}/{dir_name}/*.md = {dir_count}")

    v2_docs_rest = ["index.md","install.md","migration.md","version-policy.md","why.md"]
    v2_rest_count = 0
    for rest_name in v2_docs_rest:
        docs_dir = version_root2/"docs"/rest_name
        assert docs_dir.exists(), f"missing: {docs_dir}"
        version_label = "both" if rest_name == "migration.md" else "v2"
        path_vers_list.append(
            (
                root2,
                version_label,
                docs_dir.relative_to(PROJECT_ROOT)
            )
        )
        v2_rest_count += 1
    print(f"Number of remaining files to be included under 'v2/docs' = {v2_rest_count}")
        

    v2_pydantic_dirs = ["deprecated","experimental"]
    v2_pydantic = version_root2/"pydantic"
    for dir_name in v2_pydantic_dirs:
        docs_dir = version_root2/"pydantic"/dir_name
        dir_count = 0

        for file in docs_dir.glob("*.py"):
            if file.name == '__init__.py':
                continue # __init__.py
            path_vers_list.append(
                (
                    root2,
                    "v2",
                    file.relative_to(PROJECT_ROOT)
                )
            )
            dir_count += 1
        print(f"Number of {root2}/{dir_name}/*.py = {dir_count}")
    # =======================================================
    pydantic_count = 0
    for pyfiles in v2_pydantic.glob("*.py"):
        if pyfiles.name == "__init__.py":
            continue # __init__.py
        path_vers_list.append(
            (
                root2,
                "v2",
                pyfiles.relative_to(PROJECT_ROOT)
            )
        )
        pydantic_count+=1
    print(f"Number of {root2}/pydantic/*.py = {pydantic_count}")
    # =======================================================
    v2_hist_count =0
    file = version_root2 / "HISTORY.md"
    path_vers_list.append(
        (
            root2,
            "v2",
            file.relative_to(PROJECT_ROOT)
        )
    )
    v2_hist_count +=1
    print(f"Number of {str(file.relative_to(PROJECT_ROOT))} = {v2_hist_count}")
    # =======================================================
    return path_vers_list

lst = load_path(["pydantic-v1", "pydantic-v2"])

# print(lst)