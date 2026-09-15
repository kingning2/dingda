# packages

前端 pnpm 工作区。工作区根清单在仓库根 [`pnpm-workspace.yaml`](../pnpm-workspace.yaml)，
成员 = `packages/*` + `packages/*/*` + `apps/*`。

**一个包 = 一个业务域，或一层机制。** 名字必须能回答「这是干什么的」——
禁止 `packages/ui`、`packages/shared`、`packages/utils` 这类大杂烩命名。

```text
apps/web ─────────────────────────────────────┐
                                              ↓
ui-home · ui-ai · ui-composer · ui-account · ui-agent · ui-crawler · ui-monitor
                                              ↓
        ui-layout · ui-feedback ──→ ui-primitives ──→ ui-theme

叶子（谁都能引，自己不引业务包）：
  app-state   跨域共享 UI 状态（Agent 运行时 / 平台账号 / 最近会话）
  runtime     传输、能力开关、Server 状态、错误上报
  routes      路由契约（路径常量与解析）
  contracts   与 Python 的线协议类型
```

依赖单向：应用 → 业务域 → 骨架 → 底座 → 令牌/协议。任何一层都不反向依赖上层。
**叶子包不许引业务包** —— `runtime` 曾经引 `ui-crawler`，就是拆包后才暴露的方向反转。

## 成员包

| 包 | 职责 | 定位它 |
|----|------|--------|
| [contracts/](contracts/README.md) | 与 Python 的线协议类型（纯类型） | `server/` 改字段时同步 |
| [client/routes/](client/routes/README.md) | 路由契约：路径常量与解析 | 加页面时改 `paths.ts` |
| [client/app-state/](client/app-state/README.md) | 跨域共享 UI 状态（zustand） | 启动探测结果存哪 |
| [client/runtime/](client/runtime/README.md) | HTTP 传输、能力开关、Server 状态、错误上报、值类型判定 | 连不上 Server / 判断是否桌面端 / 判定外部数据字段类型 |
| [client/ui-theme/](client/ui-theme/README.md) | 设计令牌与全局样式 | 改颜色、圆角、字体 |
| [client/ui-primitives/](client/ui-primitives/README.md) | 无业务的原子组件 + `cn()` | 按钮/输入框长什么样 |
| [client/ui-layout/](client/ui-layout/README.md) | 外壳、标题栏、导航栏、主区域、路由出口 | 窗口骨架、侧栏、页面切换动效 |
| [client/ui-feedback/](client/ui-feedback/README.md) | 错误边界与告警宿主 | 报错怎么展示 |
| [client/ui-ai/](client/ui-ai/README.md) | AI 消息渲染、Markdown、思考过程 | 消息气泡、代码块 |
| [client/ui-composer/](client/ui-composer/README.md) | 输入区、附件、Agent 选择 | 打字框 |
| [client/ui-account/](client/ui-account/README.md) | 账号、扫码登录、登录态告警 | 账号相关 |
| [client/ui-agent/](client/ui-agent/README.md) | 外部 CLI Runtime 探测与运行态 | Agent 探测 |
| [client/ui-crawler/](client/ui-crawler/README.md) | 商品详情拉取与商品预览浮层 | 商品预览 |
| [client/ui-monitor/](client/ui-monitor/README.md) | 商品监控：监控列表、价格历史、变更事件 | 商品卖不卖得掉 / 有没有降价 |
| [client/ui-home/](client/ui-home/README.md) | 首屏、项目条、类型入口 | 首页 |

应用装配层在 [`apps/web/`](../apps/web/README.md)（Vite 根）。**启动编排**
（拉首页数据、卸启动屏）也在那里：`apps/web/src/boot/`。它要组合 Agent 域与账号域，
而两个域互不引用，所以只能待在装配层。

## 拆包暴露出的两条结构纪律

拆包之前这些问题是看不见的 —— 单棵源码树里「谁引谁」没有强制力。

1. **转发壳会把环藏起来。** `ui-agent/agent-runtime-scan.ts` 曾经整篇是
   `export { ... } from "@v2/ui-crawler/discovery-scan"`，于是依赖图看起来像
   `ui-agent → ui-crawler → ui-agent`。转发壳删掉、实现归位后环才消失。
   **不要为了「兼容旧 import」留转发文件**，直接改调用方。
2. **跨域状态要下沉成叶子包。** Agent / 账号 / 最近会话三份状态写在同一份 store 里，
   谁都来读。它一旦挂在某个业务包下（原先是 `ui-crawler`），那个包就被迫认识
   `ui-agent`、`ui-account`，环和反向依赖同时出现。状态本身不依赖业务逻辑，
   就该待在 `app-state` 这种只依赖 `contracts` 的叶子位置。
3. **包不许 import 应用源码。** `ui-layout` 曾经 `import { AnimatedOutlet }
   from "@web/routes/animated-outlet"` —— `@web/*` 是应用内部别名，这一行等于
   「包依赖应用」。依赖方向只能是应用 → 包，所以实现要挪进包
   （`AnimatedOutlet` 已归 `ui-layout`），或改为由应用注入（`setApiBaseUrl` /
   `setAppAlertNavigator` 那套）。这类越界靠人眼很难发现，因为**运行时完全正常**。

## 依赖卫生检查

上面三条纪律都有对应的自动检查，别靠自觉：

```bash
pnpm check:deps      # node scripts/check-workspace-deps.mjs
```

它扫 `src/**` 的 `.ts` / `.tsx` / `.css` 加包根 `*.config.*`，报五类问题：

| 类别 | 判定 | 后果 |
|------|------|------|
| 环 | `@v2/*` 之间成环 | 硬失败 |
| 跨层引用 | 包 import 了 `apps/**`（经 tsconfig `paths` 别名解析） | 硬失败 |
| 用了没声明 | 引了但 `package.json` 没写 | 硬失败 |
| 声明没用 | 写了但源码找不到（`peerDependencies` 豁免） | 警告 |
| 自依赖 | 包引自己 | 硬失败 |

已接进 `pnpm dev` 与 `pnpm build` 的**前置**，所以违规会在开发启动时就拦下来
（整轮约 0.3 秒）。退出码 0 = 通过，1 = 有硬失败项。

之所以必须自动化：这类违规的代价是**静默的**。靠根级 hoisting 兜着，本地能跑、
CI 能过，直到换个安装方式或挪个目录才炸。`ui-theme` 就是例子 —— 它的 `index.css`
`@import` 了四个外部包，包清单里却一个依赖都没写。

## 死代码检查

拆包之后「定义了但没人引用」也是静默问题：`tsconfig` 的 `noUnusedLocals` /
`noUnusedParameters` 只管**单文件内的局部变量**，跨文件的未使用导出、以及完全没人
import 的孤立文件，它看不见。

```bash
pnpm check:unused          # 默认只警告（退出码 0）
pnpm check:unused:strict   # 有发现就退出码 1，CI 用
```

它用 **TypeScript Compiler API** 做真正的引用分析，不是文本匹配 —— 正则/字符串计数
会把 `index.ts` 的 re-export 全部误判成死代码（实测正则法报 25.5%、真实值 0.2%，
高估约 100 倍）；re-export 链还须经 `getAliasedSymbol` 解析到原始符号才对得上号。

组件库（`ui-primitives`）与跨语言契约（`contracts`）天然有未使用导出，走脚本内的
`ALLOWLIST` 豁免。

**它分不清「死代码」与「预留件」。** 明确标注的预留件（已声明、故意未接线）不是死代码：
要么在文件里写清预留意图，要么加进 `ALLOWLIST`。反之，若某符号已被真实数据源取代
（如 mock 常量被 store 取代），那就是真死代码，应删掉而不是豁免。

已接进 `pnpm dev`（警告，不阻塞开发循环）与 `pnpm build`（`--strict`，拦住上线）；
`pnpm tauri dev` / `pnpm tauri build` 经 `tauri.conf.json` 的
`beforeDevCommand` / `beforeBuildCommand` 走同样两条链，因此一并覆盖。
临时跳过：`SKIP_UNUSED_CHECK=1 pnpm dev`。

## 测试

```bash
pnpm test         # vitest run（一次性）
pnpm test:watch   # 监听模式
```

**测试文件放包的 `tests/`，不放 `src/` 旁边。** 原因不是偏好：

- `vitest` 与 `typescript` / `vite` 同级，属**工作区级工具，只在根 `package.json` 声明**
- 而 `check:deps` 只扫 `src/**` 与包根 `*.config.*`

测试放进 `src/` 会让「用了没声明」硬失败，逼着每个包都声明 vitest。放 `tests/` 则
依赖关系清楚：**工具在根，测试在包的 `tests/`**。

配套约定：

- 测试由 vitest 按 glob 发现（`vitest.config.ts` 的 `include`），所以没人 import 它们 ——
  `check:unused` 已把 `*.test.ts` 排除出「孤立文件」；但它们**仍算消费方**，
  只被测试引用的导出不算死代码
- **不配 `resolve.alias`**：`@v2/*` 走 pnpm 工作区软链解析，与 `vite.config.ts`
  同一条约定（那里写了「加别名会掩盖工作区是否真的接通」）
- `environment: "node"`：目前测的都是纯函数。要测组件再按需换 jsdom

**为什么优先抽纯函数**：能脱离 React / DOM 的才测得了。`chat/schedule.ts`、
`agent-output.ts`、`runtime/guards.ts` 都是这个形状 —— 组件层只负责「把数据变成 DOM」。
这套测试第一次跑就抓到 `isArray` 的数组语义缺陷（商品 / 比价 / comments 会被静默清空），
而 `tsc`、`check:unused`、`check:deps` 三层门禁一个都没拦住。

## 工程机制

**源码直出**：每个包的 `exports` 直接指向 `./src/*`，不产出 `lib/`，全仓库仍是单次
Vite 构建。这样既有 pnpm 的真实包边界（依赖显式声明、越界可被发现），又没有多包构建
编排的成本。

```bash
pnpm dev          # → check:deps + check:unused（警告）+ pnpm --filter @v2/app-web dev
pnpm build        # → check:deps + check:unused --strict + tsc（全仓库类型检查）+ vite build
pnpm check:deps   # → node scripts/check-workspace-deps.mjs
pnpm check:unused # → node scripts/check-unused.mjs
```

## 新增一个包

1. 建 `packages/client/ui-<域>/`（`package.json` + `tsconfig.json` + `src/` + `README.md`）
2. `pnpm-workspace.yaml` 已用通配，无需登记
3. **三处必须同时改**，漏一处会在不同阶段炸：
   - 根 `package.json` 的 `dependencies` 加 `"@v2/ui-<域>": "workspace:*"`
   - 根 `tsconfig.json` 的 `paths` 加 `"@v2/ui-<域>"` 与 `"@v2/ui-<域>/*"` 两条
   - 跑一次 `pnpm install` 让 pnpm 建软链
4. 在本文件「成员包」表加一行
5. 跑 `pnpm check:deps` 确认没引入环 / 跨层引用 / 漏声明的依赖

## 改结构时的坑

1. **`pnpm-workspace.yaml` 不能写 `packages*`**（会匹配到 `packages-rs`，把 Rust 包当 JS 包扫）。
2. **`@v2/*` 不要加 Vite alias。** 必须走 pnpm 软链解析；加了别名会掩盖「工作区是否真接通」。
3. **Tailwind v4 要显式 `@source`。** 扫描范围写在 `ui-theme/src/index.css`，新增一级包目录
   要回去补一行 —— 漏了不报错，只会悄悄不生成那些类。
4. **不要用 `fs.rmSync(recursive)` 清理 `node_modules/@v2/*` 链接** —— 会穿过 junction
   删掉包的真实内容。只用 `fs.unlinkSync`。
5. **`public/` 必须跟着 Vite 根走。** `publicDir` 默认是 `<root>/public`。Vite 根一旦不是
   仓库根，留在仓库根的 `public/` 就彻底失效 —— **不报错**，只是所有 `/xxx` 形式的引用
   静默 404，构建产物里也一个图片都没有。本仓库的静态资源在 `apps/web/public/`。
6. **构建工具声明在使用它的包。** `vite` / `@vitejs/plugin-react` / `@tailwindcss/vite`
   声明在 `apps/web` 而非仓库根 —— 谁跑构建谁声明。同理 `ui-theme` 的 `index.css` 里
   `@import` 的外部包（`tw-animate-css` / `shadcn` / `@fontsource-variable/geist`）
   必须声明在 `ui-theme` 自己身上，别靠根级 hoisting 兜着。
7. **npm 脚本跟着 Vite 根走。** 应用是 Vite 根，`dev` / `build` / `preview` 就归它所有；
   仓库根只做转发。漏了会得到 `ERR_PNPM_RECURSIVE_RUN_NO_SCRIPT`。
