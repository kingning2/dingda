# providers

一个厂家一个文件（目录事实）。登记表在 [`__init__.py`](__init__.py)。

| 文件 | 说明 |
|---|---|
| `deepseek.py` | DeepSeek 目录 |
| `doubao.py` | 豆包目录 + `EXTRA_BODY`（thinking） |
| `base.py` | `CatalogProvider` 形状 |

Chat 模型由 [`../client.py`](../client.py) 的 `create_chat_model` 统一建，不再各写一个 Bot 类。

[返回上层](../README.md)
