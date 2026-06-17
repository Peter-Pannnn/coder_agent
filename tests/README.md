# tests

## 清除短期记忆

运行下面脚本会清空默认 SQLite 短期记忆数据库中的所有 session 记录：

```powershell
python tests\clear_memory.py
```

如果要清理指定数据库：

```powershell
python tests\clear_memory.py --db-path src\storage\short_term_memory.sqlite3
```
