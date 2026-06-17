# storage

`storage` 目录用于存放项目运行过程中产生的本地持久化数据。

## Chroma 默认目录

代码仓库索引工具 `index_repository` 默认会把 Chroma 向量库保存到：

```text
src/storage/chroma
```

对应参数：

```python
index_repository.invoke({
    "root_path": "...",
    "storage_mode": "local",
    "persist_directory": "src/storage/chroma",
})
```

## 存储模式

当前 Chroma 支持两种模式：

- `local`：保存到本地目录，默认使用 `src/storage/chroma`。
- `memory`：仅保存在当前 Python 进程内存中，进程结束后索引消失。

如果使用 `memory` 模式，索引和检索必须发生在同一个 Python 进程中。

## SQLite 短期记忆

`CoderAgent` 默认会把会话短期记忆保存到：

```text
src/storage/short_term_memory.sqlite3
```

该 SQLite 数据库用于按 `session_id` 保存最近对话消息。主回答链默认读取该 session 的全部历史消息，工具路由默认读取最近 4 条历史消息。

## Chroma 长期个人记忆

`CoderAgent` 默认会把用户长期偏好保存到：

```text
src/storage/long_term_memory
```

该 Chroma collection 用于按 `user_id` 保存用户偏好、协作习惯和长期项目约定。主 Agent 会在回答前按当前问题检索相关长期记忆，并把结果注入回答上下文。

## Git 规则

本地 Chroma 数据和 SQLite 记忆数据库都属于运行产物，不应提交到 Git。默认目录已经加入 `.gitignore`。
