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


def test_tool_routing_prompt_exports() -> None:
    if "合法 JSON 对象" not in TOOL_ROUTING_PROMPT:
        raise AssertionError("Tool routing prompt should require JSON output.")

    if "needs_tools" not in TOOL_ROUTING_PROMPT:
        raise AssertionError("Tool routing prompt should define needs_tools.")


def test_tool_routing_prompt_formats_user_input() -> None:
    prompt = get_tool_routing_chat_prompt()
    messages = prompt.format_messages(input="配置加载在哪里实现？")

    if len(messages) != 2:
        raise AssertionError(f"Expected 2 prompt messages, got {len(messages)}.")

    if "工具路由器" not in messages[0].content:
        raise AssertionError("Expected routing system message.")

    if messages[1].content != "配置加载在哪里实现？":
        raise AssertionError("Expected user input to be preserved.")


def test_tool_routing_message_prompt_type() -> None:
    message_prompt = get_tool_routing_message_prompt()
    message = message_prompt.format()

    if "可用工具" not in message.content:
        raise AssertionError("Expected available tools section in message prompt.")


def main() -> None:
    test_tool_routing_prompt_exports()
    test_tool_routing_prompt_formats_user_input()
    test_tool_routing_message_prompt_type()
    print("All prompt tests completed.")


if __name__ == "__main__":
    main()
