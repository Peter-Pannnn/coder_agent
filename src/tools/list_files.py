"""Tool for listing repository files."""

from pathlib import Path

from langchain_core.tools import tool

from .utils import resolve_path, should_ignore


@tool("list_files")
def list_files(root_path: str = ".", max_depth: int = 3, include_hidden: bool = False) -> str:
    """List repository files and folders up to a maximum depth."""
    root = resolve_path(root_path)
    if not root.exists():
        return f"Path not found: {root}"
    if not root.is_dir():
        return f"Path is not a directory: {root}"

    output = [f"Root: {root}", "./"]

    def visit(directory: Path, depth: int) -> None:
        if depth >= max_depth:
            return

        try:
            children = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except OSError:
            return

        for child in children:
            if should_ignore(child, include_hidden=include_hidden):
                continue
            indent = "  " * (depth + 1)
            if child.is_dir():
                output.append(f"{indent}{child.name}/")
                visit(child, depth + 1)
            else:
                output.append(f"{indent}{child.name}")

    visit(root, 0)
    return "\n".join(output)

