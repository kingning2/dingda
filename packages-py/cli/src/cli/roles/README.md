# cli/roles

会话角色插座：一次 CLI 会话是**谁在跑**。父 / 子 agent 的差异全在这三个方法里。

| 角色 | 提示词 | 注入 | 工作目录 |
|---|---|---|---|
| `ParentRole`「父 agent」 | `system.md` 选品前言 + 平台提示 | 用 runtime 声明的注入模式（全套选品工具） | 调用方给的 cwd（默认进程 cwd） |
| `ChildRole`「子 agent」 | 只发本次 prompt | `"none"`，不注入 | 系统临时目录 `dingda-child-agent-*`（不进仓库） |

子 agent 那三条都是为了「只做一件事、别乱来」：不带人设、不给工具（免递归）、
cwd 隔离（免得它顺手读到仓库里的现成答案）。

## 本目录文件

- `base.py` — `AgentRole`（插座）：`compose_prompt` / `mcp_mode` / `workdir`
- `parent.py` — `ParentRole`：选品调研，可调 search / product / compare / login / preview
- `child.py` — `ChildRole`：单一职责（如修 DOM 选择器），无工具、cwd 隔离
- `registry.py` — `get_role(name)`；`"parent"` / `"child"`，默认父 agent

## 子目录

无。加新角色：本目录加插头 + registry 登记一行。
