# tests

## 清除短期记忆

运行下面脚本会清空默认 SQLite 短期记忆数据库中的所有 session 记录，并尝试清空默认 Chroma 长期个人记忆：

```powershell
python tests\clear_memory.py
```

如果要清理指定数据库：

```powershell
python tests\clear_memory.py --db-path src\storage\short_term_memory.sqlite3
```

如果要清理指定长期记忆目录：

```powershell
python tests\clear_memory.py --long-term-path src\storage\long_term_memory
```

## 长期记忆集成测试

`test_long_term_memory.py` 会在临时 Chroma 目录中写入并检索一条长期个人记忆。它需要安装 `chromadb`、`langchain_chroma`、`langchain_core`，并设置 `DASHSCOPE_API_KEY`；缺少条件时会自动跳过。
