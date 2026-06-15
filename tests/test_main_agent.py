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


USER_INPUT = "./src文件夹中哪个文件是有关路由工具的选择的,要求使用RAG"


def print_section(title: str, content: object) -> None:
    print(f"\n===== {title} =====")
    print(content)


def main() -> None:
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        print(f"[skip] please set {ALI_TONGYI_API_KEY_OS_VAR_NAME} before running this script")
        return

    agent = get_coder_agent(temperature=0.2, max_tool_rounds=3)
    result = agent.run(USER_INPUT)

    print_section("user input", result.input)
    print_section("answer", result.answer)

    print_section("routing decisions", "")
    for index, decision in enumerate(result.routing_decisions, start=1):
        print(f"[round {index}]")
        print(f"intent: {decision.intent}")
        print(f"needs_tools: {decision.needs_tools}")
        print(f"confidence: {decision.confidence}")
        print(f"reason: {decision.reason}")
        print(f"answer_without_tools: {decision.answer_without_tools}")
        print(f"clarifying_question: {decision.clarifying_question}")
        print("tools:")
        for tool in decision.tools:
            print(f"  - name: {tool.name}")
            print(f"    purpose: {tool.purpose}")
            print(f"    priority: {tool.priority}")
            print(f"    suggested_input: {tool.suggested_input}")
        print()

    print_section("tool results", "")
    if not result.tool_results:
        print("No tools were executed.")
        return

    for index, tool_result in enumerate(result.tool_results, start=1):
        print(f"[tool result {index}]")
        print(f"name: {tool_result.name}")
        print(f"input: {tool_result.input}")
        if tool_result.error:
            print(f"error: {tool_result.error}")
        else:
            print("output:")
            print(tool_result.output)
        print()


if __name__ == "__main__":
    main()
