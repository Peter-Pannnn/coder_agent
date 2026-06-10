import sys
from importlib.util import find_spec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if find_spec("langchain_core") is None:
    print("[skip] main agent tests require langchain_core")
    raise SystemExit(0)


from src.agents import get_coder_agent


USER_INPUT = "temperature 是控制什么的？并说明是如何控制的。"






if __name__ == "__main__":
    agent= get_coder_agent(temperature=0.4)
    for chunk in agent.stream(USER_INPUT):
        print(chunk, end="", flush=True)
    print()
