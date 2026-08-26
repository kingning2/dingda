# Domain Registry

该表只负责把代码路径路由到领域入口。系统业务总览见 [architecture](../architecture/README.md)。

| 领域 | 主要路径 | 入口 | 状态 |
|---|---|---|---|
| Agent | `apps/desktop/src-tauri/src/**`（agent / commands） | [agent](../domains/agent/README.md) | active |
| Python Sidecar（例外） | `python/**` | [python-runtime](../domains/python-runtime/README.md) | active |
| Runtime / Worker | `apps/desktop/src-tauri/src/infrastructure/runtime/**` | [runtime](../domains/runtime/README.md) | active |
| Channel | `apps/desktop/src-tauri/src/**/channel/**` · `python/**/channel/**` | [channel](../domains/channel/README.md) | active |
| Contracts | `contracts/**` | [contracts](../domains/contracts/README.md) | active |
| Storage | `apps/desktop/src-tauri/src/infrastructure/storage/**` | [storage](../domains/storage/README.md) | active |
| OCR | `apps/desktop/src/features/plugin/` · 插件配置 | [ocr](../domains/ocr/README.md) | 语言包下载已落地；识别未实现 |
| Documentation | `docs/managed/**` | [documentation](../domains/documentation/README.md) | active |

新增领域时一并定义互斥的管理范围；同一路径若匹配多个领域，以更具体的路径为主领域。
