import sys
from importlib.util import find_spec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if find_spec("langchain_core") is None:
    print("[skip] prompt tests require langchain_core")
    raise SystemExit(0)

from src.prompt import (
    TOOL_ROUTING_PROMPT,
    get_tool_routing_chat_prompt,
    get_tool_routing_message_prompt,
)
from src.models import get_ali_model_client


def main() -> None:
    message_prompt = get_tool_routing_chat_prompt()
    client = get_ali_model_client(temperature=0)
    chain= message_prompt | client
    response = chain.invoke(
        {
            "input": "你是什么模型"
        }
    )
    print(response.content)


if __name__ == "__main__":
    main()
