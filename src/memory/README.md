# memory

`memory` 目录存放 CoderAgent 的记忆实现。

## long_term_memory.py

`long_term_memory.py` 实现 Chroma 持久化长期个人记忆。

默认数据库路径：

```text
src/storage/long_term_memory
```

主要接口：

- `ChromaLongTermMemory`: Chroma 长期个人记忆实现。
- `LongTermMemoryRecord`: 单条长期记忆检索结果。
- `DEFAULT_LONG_TERM_MEMORY_PERSIST_DIRECTORY`: 默认 Chroma 持久化目录。

长期个人记忆按 `user_id` 隔离，适合保存用户偏好、协作习惯、默认语言、解释粒度和长期项目约定。

`add_memory()` 会写入一条长期记忆；`retrieve_memories()` 会根据当前问题语义检索相关记忆；`render_relevant()` 会把检索结果渲染成可注入 prompt 的上下文。

## short_term_memory.py

`short_term_memory.py` 实现 SQLite 持久化短期记忆。

默认数据库路径：

```text
src/storage/short_term_memory.sqlite3
```

主要接口：

- `SQLiteShortTermMemory`: SQLite 短期记忆实现。
- `ShortTermMemoryMessage`: 单条短期记忆消息。
- `DEFAULT_SHORT_TERM_MEMORY_DB_PATH`: 默认数据库路径。

短期记忆按 `session_id` 隔离。`limit=None` 时读取该 session 的全部历史消息；传入整数时读取最近 N 条。

`render_recent()` 会把历史渲染成普通文本，适合路由 Agent 使用。

`load_recent_chat_messages()` 会把历史转换成 LangChain 的 `HumanMessage` / `AIMessage`，适合配合 `MessagesPlaceholder("history")` 注入最终回答 prompt。
