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

产物由两条独立命令构建，缺任何一个都会以难定位的方式失败
（`pretest` 会先检查并直接告诉你跑哪条）：

```bash
pnpm --filter @v2/e2e build:web   # 前端 → apps/web/dist
pnpm --filter @v2/e2e build:app   # 壳   → target/debug/client（= cargo build -p client --features e2e）
```

**改前端后必须重跑 `build:web`。**
**改 Rust 后必须重跑 `build:app`，且不能省 `--features e2e`。**

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

```bash
pnpm --filter @v2/e2e test          # 冒烟
pnpm --filter @v2/e2e test:debug    # 带驱动调试日志
```

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

这一层只回答「壳层装配是否正确」：

- ✅ 壳能启动、窗口能开、标题正确
- ✅ 能连上 Python Server，且端口隔离生效
- ✅ IPC `get_server_status` 可达且返回 ready
- ✅ 启动屏放行、首页渲染

**不覆盖**（别往这里塞）：

- ❌ `PythonLifecycle` 的状态机与进程回收 → 归 A 路 `cargo test -p python`（已落地 6 条）
- ❌ 业务功能（选品、爬虫、账号） → 归 L2/L3，见仓库根 `AGENTS.md`
- ❌ 托盘交互 → WebDriver 驱动不了系统托盘

## 已知坑

1. **首次运行慢**：冷缓存下壳会跑 `uv sync --frozen`，已把 `startTimeout` 放宽到 120s。
2. **`taskkill` 可能被拦**：本机安全策略曾拦 `reg.exe` / `wmic.exe`。若 `stop` 失败，
   看 `afterSession` 的告警输出。
3. **CI 上 Edge 版本落后**：GitHub Actions runner 需先 `choco upgrade microsoft-edge -y`。
4. **`msedgedriver` 版本不匹配**：多半是 PATH 里有另一个旧驱动，用 `where msedgedriver.exe` 查顺序。
