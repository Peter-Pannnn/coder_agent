# memory

`memory` 目录存放 CoderAgent 的记忆实现。

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
