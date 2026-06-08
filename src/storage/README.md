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

## Git 规则

本地 Chroma 数据属于运行产物，不应提交到 Git。默认目录已经加入 `.gitignore`。
