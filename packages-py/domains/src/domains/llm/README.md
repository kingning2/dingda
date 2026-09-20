# domains/llm

模型凭据域：管理「用哪个供应商、哪把 key、哪个模型」这件事，支持**多条并存、一条生效**。

回答两个问题：

1. 我现在有哪些可用的模型凭据？（多平台 / 同平台多把 key）
2. 哪一条正在生效，它还好使吗？

不负责「怎么跟模型说话」（那是 [agent/llm](../../../agent/src/agent/llm/README.md)），
不负责 key 的落盘细节（那是
[infrastructure/db/llm_credentials.py](../../../../infrastructure/src/infrastructure/db/README.md)）。

## 为什么供应商目录是注入进来的

目录的真相在 `agent.llm.providers`，而 `domains` **不许** import `agent`（依赖方向反了）。
抄一份目录进本包会立刻分叉，所以走构造参数注入，与 `RunContext.cookie_resolver`
同一个判断标准。有了它，供应商合法性校验才能留在本层，而不是漏到路由里各写一遍。

## 本目录文件

### `service.py`

`LlmCredentialService(catalog=…)`：`list_providers` / `list` / `create` / `update` /
`delete` / `activate` / `record_check` / `import_from_env`。

三条口径值得记住：

- **key 只进不出**：出参一律 `api_key_masked`，原文永不出这一层。改凭据时 `api_key`
  为空表示「不改」——前端不回填原文，也不该回填
- **`base_url` 的「不改」与「清空」靠 `model_fields_set` 区分**：字段没出现 = 不改，
  出现且为 `None` = 恢复供应商默认地址
- **`effective_base_url` 在这里补默认值**：库里存 `NULL` 表示跟随供应商默认，
  补值属展示口径，别把默认值抄进库

`import_from_env` 收编 `.env` 里那份配置，按「同供应商 + 同 key」查重，
一条都没有时才让导入的那条直接生效。

### `__init__.py`

包标记。

## 子目录

无。表结构：[infrastructure/db/schema.py](../../../../infrastructure/src/infrastructure/db/README.md)
的 `LLM_CREDENTIALS_TABLE_SQL`。
HTTP 落点：[api/llm.py](../../../../api/src/api/README.md)。
