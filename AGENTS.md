# DingDa 开发规范

桌面端 Web 产品（React）+ Tauri 客户端（Rust workspace）+ Python Server（`packages-py/` uv workspace）。

本文件是**开发规范说明**：写代码前必读，规则按编号引用（如「见规范 1.4」）。

**写代码前也必读 [`CONSTRAINTS.md`](CONSTRAINTS.md)**（质量约束与棘轮基线）——不得为让改动
通过而放宽它；放宽走例外表（带负责人与过期日），守卫 `pnpm check:fast` 会盯着 diff。

**语言规范（skill，按需加载）**：`.pi/skills/py-dev/`、`.pi/skills/rs-dev/`、
`.pi/skills/web-dev/`、`.pi/skills/pi-hooks/`——每个包的目录树、示例、注意项都在对应
skill 里，本文件只保留全局约束与索引。

## 1. 仓库形态：三个可运行入口

| 入口 | 目录 | 命令 | 语义 |
|------|------|------|------|
| Web 应用 | `apps/web/` | `pnpm dev`（Vite :1420） | React 装配：路由表 / 页面 / `boot/` 启动编排；浏览器直联 Server 联调 |
| Python Server | `packages-py/api/` | `uv run python -m api`（FastAPI :8787） | 唯一状态持有方；产品能力全部经 HTTP/SSE（SQLite 在 Python） |
| 桌面客户端 | `packages-rs/client/` | `pnpm tauri dev` | 壳 = Web + Server 的打包体 + OS 能力（起停 Server、对话框） |

1.1 前端是 **pnpm 工作区**，Rust 是 **Cargo 工作区**，Python 是 **uv 工作区**，三套互不干涉。

1.2 前端成员在 `packages/` + `apps/`。`pnpm-workspace.yaml` 的 glob **不要**写成
    `packages*`，否则会把 `packages-rs` 当 JS 包扫。

1.3 **前端已无仓库根 `src/`**，内容拆入 `apps/web` 与 `packages/`。

1.4 桌面壳在 **`packages-rs/client`**（不是 `src-tauri`）。Tauri CLI 默认只认
    `<cwd>/src-tauri`，故 `pnpm tauri` 走 `scripts/tauri.mjs` 注入 `TAURI_APP_PATH`。
    **不要直接 `pnpm exec tauri`**。

1.5 Rust 工作区根在仓库根 `Cargo.toml`，编译产物在 `<repo>/target/`。

1.6 成员包边界与依赖方向见 [`packages/README.md`](packages/README.md) 与
    [`packages-rs/README.md`](packages-rs/README.md)；目录级细则见各目录 `README.md`
    （116 个目录 README 已全覆盖，写码前先读目标目录的 README）。

1.7 **目录地图**（每个文件夹怎么用；分包判定细则见对应 skill 第「各包收什么」节）

```text
packages-py/  Python（uv workspace；分层 Agent → Tool → Crawler → BrowserPort → Adapter）
  agent/           Planner/Executor/LangGraph/Workflow 编排（禁 import Playwright/SQLite/电商包）
  tools/           Agent 可调用能力：名称 + Schema + 错误模型 + timeout + cancellation
  crawler/         平台抓取：core/ + sources/<platform>/ + extraction/（平台特例只进 sources）
  browser/         浏览器生命周期：adapters/<browser>/（禁商品模型与 Agent 推理）
  channels/        登录/账号/IM：channels/<platform>/（ali1688 · xianyu · xiaohongshu）
  api/             FastAPI HTTP：routes/<域>/<动作>.py 一端点一文件 + boot/ + lib/
  domains/         应用服务：account/channel/watch/knowledge/...（禁 service.py 上帝类）
  contracts/       与前端的线协议（pydantic；改字段先改这里，见 4.6）
  infrastructure/  db / events 底座
  core/            errors / http 机制底座（AppError 在 core/errors.py）
  ※ 测试统一在 packages-py/api/tests/<域>/，不跟包走

packages/    前端（pnpm workspace；依赖单向：应用 → 业务域 → 骨架 → 底座 → 令牌/协议）
  contracts/       与 Python 的线协议类型（纯类型，与 packages-py/contracts 同步）
  client/routes/   路由契约 paths.ts
  client/app-state/ 跨域共享 UI 状态（zustand）
  client/runtime/  HTTP 传输、能力开关、错误上报、guards 字段判定器
  client/ui-theme/ ui-primitives/ ui-layout/ ui-feedback/
                   底座：设计令牌 · 原子组件 + cn() · 外壳导航 · 错误边界
  client/ui-home|ui-ai|ui-composer|ui-account|ui-agent|ui-crawler|ui-watch|ui-workflow/
                   业务域包（一包一域互不横引；跨域组合只允许在 apps/web 装配层）

packages-rs/ Rust（Cargo workspace；依赖 common ← camoufox ← python ← client）
  common/          日志出口、路径解析、平台标签（唯一底座）
  camoufox/        Camoufox 定位与解压
  python/          Python Server 子进程生命周期
  client/          Tauri 壳：窗口/托盘/IPC；commands/ 一命令一文件 + generate_handler! 集中登记
```

## 2. 分层规则（原文必遵）

2.1 **八条核心规则**（硬约束）：

1. Browser = 浏览器能力层，只负责启动、Context、Page、导航、点击、输入、Cookie、
   Session、截图、网络监听等通用能力。
2. Crawler = 平台采集层，只负责闲鱼/1688 等平台的搜索、详情、解析、标准化、Snapshot、Dedup。
3. Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
4. Browser 禁止出现 Xianyu、1688、商品、价格等平台业务逻辑。
5. 平台新增只修改 `crawler/sources/<platform>/`，浏览器新增只修改 `browser/adapters/<browser>/`。
6. 登录/账号语义属于 `channels/<platform>/`，Browser 只负责通用 Session/Cookie 能力。
7. Agent / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
8. 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

路径均在 `packages-py/<pkg>/src/<pkg>/` 下。产品 SQLite 继续留在 Python
`packages-py/infrastructure/src/infrastructure/db`，不要为 Browser/Crawler 新开 Rust DB。

2.2 Python 分层依赖：`Agent → Tool → Crawler → BrowserPort → Adapter`；跨层 import = 错。

2.3 `api/` 只做 HTTP 校验与调用；`domains/` 承担应用服务；`channels/` 承担登录/账号/IM。

2.4 **Channel ≠ Source ≠ Browser**：渠道管登录会话语义，Source 管平台采集，Browser 只管
   通用浏览器能力；三者的共同字段下沉到各自插座基类，特例留在平台目录里。
   多实现能力统一走**插座模式**（插座→实现→注册表→生命周期收口→消费方注入→装配点，
   禁止业务里 if/else 选实现），范本与操作规则见 `.pi/skills/py-dev/SKILL.md` 第 2.1 节。

2.5 **两个「Agent」禁止混用**：产品 Agent（`agent_id="dingda"`，模型由 Server 侧
   `DINGDA_LLM_*` 决定，AGENTS.md 5.5）≠ 编码 agent（本文件的读者）。产品能力归产品
   Agent，开发流程归编码 agent；不要在产品代码里写「开发流程」语义，反之亦然。

2.6 **IPC 决策**：产品能力一律经 HTTP/SSE（Web 与桌面共用）；桌面壳不做 Rust IPC 业务
   通道，只做 OS 能力与进程编排（见 5.2）。

2.7 前端三条结构纪律（依赖单向、跨域状态下沉、包不 import 应用源码）见
   `.pi/skills/web-dev/SKILL.md` 第 2 节。

## 3. 行为铁律（反模糊，对 AI 与人同样生效）

3.1 **只做被明确要求的事**：不主动完善、不扩展、不加「顺手」的重构；占位文案、示例数据、
    模拟回复一律禁止——除非用户当前明确要求。

3.2 **YAGNI 五级台阶**（要新建东西前自问，逐级往上）：
    ① 真的需要吗？② 仓库里已有吗（先 Grep）？③ 标准库能做吗？④ 已装依赖能做吗？
    ⑤ 一行能搞定吗？全否才新建。新文件头写 `// ACT: <理由>`，理由消失即删。

3.3 **修根因不修症状**：改 bug 先 Grep 该函数/组件的所有调用方，在公共处改一次；
    禁止为过测试改断言、加 `@ts-ignore`、吞异常。

3.4 **命名无例外**：文件/目录命名、组件符号、变量速查表见
    `.pi/skills/web-dev/SKILL.md` 第 1 节（前端）与各语言 skill「命名」节。
    已存在的例外不作为新代码的参考依据。

3.5 **回答与注释用中文**；标识符用英文。

## 4. 新增能力落点（写在这里，勿另起炉灶）

4.1 **新增 HTTP 端点**：`packages-py/api/src/api/routes/<域>/<动作>.py`，一端点一文件；
    一个路由文件只注册一个 HTTP 方法与路径，读取、保存等必须拆开，不合并读写。
    域 `__init__.py` 挂 `APIRouter(prefix, tags)`，并在 `routes/__init__.py` 聚合。
    详见 [`packages-py/api/src/api/README.md`](packages-py/api/src/api/README.md)。

4.2 **新增 Tool**：`uv run python -m tools.scaffold <name>` 生成
    `packages-py/tools/src/tools/<name>/__init__.py` 骨架；registry 自动发现，
    `tools.cli` 子命令同步出现，无需手工注册。

4.3 **新增平台**：只改 `packages-py/crawler/src/crawler/sources/<platform>/`。

4.4 **新增浏览器**：只改 `packages-py/browser/src/browser/adapters/<browser>/`。

4.5 **新增登录渠道**：只改 `packages-py/channels/src/channels/<platform>/`。

4.6 **改产品 API**：先契约（`packages-py/contracts` ↔ `packages/contracts`），再 Python，
    再 React；不必改 Rust。

4.7 **新增 Tauri 命令**：`commands/<域>.rs` + `commands/mod.rs` + `generate_handler!`
    各一行；映射表见 `.pi/skills/rs-dev/SKILL.md` 第 4 节。

## 5. 禁止清单

5.1 禁止垃圾桶目录：`utils/`、`helpers/`、`services/`、`common/`；包名必须对应一个业务域或一层机制。

5.2 禁止第二套 Skill / 规范副本：规范只此一份（本文件 + `.pi/skills/`）；产品不用 Rust IPC crate。
    不再创建 `.cursor/`、`.agents/` 规范目录（已删）。

5.3 Agent / Tool 不得直接 import Playwright、Camoufox、SQLite 或具体电商平台包。

5.4 禁止 `domains/*/service.py` 上帝类；新代码目录在
    `packages-py/{agent,crawler,browser,tools}/src/<pkg>/`。

5.5 AI 能力统一走内置产品 Agent（`agent_id="dingda"`，模型由 Server 侧 `DINGDA_LLM_*`
    决定）；Agent / Tool 一律经 Tool → Crawler → Browser。

5.6 提交规范：`<type>(<scope>): 中文简述`，按模块边界拆 commit；type 用
    feat/fix/refactor/docs/test/chore。

## 6. Skill 索引（写哪栈，读哪份）

| Skill | 何时加载 | 内容 |
|-------|----------|------|
| `.pi/skills/py-dev/SKILL.md` | 改 `packages-py/**` | 十包各自收什么、插座模式六环、路由映射、AppError、验证命令 |
| `.pi/skills/py-flows/SKILL.md` | 接新爬虫平台/排障浏览器/写 Tool 编排 | 运行链路实证：浏览器从壳到 Page 起停全链、爬虫从 Tool 到 Source 调用全链、新增平台三步 |
| `.pi/skills/rs-dev/SKILL.md` | 改 `packages-rs/**` | 四包边界、命令映射表、三条路径陷阱、验证命令 |
| `.pi/skills/web-dev/SKILL.md` | 改 `apps/web/**` 或 `packages/**` | 命名速查、guards 容错、16 包地图、三条结构纪律 |
| `.pi/skills/pi-hooks/SKILL.md` | 调整 pi 扩展/`/命令`/skill 加载 | 三挂载点、事件面、本仓扩展示例 |

架构边界存疑时：先读本文件第 2 节，再读对应 skill 的「各包收什么」表。

## 7. 常用命令

```bash
pnpm check:fast                # < 5s：floor-guard + layers-guard（写完随手跑）
pnpm build                     # 前端：check:deps + check:unused --strict + tsc + vite build
pnpm test                      # vitest
uv run ruff check packages-py --select E4,E7,E9,F
uv run pytest packages-py/api/tests -m "not integration"   # 集成测试只在本地跑
cargo check --workspace --all-targets
```

- 阈值、棘轮基线与例外规则：[`CONSTRAINTS.md`](CONSTRAINTS.md)；架构决策史：
  [`docs/adr/`](docs/adr/)。
- 桌面壳必须经 `pnpm tauri`（注入 `TAURI_APP_PATH`），不要直接 `pnpm exec tauri`。
