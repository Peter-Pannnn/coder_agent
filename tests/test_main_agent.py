import os
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_PACKAGES = [
    "langchain_core",
    "langchain_openai",
]

for package_name in REQUIRED_PACKAGES:
    if find_spec(package_name) is None:
        print(f"[skip] main agent script requires {package_name}")
        raise SystemExit(0)

from src.agents import CoderAgentResult, get_coder_agent
from src.models import ALI_TONGYI_API_KEY_OS_VAR_NAME
from src.prompt import get_chat_prompt


# USER_INPUT = "./src文件夹中哪个文件是有关路由工具的选择的,要求使用RAG"
SESSION_ID = "test_main_agent3"


def print_section(title: str, content: object) -> None:
    print(f"\n===== {title} =====")
    print(content)


def format_answer_prompt(answer_input: dict[str, Any]) -> str:
    messages = get_chat_prompt().format_messages(**answer_input)
    blocks = []
    for message in messages:
        role = getattr(message, "type", message.__class__.__name__)
        content = getattr(message, "content", str(message))
        blocks.append(f"[{role}]\n{content}")

    return "\n\n".join(blocks)


def run_and_print(agent, user_input: str) -> None:
    agent._validate_user_input(user_input)

    answer_history = agent._load_memory_messages(agent.answer_memory_messages)
    long_term_memory_write = agent._maybe_store_long_term_memory(user_input)
    long_term_memory_context = agent._render_long_term_memory_context(user_input)
    routing_decisions, context, tool_results = agent._route_until_ready(user_input)
    answer_context = agent._build_answer_context(
        tool_context=context,
        long_term_memory_context=long_term_memory_context,
        long_term_memory_write=long_term_memory_write,
    )
    answer_input = agent._build_answer_input(user_input, answer_context, answer_history)

    print_section("user input", user_input)
    print_section("answer prompt", format_answer_prompt(answer_input))

    answer = agent.answer_chain.invoke(answer_input)
    agent._remember_exchange(user_input, answer)

    result = CoderAgentResult(
        input=user_input,
        answer=answer,
        routing_decision=routing_decisions[-1],
        routing_decisions=routing_decisions,
        tool_results=tool_results,
    )
    print_section("answer", result.answer)


def main() -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] please set {ALI_TONGYI_API_KEY_OS_VAR_NAME} before running this script")
        return

    agent = get_coder_agent(
        temperature=0.2,
        max_tool_rounds=5,
        session_id=SESSION_ID,
        user_id="test_user",
        routing_memory_messages=4,
    )
    run_and_print(agent, "./src是一个Agent实现的核心文件夹，这个agent是否实现了记忆功能")





if __name__ == "__main__":
    main()
