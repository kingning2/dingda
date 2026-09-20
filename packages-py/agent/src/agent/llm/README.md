# llm

LangChain ``ChatOpenAI``（OpenAI 兼容口）+ 供应商目录。DeepSeek / 豆包都走兼容协议。

| 文件 | 职责 |
|---|---|
| `client.py` | `LlmClient` / `create_chat_model` |
| `models.py` | `LlmSettings` / `ChatResult` |
| `errors.py` | SDK 异常 → `AppError` |
| `providers/<id>.py` | 厂家目录事实（base_url / 默认模型 / key 环境变量） |

新增厂家：加 `providers/<id>.py` 的 `PROVIDER`，在 `providers/__init__._CATALOG` 加一行；
若有私有请求字段（如豆包 thinking），在 `create_chat_model` 里按 `provider_id` 挂上。

[providers/](providers/README.md) · [返回上层](../README.md)
