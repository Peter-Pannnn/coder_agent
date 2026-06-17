import os
import sys
import tempfile
from importlib.util import find_spec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_PACKAGES = [
    "chromadb",
    "langchain_chroma",
    "langchain_core",
]

for package_name in REQUIRED_PACKAGES:
    if find_spec(package_name) is None:
        print(f"[skip] long-term memory tests require {package_name}")
        raise SystemExit(0)

from src.memory import ChromaLongTermMemory
from src.models import ALI_TONGYI_API_KEY_OS_VAR_NAME


def main() -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] long-term memory integration requires {ALI_TONGYI_API_KEY_OS_VAR_NAME}")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        memory = ChromaLongTermMemory(
            persist_directory=str(Path(temp_dir) / "long_term_memory"),
            collection_name="test_personal_memory",
        )
        memory_id = memory.add_memory(
            "用户偏好：回答代码问题时先给结论，再给简短原因。",
            user_id="test_user",
        )
        records = memory.retrieve_memories(
            "回答代码问题时应该用什么风格？",
            user_id="test_user",
            k=1,
        )

        if not records:
            raise AssertionError("Expected at least one retrieved long-term memory.")

        print("memory_id:", memory_id)
        print("retrieved:", records[0])


if __name__ == "__main__":
    main()
