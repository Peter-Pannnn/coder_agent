"""Tool for reading text files."""

from langchain_core.tools import tool

from .utils import read_text_file, resolve_path


@tool("read_file")
def read_file(file_path: str, start_line: int = 1, end_line: int = 0) -> str:
    """Read a text file, optionally with a 1-based inclusive line range."""
    path = resolve_path(file_path)
    if not path.exists():
        return f"File not found: {path}"
    if not path.is_file():
        return f"Path is not a file: {path}"

    text = read_text_file(path)
    lines = text.splitlines()
    if not lines:
        return f"{path} is empty."

    start = max(1, start_line)
    end = len(lines) if end_line <= 0 else min(end_line, len(lines))
    if start > end:
        return f"Invalid line range: start_line={start_line}, end_line={end_line}"

    selected = lines[start - 1 : end]
    numbered = [f"{line_no}: {line}" for line_no, line in enumerate(selected, start=start)]
    return f"File: {path}\nLines: {start}-{end}\n" + "\n".join(numbered)

