import sys
import tempfile
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if find_spec("langchain_core") is None:
    print("[skip] memory tests require langchain_core")
    raise SystemExit(0)

MEMORY_MODULE_PATH = PROJECT_ROOT / "src" / "memory" / "short_term_memory.py"
spec = spec_from_file_location("coder_agent_short_term_memory", MEMORY_MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load memory module from {MEMORY_MODULE_PATH}")

memory_module = module_from_spec(spec)
sys.modules[spec.name] = memory_module
spec.loader.exec_module(memory_module)
SQLiteShortTermMemory = memory_module.SQLiteShortTermMemory


def test_sqlite_short_term_memory_persists_recent_messages() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "short_term_memory.sqlite3"
        memory = SQLiteShortTermMemory(db_path)

        memory.add_message("session-a", "user", "first")
        memory.add_message("session-a", "assistant", "second")
        memory.add_message("session-a", "user", "third")
        memory.add_message("session-b", "user", "other session")

        recent = memory.load_recent("session-a", limit=2)
        if [message.content for message in recent] != ["second", "third"]:
            raise AssertionError("Expected recent messages in chronological order.")

        all_messages = memory.load_recent("session-a", limit=None)
        if [message.content for message in all_messages] != ["first", "second", "third"]:
            raise AssertionError("Expected limit=None to load all session messages.")

        rendered = memory.render_recent("session-a", limit=2)
        if rendered != "assistant: second\nuser: third":
            raise AssertionError(f"Unexpected rendered memory: {rendered!r}")

        if memory.render_recent("session-b", limit=4) != "user: other session":
            raise AssertionError("Expected memory to be isolated by session_id.")

        chat_messages = memory.load_recent_chat_messages("session-a", limit=2)
        if [message.type for message in chat_messages] != ["ai", "human"]:
            raise AssertionError("Expected memory to convert to LangChain chat messages.")


def main() -> None:
    test_sqlite_short_term_memory_persists_recent_messages()
    print("All memory tests completed.")


if __name__ == "__main__":
    main()
