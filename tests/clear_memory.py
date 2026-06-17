"""Clear all persisted CoderAgent short-term memory."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMORY_DB_PATH = PROJECT_ROOT / "src" / "storage" / "short_term_memory.sqlite3"
DEFAULT_LONG_TERM_MEMORY_DIRECTORY = PROJECT_ROOT / "src" / "storage" / "long_term_memory"
MEMORY_TABLE = "short_term_memory_messages"
LONG_TERM_MEMORY_COLLECTION = "personal_memory"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear CoderAgent short-term and long-term memory records.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_MEMORY_DB_PATH,
        help=f"SQLite memory database path. Default: {DEFAULT_MEMORY_DB_PATH}",
    )
    parser.add_argument(
        "--long-term-path",
        type=Path,
        default=DEFAULT_LONG_TERM_MEMORY_DIRECTORY,
        help=f"Chroma long-term memory directory. Default: {DEFAULT_LONG_TERM_MEMORY_DIRECTORY}",
    )
    return parser.parse_args()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def clear_all_memory(db_path: Path) -> int:
    if not db_path.exists():
        print(f"[skip] memory database does not exist: {db_path}")
        return 0

    connection = sqlite3.connect(db_path)
    try:
        if not table_exists(connection, MEMORY_TABLE):
            print(f"[skip] memory table does not exist: {MEMORY_TABLE}")
            return 0

        row = connection.execute(f"SELECT COUNT(*) FROM {MEMORY_TABLE}").fetchone()
        deleted_count = int(row[0]) if row else 0
        connection.execute(f"DELETE FROM {MEMORY_TABLE}")
        connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", (MEMORY_TABLE,))
        connection.commit()
    finally:
        connection.close()

    print(f"Cleared {deleted_count} memory record(s) from {db_path}")
    return deleted_count


def clear_long_term_memory(persist_directory: Path) -> int:
    if not persist_directory.exists():
        print(f"[skip] long-term memory directory does not exist: {persist_directory}")
        return 0

    try:
        import chromadb
    except ModuleNotFoundError:
        print("[skip] clearing long-term memory requires chromadb")
        return 0

    client = chromadb.PersistentClient(path=str(persist_directory))
    try:
        collection = client.get_collection(LONG_TERM_MEMORY_COLLECTION)
    except Exception:
        print(f"[skip] long-term memory collection does not exist: {LONG_TERM_MEMORY_COLLECTION}")
        return 0

    deleted_count = int(collection.count())
    client.delete_collection(LONG_TERM_MEMORY_COLLECTION)
    print(f"Cleared {deleted_count} long-term memory record(s) from {persist_directory}")
    return deleted_count


def main() -> None:
    args = parse_args()
    clear_all_memory(args.db_path.resolve())
    clear_long_term_memory(args.long_term_path.resolve())


if __name__ == "__main__":
    main()
