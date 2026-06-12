import sys
from importlib.util import find_spec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if find_spec("langchain_core") is None:
    print("[skip] agent tests require langchain_core")
    raise SystemExit(0)

from langchain_core.runnables import RunnableLambda

from src.agents import ToolRoutingAgent, get_tool_routing_agent





def main() -> None:
    agent = get_tool_routing_agent()
    test_inputs = "这个文件是干什么的？"
    decision = agent.route(test_inputs)

    print("Tool routing decision:")
    print(decision)


if __name__ == "__main__":
    main()
