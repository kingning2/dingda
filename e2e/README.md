# e2e

桌面端 E2E：驱动 **Tauri 壳**（`target/debug/client`）跑冒烟。

驱动方式是 `driverProvider: 'embedded'` —— 应用在进程内跑一个 W3C WebDriver
服务，**不需要 tauri-driver，也不需要 msedgedriver**，也不依赖 WebView2 的远程
调试端口。代价是 Rust 侧要引入 `tauri-plugin-wdio-webdriver`；已用 Cargo feature
`e2e` 隔离，**release 与日常 dev 构建都不含它**，生产二进制不受影响。

> feature 而非 `[target.'cfg(debug_assertions)'.dependencies]`：Cargo 的 target 段
> 不支持 `debug_assertions`，写了会被忽略并报 warning，依赖照样进 release。
> 所以**必须显式 `--features e2e`**，否则壳里没有 WebDriver 服务，
> session 创建会失败。

不用 external（tauri-driver）的原因：wry 在 `additional_browser_args` 为 None 时
会自行构造默认值并调 `set_additional_browser_arguments()`，而 WebView2 该属性
优先级高于环境变量，于是 tauri-driver 注入的 `--remote-debugging-port` 被静默
覆盖（wry-0.55.1/src/webview2/mod.rs:294-327），调试端口永不打开，
session 必然失败并报 `DevToolsActivePort file doesn't exist`。

## 跑之前

日常请直接用仓库根的 `pnpm e2e`（内部会重编译）。若只想单独编产物：

```bash
pnpm --filter @v2/e2e build:web   # 前端 → apps/web/dist
pnpm --filter @v2/e2e build:app   # 壳（默认写到 target-e2e，见 scripts/run.mjs）
```

**改前端 / Rust 后不必再记两步**——`pnpm e2e` 每次都会重编。

### 壳被 dev 会话占用时（重要）

`pnpm tauri dev` 起的那个进程会把 `target/debug/client.exe` **一直占着**，于是
`build:app` 会在链接阶段失败：

```
LINK : fatal error LNK1104: 无法打开文件 "...\target\debug\deps\client.exe"
```

两个选择：停掉 dev 会话，或者**另建一个 target 目录**（不必打断 dev）：

```bash
CARGO_TARGET_DIR=target-e2e cargo build -p client --features e2e
DINGDA_E2E_APP_BINARY=target-e2e/debug/client.exe pnpm --filter @v2/e2e test
```

`DINGDA_E2E_APP_BINARY` 相对路径按仓库根解析（`wdio.conf.ts` 的
`resolveAppBinary()` 与 `scripts/require-artifacts.mjs` 读的是同一个变量）。
换目录是安全的：壳的仓库根来自编译期 `CARGO_MANIFEST_DIR`
（`packages-rs/client/src/lib.rs`），与 target 目录无关，照样能找到 `packages-py/`
并拉起 Server。代价是首次要在新目录里全量重编译一遍。

### `build:app` 会改到已提交的生成文件（提交前必看）

带 `--features e2e` 构建时，`tauri_build::build()` 会把 e2e 专用插件
`tauri-plugin-wdio-webdriver` 的权限写进 **已提交** 的生成 schema：

```
packages-rs/client/gen/schemas/acl-manifests.json     # 多出 "wdio-webdriver": {...}
packages-rs/client/gen/schemas/desktop-schema.json    # 权限枚举多出 "wdio-webdriver:default"
packages-rs/client/gen/schemas/windows-schema.json
```

运行时无影响（没有任何 capability 真的授予它），但**别把这三处带进提交** ——
它们由每次构建重生成，带不带 `e2e` 会来回翻转。提交前：

```bash
git checkout -- packages-rs/client/gen/schemas/
```

（本次就是先跑了 e2e 构建，发现这三处被改动后还原的。）

驱动侧**无需准备** —— embedded 模式不依赖 tauri-driver，也不需要 msedgedriver。
（`.drivers/` 里若还留着 msedgedriver，是早先 external 模式的产物，可忽略。）

### 为什么窗口会白屏（重要）

**debug 壳走 `devUrl`（`http://localhost:1420`），不是 `frontendDist`。**
`cargo build` 产出的壳里 `cfg!(dev) == true`（由 `tauri_build::build()` 设置），
于是 Tauri 去拉 `devUrl`。1420 上没人应答时的表现是：

- 窗口能起来，但**页面全白**
- 前端 JS 从未执行，于是不会调 `/v1/bootstrap`
- Server 的 `phase` 永远停在 `shell`，看着像"后端没预热"，其实是前端没加载

测试期间由 `onPrepare` 自动起静态服务顶上。日常开发请用 `pnpm tauri dev`
（自带 Vite dev server）—— 直接跑 `target/debug/client.exe` 必然白屏。

## 跑

仓库根一条命令（**每次先重编译**前端 + 带 `--features e2e` 的壳，再跑 wdio）：

```bash
pnpm e2e                    # 全部 spec
pnpm e2e:codex              # 只跑 Codex 找商品（商品 + 直播流 + 中文）
pnpm e2e -- --spec ./specs/desktop-smoke.spec.ts
```

默认壳产物落到 `target-e2e/debug/client`，避开 `pnpm tauri dev` 锁住的
`target/debug/client.exe`。等价于：

```bash
pnpm --filter @v2/e2e e2e
# = build:web + build:app + wdio
```

只要跑、不编译：`DINGDA_E2E_SKIP_BUILD=1 pnpm e2e -- --spec …`  
或 `pnpm --filter @v2/e2e test:only -- --spec …`。

调试驱动日志：`pnpm --filter @v2/e2e test:debug`  
只做类型检查：`pnpm --filter @v2/e2e typecheck`

> `typecheck` 走的是 `e2e/tsconfig.json`。注意**仓库根的 `tsc` 不覆盖本目录**
> （根 `tsconfig.json` 的 `include` 只有 `apps` 与 `packages`），所以改动本目录的
> TS 后请单独跑一次 `typecheck`，否则类型错误不会有人发现。

**本层是本地手动测试，不挂 CI**（`.github/workflows/desktop-release.yml` 只做
tag + 打包发布，不跑 e2e）。原因：embedded 模式依赖真实 WebView2 运行时，且冷缓存
首跑要 `uv sync --frozen`，在 runner 上代价与不稳定度都偏高。请勿往 CI 里加。

A 路单测（不启 WebView，3 秒）：

```bash
cargo test -p python
```

## 端口纪律（重要）

`PythonLifecycle::start_background` 会**主动 kill 掉自己端口上的既有监听进程**。
所以 E2E 强制用 `8799`（见 `wdio.conf.ts` 顶层的 `DINGDA_PORT` 注入），
绝不碰开发默认的 `8787` —— 否则跑一次测试就会杀掉你正在用的 dev server。

桌面模式的前端经 IPC 拿 `apiBaseUrl`，会自动跟上新端口，前端无需改。

要临时换端口：`DINGDA_E2E_PORT=8801 pnpm --filter @v2/e2e test`。

## 断言锚点

用例只依赖两个稳定锚点，不碰 CSS 类名和文案：

| 锚点 | 来源 | 含义 |
|---|---|---|
| `#boot-splash` | `apps/web/index.html` 内联 | 存在 = 启动中；被 `remove()` = 已放行 |
| `[data-testid="home-hero"]` | `packages/client/ui-home/home-hero.tsx` | 首页已渲染 |

`#boot-splash` 消失是**壳层装配成功的最强单一信号**：它同时要求
`server-ready` 事件链走通、`BootGate` 放行、首页预载完成。

## 覆盖边界

两层，各自回答一个问题：

**`specs/desktop-smoke.spec.ts` —— 壳层装配是否正确：**

- ✅ 壳能启动、窗口能开、标题正确
- ✅ 能连上 Python Server，且端口隔离生效
- ✅ IPC `get_server_status` 可达且返回 ready
- ✅ 启动屏放行、首页渲染

> 该 spec 会先把「在首页」变成显式前置（不在首页就点侧栏「首页」归位），
> 因为 URL 会跨应用实例残留 —— 见「已知坑」第 3 条。

**`specs/account-qr.spec.ts` —— 账号登录链路是否可用：**

- ✅ 查账号：缺号或登录态过期（`auth_valid=false`）时自动转入扫码
- ✅ 点页面按钮走完扫码：进账号页 → 选平台页签 → 点「重新扫码」/「扫码登录」
- ✅ 二维码真的渲染出来（`img[alt="登录二维码"]`），并导出 PNG 到 `artifacts/`
- ✅ 阻塞等待扫码完成，成功后独立校验账号已变为有效

驱动原则：**全程点页面按钮**，不直接打 `/v1/channel/qr/*` 推进流程。测试进程只做
「扫码前读账号、扫码后验账号」这两件旁证的事。选择器一律用源码里写死的
`data-slot` 与 `alt`，不碰 CSS 类名和文案。

时间预算：闲鱼二维码只有约 **120 秒**（后端 `deadline = timeout`，
`_PLATFORM_TIMEOUT["xianyu"] = 120`），超时后还会转一次风控恢复。所以扫码前请先
把手机和对应 App 准备好。

**`specs/ai-product-search.spec.ts` —— AI 找商品（业务链路）：**

- ✅ 首页用 opencode 发一句「去找商品」→ 跳工作页自动开跑 → 右侧「爬取结果」出商品
- ✅ 全程点页面控件（Agent 下拉 → 输入框 → 发送），**不直接打 `/v1/agent/runtimes/{id}/run`**
- ✅ 跑完用 `GET /v1/agent/works/{work_id}` 独立取证：落库 `products.total` 与页面一致
- ✅ 断言「确实是用目标 Agent 跑的」（`composer_agent_id` 等于 opencode）

驱动原则同 agent-runtimes：测试进程只做旁证。**不写用户偏好**（首页选 Agent 只改组件
内 state，不碰 `app_settings`），但**会新增一条 AI 工作记录**（`work-<时间戳>` 写进
`~/.dingda/v2/dingda.db`，后端无删除接口，不清理，会出现在「最近项目」）。

时间预算：真实找商品 = opencode 调 `dingda-crawl` skill 起浏览器爬平台，skill 文档写明
单次 1~5 分钟，一轮常见 3~10 分钟。所以等运行结束默认给 600s（环境变量
`DINGDA_E2E_RUN_TIMEOUT_MS`），且 `wdio.conf.ts` 的 `mochaOpts.timeout` 已抬到 920s 覆盖它。
干跑只验「发得出去、跑起来了、取消得掉」，不等结果：

```bash
DINGDA_E2E_SEARCH_DRY_RUN=1 pnpm e2e -- --spec ./specs/ai-product-search.spec.ts
```

可选环境变量：`DINGDA_E2E_AGENT_ID`（默认 `opencode`）、`DINGDA_E2E_MODEL_ID`（默认沿用该
Agent 的首选模型，即用户偏好）、`DINGDA_E2E_PROMPT`（默认闲鱼搜露营椅，并限定只调一次
search、不补详情、不比价）、`DINGDA_E2E_MIN_PRODUCTS`（默认 1）。

**跑之前先看模型**：这条用例的成败首先取决于模型上下文，不是用例写得对不对。找商品要先
读 4 个 skill 正文再叠多轮工具结果，实测约需 66k tokens；免费小模型（如
`openrouter/liquid/lfm-2.5-2.6b:free`，上限 65536）会直接报 context length 超限、
`exitCode=1`。用 `DINGDA_E2E_MODEL_ID` 显式指定一个上下文足够的模型；不指定时会沿用
`app_settings` 里的用户偏好，同一用例在不同机器上结论可能不同。

**`specs/ai-codex-product.spec.ts` —— Codex 找商品（业务链路 + 直播流 + 步骤块 + 中文）：**

- ✅ 首页选 **Codex** → 发一句「闲鱼搜露营椅」→ 工作页跑完
- ✅ 断言：真的调过工具、至少一步是搜索类（不是只聊天）
- ✅ 断言**工具身份被还原**：步骤块标题出现「搜索商品 / 查看商品详情 / 连贯浏览 /
  预览网页 / 扫码登录 / 比价找同款」这类面向用户的动作文案，而不是清一色「执行操作」。
  注意直播帧**不许**把它覆盖成页面标题（`ui-agent/run/reducer.ts` 的 `browserFrame` 分支
  曾经是 `label: page.title || prev.label`，正好把后端刚还原出来的标题抹掉）
- ✅ 断言**步骤块真的能折叠**：真实点标题栏，开合状态必须翻转，再点回来
- ✅ 断言**命令行块**：展开后读到 `tool <子命令> …` 形态的裸入口，
  且**不出现**解释器路径与 `run_tool.py` / `tools/cli`
- ✅ 断言**完整输出**：折叠区里最长的一段原始返回 > 200 字（不是被 hint 那样截到 160）
- ✅ 断言页面出现**直播流**（运行中采样 LIVE 徽标 / `data:image` 截图，
  跑完补采，再看落库 `browser_history` 里带 `screenshot_url` 的帧 —— 三取一）
- ✅ 断言**商品**：结果面板「共 N 条」≥ 阈值，且落库 `products.total` 对得上
- ✅ 断言**全程中文**：助手正文含中文且无超长英文串；思考块（展开后）有内容则必须中文
- ✅ 本机无 Codex 时跳过（不失败）

> 步骤块断言靠源码里写死的 `data-testid`：`step-block`（`blocks/step.tsx` 的 `Collapse`）、
> `step-terminal-command` / `step-terminal-output`。收起时正文被 `Collapse` 卸载，
> 所以命令行与输出**必须先真实点开再读** —— 这本身也是折叠是否生效的判据。

一轮真实抓商品常见 3~10 分钟。

```bash
pnpm e2e:codex

# 干跑：只验能选中 / 能开跑 / 能取消
DINGDA_E2E_CODEX_DRY_RUN=1 pnpm e2e:codex
```

可选：`DINGDA_E2E_MODEL_ID`（本机 Codex 若走自定义代理，请显式指定如
`deepseek-v4-flash`，否则可能落到未鉴权的 api.openai.com 报 401）、
`DINGDA_E2E_RUN_TIMEOUT_MS`（默认 600000）、`DINGDA_E2E_MIN_PRODUCTS`（默认 1）、
`DINGDA_E2E_AGENT_ID`（默认 `codex`）。

**`specs/agent-runtimes.spec.ts` —— Agent 检测与模型选择：**

- ✅ 点侧栏导航「Agent」进页面，页面「已检测到（N）」与 `GET /v1/agent/runtimes` 一致
- ✅ 点「扫描 Agent」跑完一次检测（含 PATH 探测 + 逐个深探测），结果与落库目录一致
- ✅ 在卡片「可用模型」下拉里切换模型，页面回显与 `GET /v1/agent/preferences`
  的 `default_models` 一致

**副作用约定（重要）**：该用例会写 `app_settings`。

- 「扫描 Agent」写 `agent_runtimes_catalog` —— 那是可重建的缓存，属按钮本职行为；
- 模型选择写 `default_models` —— **那是用户的真实偏好**。所以用例做**往返验证**：
  记下原值 → 换一个 → 校验 → 用 UI 改回原值再校验。还原放在 `finally`，
  中途断言失败也不会把偏好留在改动后的值上；UI 还原失败才用接口兜底并告警。
- 用例**不改**默认 Agent（那需要用户明确要求）。

**`scripts/e2e_orchestrate.py`（Python，不启 WebView）—— CLI 主编排器握手：**

- ✅ 角色面：parent 只编排 / worker 只取证 / child 无人设
- ✅ 工具注册：`child_run|resume|cancel|status` + `repair_dom`
- ✅ RepairOwner：默认 escalate，`crawler` 才内联
- ✅ 握手：`child_run` → `needs_repair` → `repair_dom` → `child_resume` → `completed`
- ✅ Store / live `agentPhase` / `child_cancel`

不启真实 Codex/爬虫（假 `run_cli` + 假 `run_product`）。跑：

```bash
pnpm --filter @v2/e2e e2e:orchestrate
# 或
uv run --directory packages-py/api python scripts/e2e_orchestrate.py
```

**不覆盖**（别往这里塞）：

- ❌ `PythonLifecycle` 的状态机与进程回收 → 归 A 路 `cargo test -p python`（已落地 6 条）
- ❌ 选品 / 爬虫等其它业务功能 → 归 L2/L3，见仓库根 `AGENTS.md`
- ❌ 托盘交互 → WebDriver 驱动不了系统托盘
- ❌ 真实风控下的长期稳定性（只能验一次真实的扫码登录）

## 已知坑

0. **`tauri-service` 的「命令前自动聚焦」会让每个元素操作多花 5 秒**（踩得最狠的一个）。
   它的 `beforeCommand` 会对 `getTitle / $ / $$ / findElement(s) / elementClick` 先跑
   `ensureActiveWindowFocus`，而本机环境里 `getWindowStates` 每次都失败并**等满 5 秒**：

   ```
   WARN tauri-service:window: Failed to get window states:
     Error: Tauri core.invoke not available after 5s timeout
   ```

   后果：`account-qr` 的二维码等待被拖到十几分钟也结束不了（元素查询根本走不完）。
   **解法**：调一次 `browser.tauri.switchWindow("main")` —— 它会先置上
   `suppressActiveWindowFocus`，之后自动聚焦全部跳过；另外 `browser.execute`
   **不在** focusCommands 列表里，所以高频轮询一律走 `execute`。
   见 `specs/account-qr.spec.ts` 的 `disableAutoFocus()` 与文件头说明。
1. **首次运行慢**：冷缓存下壳会跑 `uv sync --frozen`，已把 `startTimeout` 放宽到 120s。
2. **`taskkill` 可能被拦**：本机安全策略曾拦 `reg.exe` / `wmic.exe`。若 `stop` 失败，
   看 `afterSession` 的告警输出。日志里出现「PROGRAM BLOCKED BY SECURITY POLICY」
   就是它；该提示**出现在用例跑完之后时不影响结果**，但会污染退出码。
3. **URL（含 hash）会跨应用实例残留** —— 本层每个 spec 文件都会拉起**新的**应用实例，
   但新实例会恢复上一个实例的 URL。实测：跟在 `agent-runtimes` 后面跑时，`desktop-smoke`
   的实例起来就是 `#/agents`，于是首页的 `home-hero` 必然不存在（它是无条件渲染的）。
   **不是应用层持久化** —— 全仓库没有任何 `localStorage` 用法，是 WebView2 用户数据目录
   恢复了上次 URL。影响：**任何依赖「初始路由」的用例都会变成顺序相关的偶发失败**。
   解法：`desktop-smoke` 现在会先读 hash，不在首页就点侧栏「首页」归位（真实点击）再断言。
   新增 spec 时请同样把「起始路由」当成显式前置，别默认应用会停在首页。

4. **用 `browser.execute` 打临时标记定位元素时，每次都要先清标记**（踩过一次，静默通过）。
   下拉的内容容器**不随收起而卸载**，上一轮标记过的旧元素还在 DOM 里；若沿用同一个
   属性名又不清理，`$('[data-e2e-item]')` 按文档顺序会命中**旧元素** —— 点了等于没点。
   同理：别用「等下拉收起」判断选中成功（实测点完并不必然收起），要等**触发器文案变化**。
   见 `specs/agent-runtimes.spec.ts` 的 `clearMarker()` / `pickModel()`。
5. **模型下拉的触发器曾显示 `model.id` 而不是 `model.label`**（已修，2026-09-14）。
   症状：选完「Claude Sonnet 4.6」触发器却显示 `claude-sonnet-4-6`。
   根因：`ui-primitives/select.tsx` 的 `Select` 就是 base-ui 的 `Select.Root` 直接再导出，
   没传 `items`，于是 `Select.Value` 回落成原始 value。
   修法：在调用点 `agent-runtime-card.tsx` 给 `Select` 传
   `items={models.map((m) => ({ value: m.id, label: m.label }))}`
   （base-ui 文档：指定 `items` 后 `<Select.Value>` 渲染选中项的 label）。
   注意 **claude / codex 的 label ≠ id**，所以只有它们暴露了这个问题；opencode 两者相同。
   用例按现状断言「id 或 label 皆可」，不锁死实现。
6. **`raiseWindow()` 目前不起作用**：调 Tauri window 插件命令会被拒（壳没开
   `core:window:allow-{unminimize,show,set-focus}`）。窗口可见性靠系统对新窗口的默认置前。
7. **CI 上 Edge 版本落后**：仅当切回 external 模式才相关 —— GitHub Actions runner
   需先 `choco upgrade microsoft-edge -y`。当前 embedded 模式不读 Edge，且本层
   未挂 CI（本地手动跑）。
8. **`msedgedriver` 版本不匹配**：同上，仅 external 模式相关。多半是 PATH 里有另一个
   旧驱动，用 `where msedgedriver.exe` 查顺序。
