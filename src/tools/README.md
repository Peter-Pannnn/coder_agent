# tools

`tools` 目录存放 Codebase Agent Assistant 可调用的工具。每个工具单独放在一个文件中，方便维护、测试和按需注册到 LangChain Agent。

## 对外接口

工具统一从 `src.tools` 导出：

```python
from src.tools import REPOSITORY_TOOLS
from src.tools import list_files, read_file, search_code, index_repository, retrieve_context
```

`REPOSITORY_TOOLS` 是当前默认工具集合，可直接注册给 LangChain Agent。

## 工具列表

### list_files

文件：`list_files.py`

功能：列出指定目录下的文件和文件夹结构。

用途：

- 快速了解代码仓库目录结构。
- 帮助 Agent 判断项目类型、核心目录和可能入口。
- 在回答问题前获取仓库整体上下文。

主要参数：

- `root_path`：要扫描的目录路径，默认当前目录。
- `max_depth`：最大展示深度，避免输出过长。
- `include_hidden`：是否包含隐藏文件和隐藏目录。

输出：文本形式的目录树。

### read_file

文件：`read_file.py`

功能：读取指定文本文件内容，支持按行号读取部分内容。

用途：

- 查看某个文件的具体实现。
- 读取搜索结果对应的代码上下文。
- 避免一次性读取大文件导致上下文过长。

主要参数：

- `file_path`：目标文件路径。
- `start_line`：起始行号，默认第 1 行。
- `end_line`：结束行号，默认读取到文件末尾。

输出：带文件路径和行号的文本内容。

### search_code

文件：`search_code.py`

功能：基于关键词搜索代码，优先使用 `ripgrep`，如果系统没有安装 `rg`，会退回到 Python 文本搜索。

用途：

- 定位函数、类、变量、配置项和错误信息。
- 在语义检索前做精确关键词搜索。
- 快速查找某个功能可能在哪些文件中实现。

主要参数：

- `query`：搜索关键词。
- `root_path`：搜索根目录。
- `max_results`：最大返回结果数量。

输出：匹配文件、行号、列号和对应代码行。

### index_repository

文件：`index_repository.py`

功能：扫描仓库中的文本和代码文件，切分为代码片段，并写入 Chroma 向量数据库。

用途：

- 为代码仓库构建语义检索索引。
- 支持后续通过自然语言查询相关代码片段。
- 作为 RAG 问答流程的基础能力。

主要参数：

- `root_path`：要索引的仓库目录。
- `storage_mode`：Chroma 存储模式，`local` 表示保存到本地，`memory` 表示仅保存在当前进程内存中，默认 `local`。
- `persist_directory`：Chroma 本地持久化目录，默认 `src/storage/chroma`。
- `collection_name`：Chroma collection 名称，默认 `codebase`。
- `chunk_size`：代码片段大小。
- `chunk_overlap`：片段重叠大小。
- `max_file_size_kb`：单文件最大索引大小。

输出：索引摘要，包括存储模式、索引目录、collection、文档片段数量和跳过文件数量。

注意：该工具会调用 embedding 模型，需要先设置 `DASHSCOPE_API_KEY`。

### retrieve_context

文件：`retrieve_context.py`

功能：从 Chroma 中检索和用户问题语义相关的代码片段。

用途：

- 根据自然语言问题获取相关代码上下文。
- 为 Agent 回答问题、解释代码或生成修改计划提供依据。
- 和 `index_repository` 配合构成基础 RAG 流程。

主要参数：

- `query`：自然语言查询。
- `storage_mode`：Chroma 存储模式，需和 `index_repository` 保持一致，支持 `local` 和 `memory`。
- `persist_directory`：Chroma 本地持久化目录，默认 `src/storage/chroma`。
- `collection_name`：Chroma collection 名称。
- `k`：返回的相关片段数量。

输出：按相关性排序的代码片段，包含来源文件、行号范围和相似度分数。

注意：使用前需要先运行 `index_repository` 建立索引。若使用 `memory` 模式，索引和检索必须发生在同一个 Python 进程中。

## 工具辅助模块

### utils

文件：`utils.py`

功能：存放多个工具共享的辅助逻辑。

包含能力：

- 路径解析。
- 忽略目录判断。
- 仓库文件遍历。
- 文本文件读取。
- 文本切块。
- 默认索引文件类型配置。
- Chroma 本地/内存存储模式选择。

`utils.py` 不是直接注册给 Agent 的工具，而是供其他工具复用的基础模块。


