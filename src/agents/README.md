# agents

`agents` 目录存放 Agent 编排层代码，负责用 LangChain 把 prompt、模型和工具决策串起来。

## ToolRoutingAgent

`ToolRoutingAgent` 用于在真正调用仓库工具前，先让大模型输出结构化工具路由决策。

它的职责：

- 接收用户自然语言问题。
- 使用 `get_tool_routing_chat_prompt()` 构建工具路由提示词。
- 通过 LCEL 组合 `prompt | model | JsonOutputParser | RunnableLambda`。
- 将模型 JSON 输出校验并解析为 `ToolRoutingDecision`。

示例：

```python
from src.agents import get_tool_routing_agent

agent = get_tool_routing_agent()
decision = agent.route("配置加载在哪里实现？")

print(decision.intent)
print(decision.needs_tools)
print([tool.name for tool in decision.tools])
```

也可以直接取得 LangChain Runnable：

```python
chain = agent.as_chain()
decision = chain.invoke({"input": "配置加载在哪里实现？"})
```

如果需要注入自定义模型：

```python
from src.agents import ToolRoutingAgent
from src.models import get_ali_model_client

model = get_ali_model_client(temperature=0.0)
agent = ToolRoutingAgent(model=model)
decision = agent.route("请解释 src/tools/list_files.py")
```

## 数据结构

### ToolRoutingDecision

字段：

- `intent`: 用户意图，例如 `locate_code`、`explain_code`、`plan_change`。
- `needs_tools`: 是否需要调用工具。
- `confidence`: 路由判断置信度，范围为 0 到 1。
- `reason`: 路由原因。
- `tools`: 候选工具列表。
- `answer_without_tools`: 是否允许不使用工具直接回答。
- `clarifying_question`: 需要追问用户的问题，没有则为空字符串。

### ToolCallDecision

字段：

- `name`: 工具名。
- `purpose`: 调用目的。
- `priority`: 调用优先级，数字越小越先调用。
- `suggested_input`: 从用户问题中可靠推断出的工具入参。
