import os
import sys
from importlib.util import find_spec
from pathlib import Path

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

from src.agents import get_coder_agent
from src.models import ALI_TONGYI_API_KEY_OS_VAR_NAME


# USER_INPUT = "./src文件夹中哪个文件是有关路由工具的选择的,要求使用RAG"
SESSION_ID = "test_main_agent"


def print_section(title: str, content: object) -> None:
    print(f"\n===== {title} =====")
    print(content)


def print_history(agent, title: str = "history") -> None:
    history = agent.memory.render_recent(agent.session_id, limit=None) if agent.memory else ""
    print_section(title, history or "<empty>")


def run_and_print(agent, user_input: str) -> None:
    result = agent.run(user_input)
    print_section("user input", result.input)
    print_section("answer", result.answer)
    print_history(agent, "history after answer")


def main() -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] please set {ALI_TONGYI_API_KEY_OS_VAR_NAME} before running this script")
        return

    agent = get_coder_agent(
        temperature=0.2,
        max_tool_rounds=3,
        session_id=SESSION_ID,
        routing_memory_messages=4,
    )
    print_history(agent, "history before run")

    run_and_print(agent, "接下来我要问你几个问题，你只需要回答是或否")
    run_and_print(agent, "你是否能帮助我写代码？")
    run_and_print(agent, "你是否可以联网得到最新信息？")


if __name__ == "__main__":
    main()
