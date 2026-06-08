"""Tool for keyword code search."""

import subprocess

from langchain_core.tools import tool

from .utils import iter_files, read_text_file, resolve_path


@tool("search_code")
def search_code(query: str, root_path: str = ".", max_results: int = 50) -> str:
    """Search code with ripgrep and return matching file paths and lines."""
    root = resolve_path(root_path)
    if not root.exists():
        return f"Path not found: {root}"

    command = [
        "rg",
        "--line-number",
        "--column",
        "--hidden",
        "--glob",
        "!.git/**",
        "--glob",
        "!__pycache__/**",
        "--glob",
        "!.chroma/**",
        query,
        str(root),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        matches: list[str] = []
        for file_path in iter_files(root):
            if len(matches) >= max_results:
                break
            try:
                for line_number, line in enumerate(read_text_file(file_path).splitlines(), start=1):
                    if query.lower() in line.lower():
                        matches.append(f"{file_path}:{line_number}: {line.strip()}")
                        if len(matches) >= max_results:
                            break
            except OSError:
                continue
        return "\n".join(matches) if matches else f"No matches found for: {query}"

    if result.returncode not in (0, 1):
        return result.stderr.strip() or f"Search failed with exit code {result.returncode}"

    lines = result.stdout.splitlines()[:max_results]
    return "\n".join(lines) if lines else f"No matches found for: {query}"

