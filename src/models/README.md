# models

`models` 目录负责封装项目中使用的大模型、Embedding 模型和重排序模型客户端。其他模块不直接关心底层厂商 API，只通过这里提供的统一接口获取模型实例。

## 对外接口

模型接口统一从 `src.models` 导出：

```python
from src.models import (
    ALI_TONGYI_API_KEY_OS_VAR_NAME,
    get_lc_model_client,
    get_ali_model_client,
    get_ali_embeddings,
    get_ali_rerank,
    get_ali_clients,
)
```

## 环境变量

当前默认使用阿里通义千问兼容 OpenAI 格式的接口。

需要设置环境变量：

```text
DASHSCOPE_API_KEY
```

该环境变量名称由 `ALI_TONGYI_API_KEY_OS_VAR_NAME` 定义。

## 接口说明

### get_lc_model_client

功能：通过 LangChain 的 `ChatOpenAI` 创建一个 OpenAI 兼容模型客户端。

用途：

- 连接支持 OpenAI 兼容协议的大模型服务。
- 自定义 `api_key`、`base_url`、`model`、`temperature` 等参数。
- 作为更底层的通用模型客户端构造函数。

### get_ali_model_client

功能：创建阿里通义千问聊天模型客户端。

用途：

- 项目默认聊天模型入口。
- 供 Agent、测试脚本和链式调用使用。
- 可通过参数切换模型和温度。

示例：

```python
from src.models import get_ali_model_client

model = get_ali_model_client(temperature=0.2)
response = model.invoke("请介绍一下你自己。")
print(response.content)
```

### get_ali_embeddings

功能：创建阿里通义千问 Embedding 模型实例。

用途：

- 为代码片段生成向量。
- 配合 Chroma 构建代码仓库语义索引。
- 被 `index_repository` 和 `retrieve_context` 等工具使用。

### get_ali_rerank

功能：创建阿里重排序模型实例。

用途：

- 对初步检索结果进行二次排序。
- 提高 RAG 场景下的上下文相关性。
- 后续可接入检索增强问答流程。

### get_ali_clients

功能：一次性返回聊天模型客户端和 Embedding 客户端。

用途：

- 快速初始化模型相关依赖。
- 适合在 Agent 启动阶段统一创建模型对象。

## 注意事项

- 使用模型、Embedding 或重排序能力前，需要先设置 `DASHSCOPE_API_KEY`。
- 当前模块只负责创建客户端，不负责业务提示词、工具调用或 Agent 编排。
- 如果后续接入其他模型厂商，建议继续在该目录下扩展统一的模型创建接口。
