# prompt

`prompt` 目录负责管理 Agent 使用的提示词模板。提示词通过 LangChain Prompt 组件封装，供 Agent、测试脚本和链式调用复用。

## 对外接口

提示词接口统一从 `src.prompt` 导出：

```python
from src.prompt import SYSTEM_PROMPT, get_system_message_prompt, get_chat_prompt
```

## 文件说明

### system_prompt.py

功能：定义 Codebase Agent Assistant 的系统提示词，并提供 LangChain 包装接口。

包含内容：

- Agent 角色定位。
- 工作原则。
- 工具使用规范。
- 安全边界。
- 回答格式。
- 禁止行为。

## 接口说明

### SYSTEM_PROMPT

类型：字符串。

用途：

- 保存完整系统提示词文本。
- 方便调试、打印、检查或传给其他 Prompt 构造函数。

### get_system_message_prompt

功能：返回 LangChain 的 `SystemMessagePromptTemplate`。

用途：

- 将系统提示词作为系统消息注册到聊天提示词中。
- 适合和其他 Human、AI、MessagesPlaceholder 等模板组合。

### get_chat_prompt

功能：返回一个基础的 `ChatPromptTemplate`。

当前模板结构：

```text
system: SYSTEM_PROMPT
human: {input}
```

用途：

- 快速构建最小可用的模型调用链。
- 可直接和模型通过 LCEL 组合：`prompt | model`。
- 适合测试模型是否能按照系统提示词回答。

示例：

```python
from src.models import get_ali_model_client
from src.prompt import get_chat_prompt

model = get_ali_model_client(temperature=0.2)
prompt = get_chat_prompt()
chain = prompt | model

response = chain.invoke({"input": "请解释这个项目的目标。"})
print(response.content)
```

## 使用建议

- 系统提示词负责稳定约束 Agent 行为。
- 任务提示词、规划提示词、审查提示词可以后续拆成独立文件。
- 不建议把长提示词直接散落在 Agent 或工具代码中。
- 修改提示词后，建议用测试脚本做一次最小模型调用验证。
