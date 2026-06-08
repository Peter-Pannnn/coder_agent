import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import ALI_TONGYI_API_KEY_OS_VAR_NAME, get_ali_model_client
from src.prompt import get_chat_prompt


def main():
    if not os.getenv(ALI_TONGYI_API_KEY_OS_VAR_NAME):
        raise RuntimeError(
            f"请先设置环境变量 {ALI_TONGYI_API_KEY_OS_VAR_NAME}，再运行测试脚本。"
        )

    model = get_ali_model_client(temperature=0.2, verbose=True)
    prompt = get_chat_prompt()
    chain = prompt | model

    response = chain.invoke(
        {
            "input": "请用一句话介绍你自己，并说明你能如何帮助开发者理解代码仓库。"
        }
    )

    print("模型返回：")
    print(response.content)


if __name__ == "__main__":
    main()
