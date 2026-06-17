# agents

`agents` 目录存放 Agent 编排层代码，负责用 LangChain 把 prompt、模型和工具决策串起来。

## CoderAgent

`CoderAgent` 是主 Agent，负责统一编排用户请求。

当前流程：

```text
user input
  -> ToolRoutingAgent.route()
  -> needs_tools == false
      -> answer_chain
      -> CoderAgentResult
  -> needs_tools == true
      -> 检查工具 suggested_input
      -> 缺少必要参数
          -> answer_chain 提醒用户补充参数
          -> CoderAgentResult
      -> 参数完整
          -> 按 priority 顺序执行工具
          -> 将工具结果拼接为回答上下文
          -> 再次 ToolRoutingAgent.route(用户问题 + 已获得的工具上下文)
          -> 循环直到 needs_tools == false、缺少参数、工具重复或达到 max_tool_rounds
          -> answer_chain 基于累计工具结果回答
          -> CoderAgentResult
```

工具执行路径会使用 `ToolRoutingDecision.tools[*].suggested_input` 作为工具入参。若路由结果选择了需要 `file_path`、`query`、`target_path` 等必要参数的工具，但用户没有提供对应参数，主 Agent 不会编造参数或直接调用工具，而是把 `clarifying_question` 交给回答链，让回答模型提示用户补充信息。

目前主 Agent 支持执行 `src.tools.REPOSITORY_TOOLS` 中注册的工具，包括 `list_files`、`search_code`、`read_file`、`index_repository` 和 `retrieve_context`。工具结果会保存到 `CoderAgentResult.tool_results`，并通过回答 prompt 的 `context` 段传给最终回答链。

循环式工具路由默认最多执行 3 轮，可以通过 `max_tool_rounds` 调整。每轮执行后，主 Agent 会把累计工具结果传回路由 Agent；如果路由 Agent 判断已有信息足够回答，会返回 `needs_tools=false` 并进入最终回答链。主 Agent 也会记录已经执行过的工具调用签名，避免重复调用同一个工具和相同参数。

示例：

```python
from src.agents import get_coder_agent

agent = get_coder_agent()
result = agent.run("temperature 是控制什么的？")

print(result.answer)
print(result.routing_decision.intent)
```

流式输出：

```python
from src.agents import get_coder_agent

agent = get_coder_agent()

for chunk in agent.stream("temperature 是控制什么的？"):
    print(chunk, end="", flush=True)
print()
```

如果需要调整模型温度：

```python
from src.agents import get_coder_agent

agent = get_coder_agent(temperature=0.1, max_tool_rounds=4)
```

`get_coder_agent()` 会创建一个模型 client，并将同一个 client 同时传给主回答链和 `ToolRoutingAgent`。

`get_coder_agent()` 只暴露常用参数：

- `model`: 可选的模型 client；不传时根据 `temperature` 创建默认模型。
- `temperature`: 默认 `0.2`。
- `max_tool_rounds`: 默认 `3`。
- `session_id`: 短期记忆会话 ID。
- `user_id`: 长期个人记忆用户 ID。
- `routing_memory_messages`: 路由 Agent 读取的最近短期记忆条数，默认 `4`。

回答链、SQLite 短期记忆、Chroma 长期个人记忆、最终回答读取全部历史、长期记忆检索 4 条、自动保存明确偏好等配置都在函数内部使用默认值。

回答链由 `answer_chain.py` 中的 `get_answer_chain()` 构建，默认结构为：

```text
get_chat_prompt() | model | StrOutputParser()
```

`get_chat_prompt()` 会接收 `input`、可选 `context` 和通过 `MessagesPlaceholder` 注入的 `history`。没有工具结果时 `context` 为空；工具执行完成后，`CoderAgent` 会将路由原因、工具入参、工具输出或工具错误写入 `context`，再交给回答链生成最终答案。若启用了长期个人记忆，相关用户偏好也会写入 `context`。

`CoderAgent` 本身只接收已经构建好的 `answer_chain`，不负责拼接 prompt、model 和 parser。

## SQLite 短期记忆

`get_coder_agent()` 默认会创建 `SQLiteShortTermMemory`，把短期会话消息持久化到：

```text
src/storage/short_term_memory.sqlite3
```

该目录属于运行产物，已经被 `.gitignore` 忽略。

默认记忆策略：

- 最终回答链默认读取该 session 的全部历史消息。
- 路由 Agent 读取最近 4 条历史消息，用于理解“继续”“这个文件”等指代。
- 每次 `run()` 或 `stream()` 完成后，会追加一条用户消息和一条助手消息。

最终回答链使用 `SQLiteShortTermMemory.load_recent_chat_messages()` 将历史转换成 LangChain 的 `HumanMessage` / `AIMessage`，再通过 `MessagesPlaceholder("history")` 注入 prompt。路由 Agent 仍使用渲染后的短文本历史作为路由判断输入。

可以通过参数调整：

```python
from src.agents import get_coder_agent

agent = get_coder_agent(
    session_id="demo",
    routing_memory_messages=4,
)
```

最终回答链默认读取该 session 的全部历史；路由 Agent 默认读取最近 4 条历史，可以通过 `routing_memory_messages` 调整。

## Chroma 长期个人记忆

`get_coder_agent()` 默认会创建 `ChromaLongTermMemory`，把用户偏好和长期协作约定持久化到：

```text
src/storage/long_term_memory
```

长期个人记忆按 `user_id` 隔离；短期对话按 `session_id` 隔离。换句话说，用户可以开启新的 session，但继续复用同一个 `user_id` 下的长期偏好。

默认行为：

- 每次回答前，主 Agent 会根据当前问题检索最近相关的长期个人记忆。
- 检索到的记忆会注入回答 prompt 的 `context`，只用于回答风格、默认偏好和协作习惯。
- 当用户明确说出“请记住”“记住”“以后默认”“我的偏好”等表达时，主 Agent 会自动把这句话写入长期个人记忆。

手动写入偏好：

```python
from src.agents import get_coder_agent

agent = get_coder_agent(user_id="peter")
memory_id = agent.remember_preference("用户偏好：回答时先给结论，再给简短原因。")
print(memory_id)
```

清除当前用户的长期记忆：

```python
agent.clear_long_term_memory()
```

如果要关闭长期记忆：

```python
from src.agents import CoderAgent, get_answer_chain, get_tool_routing_agent
from src.models import get_ali_model_client

model = get_ali_model_client(temperature=0.2)
agent = CoderAgent(
    routing_agent=get_tool_routing_agent(model=model),
    answer_chain=get_answer_chain(model=model),
    long_term_memory=None,
)
```

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

### CoderAgentResult

字段：

- `input`: 用户原始输入。
- `answer`: 最终回答文本。
- `routing_decision`: 工具路由决策。
- `routing_decisions`: 多轮工具路由的完整决策历史。
- `tool_results`: 工具执行结果列表；没有调用工具时为空数组。

### ToolExecutionResult

字段：

- `name`: 工具名。
- `input`: 实际传给工具的参数。
- `output`: 工具返回文本。
- `error`: 工具调用错误；成功时为空字符串。

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
