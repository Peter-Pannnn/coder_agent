"""Shared helpers for repository tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import chromadb

DEFAULT_CHROMA_PERSIST_DIRECTORY = "src/storage/chroma"
DEFAULT_CHROMA_STORAGE_MODE = "local"

_MEMORY_CHROMA_CLIENT = chromadb.Client()

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".chroma",
    "chroma",
}

DEFAULT_INDEX_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
    ".ps1",
}


def resolve_path(path: str) -> Path:
    """Resolve a user-provided path to an absolute Path."""
    return Path(path).expanduser().resolve()


def normalize_chroma_storage_mode(storage_mode: str) -> str:
    """Normalize and validate a Chroma storage mode."""
    normalized = storage_mode.strip().lower()
    if normalized not in {"local", "memory"}:
        raise ValueError("storage_mode must be 'local' or 'memory'")
    return normalized


def get_chroma_client(storage_mode: str, persist_directory: str = DEFAULT_CHROMA_PERSIST_DIRECTORY):
    """Create or reuse a Chroma client for local or in-memory storage."""
    normalized = normalize_chroma_storage_mode(storage_mode)
    if normalized == "memory":
        return _MEMORY_CHROMA_CLIENT

    persist_path = resolve_path(persist_directory)
    persist_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_path))


def should_ignore(path: Path, include_hidden: bool = False) -> bool:
    """Return whether a path should be ignored by repository tools."""
    parts = set(path.parts)
    if parts.intersection(DEFAULT_IGNORE_DIRS):
        return True
    if not include_hidden and any(part.startswith(".") for part in path.parts):
        return True
    return False


def iter_files(root: Path, include_hidden: bool = False) -> Iterable[Path]:
    """Yield non-ignored files under a root directory."""
    for current_root, dir_names, file_names in os.walk(root):
        current_path = Path(current_root)
        dir_names[:] = [
            name
            for name in dir_names
            if not should_ignore(current_path / name, include_hidden=include_hidden)
        ]
        for file_name in file_names:
            file_path = current_path / file_name
            if not should_ignore(file_path, include_hidden=include_hidden):
                yield file_path


def read_text_file(path: Path) -> str:
    """Read a text file with tolerant UTF-8 decoding."""
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int, str]]:
    """Split text into line-aware chunks."""
    lines = text.splitlines()
    chunks: list[tuple[int, int, str]] = []
    current_lines: list[str] = []
    current_start = 1
    current_size = 0

    for line_number, line in enumerate(lines, start=1):
        line_size = len(line) + 1
        if current_lines and current_size + line_size > chunk_size:
            chunks.append((current_start, line_number - 1, "\n".join(current_lines)))

            overlap_lines: list[str] = []
            overlap_size = 0
            for previous_line in reversed(current_lines):
                previous_size = len(previous_line) + 1
                if overlap_size + previous_size > chunk_overlap:
                    break
                overlap_lines.insert(0, previous_line)
                overlap_size += previous_size

            current_lines = overlap_lines
            current_start = max(1, line_number - len(current_lines))
            current_size = overlap_size

        current_lines.append(line)
        current_size += line_size

    if current_lines:
        chunks.append((current_start, len(lines), "\n".join(current_lines)))

    return chunks
