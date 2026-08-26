# DingDa Managed Docs

这里是 DingDa 的增量文档管理中心。

**系统业务与架构叙事唯一入口：** [`architecture/README.md`](architecture/README.md)。

## Agent 最小读取路径

处理任何改动时，只按下面顺序读取，找到足够上下文后立即停止：

1. [`architecture/README.md`](architecture/README.md)（业务）或本文件（治理）；
2. [`ACTIVE.md`](registry/ACTIVE.md)；
3. 与任务相关的一个领域入口；
4. 当前变更记录；
5. 只有发生冲突时才读取决策记录或历史记录。

禁止默认递归读取整个 `docs/managed/`。

## 文档地图

| 目录 | 管理范围 | 拆分单位 |
|---|---|---|
| `architecture/` | 系统业务与架构总览（唯一叙事入口） | 一份 README |
| `registry/` | 小型导航与当前工作 | 活跃项、领域目录 |
| `domains/` | 某个稳定领域的现状 | 一个领域一个目录 |
| `roadmaps/` | 领域里程碑与尚未完成的目标 | 一个领域一份活跃路线图，过大时按里程碑拆分 |
| `changes/` | 每次代码改动的计划与结果 | 一个变更一个文件，按年月分片 |
| `decisions/` | 长期有效的架构决策 | 一个决策一个文件，按领域分片 |
| `templates/` | 新文档模板 | 一种文档一个模板 |
| `archive/` | 过期索引与归档规则 | 只保留导航，不集中堆正文 |

## 修改门禁

任何代码、契约、配置或依赖修改开始前，必须先创建一份 Change Record，并至少填写：

- 目标与非目标；
- 影响范围；
- 契约、Feature 和分层检查；
- 验收方式；
- 状态 `proposed`。

开始修改代码时将状态改为 `in_progress`；验证完成后补充实际结果并改为 `completed`。紧急修复也不能跳过记录，但允许使用精简模板。

完整规则见 [`GOVERNANCE.md`](GOVERNANCE.md)，上下文控制见 [`CONTEXT_POLICY.md`](CONTEXT_POLICY.md)。

## 命名规则

- Change ID：`CHG-YYYYMMDD-NNN-short-name`
- Epic ID：`EPIC-YYYYMMDD-NNN-short-name`
- Decision ID：`ADR-NNNN-short-name`
- 领域目录：短名小写，例如 `python-runtime`、`contracts`、`agent`
- 文件名只使用小写英文、数字和连字符

## 当前边界

此系统目前提供文档约束，不自动阻止未登记的代码修改。若要形成强制门禁，后续应在不违背仓库协作规则的前提下，将入口接入根级 Agent 指令，并增加只校验、不自动生成文档的提交检查。
