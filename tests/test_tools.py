import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import ALI_TONGYI_API_KEY_OS_VAR_NAME
from src.tools import (
    REPOSITORY_TOOLS,
    index_repository,
    list_files,
    read_file,
    retrieve_context,
    search_code,
)


def print_tool_output(title: str, output: object) -> None:
    print(f"\n===== {title} output =====")
    print(output)
    print(f"===== end {title} output =====\n")


def assert_contains(text: str, expected: str) -> None:
    if expected not in text:
        raise AssertionError(f"Expected to find {expected!r} in:\n{text}")


def assert_not_contains(text: str, unexpected: str) -> None:
    if unexpected in text:
        raise AssertionError(f"Expected not to find {unexpected!r} in:\n{text}")


def test_tool_exports() -> None:
    names = [tool.name for tool in REPOSITORY_TOOLS]
    print_tool_output("REPOSITORY_TOOLS", names)

    expected = ["list_files", "read_file", "search_code", "index_repository", "retrieve_context"]
    if names != expected:
        raise AssertionError(f"Unexpected tool exports: {names}")
    print("[ok] REPOSITORY_TOOLS exports 5 tools")


def test_list_files(repo_root: Path) -> None:
    output = list_files.invoke({"root_path": str(repo_root), "max_depth": 5})
    print_tool_output("list_files", output)

    assert_contains(output, "src/")
    assert_contains(output, "README.md")
    assert_not_contains(output, "__pycache__")
    print("[ok] list_files")


def test_read_file(repo_root: Path) -> None:
    output = read_file.invoke(
        {
            "file_path": str(repo_root / "src" / "tools" / "list_files.py"),
            "start_line": 1,
            "end_line": 20,
        }
    )
    print_tool_output("read_file", output)

    assert_contains(output, "Tool for listing repository files")
    assert_contains(output, "def list_files")
    print("[ok] read_file")


def test_search_code(repo_root: Path) -> None:
    output = search_code.invoke({"query": "def list_files", "root_path": str(repo_root), "max_results": 5})
    print_tool_output("search_code", output)

    assert_contains(output, "list_files.py")
    assert_contains(output, "def list_files")
    print("[ok] search_code")


def test_index_repository_empty_branch() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        empty_repo = Path(temp_dir) / "empty_repo"
        empty_repo.mkdir()
        output = index_repository.invoke({"root_path": str(empty_repo)})

    print_tool_output("index_repository empty branch", output)
    assert_contains(output, "No indexable files found")
    print("[ok] index_repository empty repository branch")


def test_retrieve_context_missing_index() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        missing_index = Path(temp_dir) / "missing_chroma"
        output = retrieve_context.invoke({"query": "greet", "storage_mode": "local", "persist_directory": str(missing_index)})

    print_tool_output("retrieve_context missing index", output)
    assert_contains(output, "Run index_repository first")
    print("[ok] retrieve_context missing index branch")


def test_chroma_local_integration_if_key_exists(repo_root: Path) -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] Chroma integration requires {ALI_TONGYI_API_KEY_OS_VAR_NAME}")
        return

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        persist_dir = Path(temp_dir) / "chroma"
        collection_name = "tool_test_codebase"

        index_output = index_repository.invoke(
            {
                "root_path": str(repo_root),
                "storage_mode": "local",
                "persist_directory": str(persist_dir),
                "collection_name": collection_name,
                "chunk_size": 500,
                "chunk_overlap": 50,
            }
        )
        print_tool_output("index_repository", index_output)

        assert_contains(index_output, "Indexed repository")
        assert_contains(index_output, "Documents:")

        retrieve_output = retrieve_context.invoke(
            {
                "query": "Where is the list_files tool defined?",
                "storage_mode": "local",
                "persist_directory": str(persist_dir),
                "collection_name": collection_name,
                "k": 2,
            }
        )
        print_tool_output("retrieve_context", retrieve_output)

        assert_contains(retrieve_output, "list_files.py")
        assert_contains(retrieve_output, "list_files")

    print("[ok] index_repository + retrieve_context Chroma local integration")


def test_chroma_memory_integration_if_key_exists(repo_root: Path) -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] Chroma memory integration requires {ALI_TONGYI_API_KEY_OS_VAR_NAME}")
        return

    collection_name = "tool_test_codebase_memory"

    index_output = index_repository.invoke(
        {
            "root_path": str(repo_root),
            "storage_mode": "memory",
            "collection_name": collection_name,
            "chunk_size": 500,
            "chunk_overlap": 50,
        }
    )
    print_tool_output("index_repository memory", index_output)

    assert_contains(index_output, "Storage mode: memory")
    assert_contains(index_output, "Persist directory: memory only")
    assert_contains(index_output, "Documents:")

    retrieve_output = retrieve_context.invoke(
        {
            "query": "Where is the list_files tool defined?",
            "storage_mode": "memory",
            "collection_name": collection_name,
            "k": 2,
        }
    )
    print_tool_output("retrieve_context memory", retrieve_output)

    assert_contains(retrieve_output, "list_files.py")
    assert_contains(retrieve_output, "list_files")

    print("[ok] index_repository + retrieve_context Chroma memory integration")

def main() -> None:
    repo_root = PROJECT_ROOT
    print_tool_output("repo_root", repo_root)

    test_tool_exports()
    test_list_files(repo_root)
    test_read_file(repo_root)
    test_search_code(repo_root)
    test_index_repository_empty_branch()
    test_retrieve_context_missing_index()
    test_chroma_local_integration_if_key_exists(repo_root)
    test_chroma_memory_integration_if_key_exists(repo_root)

    print("All tool tests completed.")


if __name__ == "__main__":
    main()



