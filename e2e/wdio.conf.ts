/**
 * DingDa 桌面端 E2E 配置（WebdriverIO + 应用内嵌 WebDriver）。
 *
 * 被测对象：`target/debug/client`（Tauri 壳），它会自己拉起 Python Server。
 *
 * 驱动方式：`driverProvider: 'embedded'` —— 应用在进程内跑一个 W3C WebDriver
 * 服务，不需要 tauri-driver、不需要 msedgedriver，也不依赖 WebView2 的远程调试
 * 端口。代价是 Rust 侧要引入 `tauri-plugin-wdio-webdriver`；已用 Cargo feature
 * `e2e` 隔离（见 packages-rs/client/Cargo.toml），release 与日常 dev 构建都不含
 * 该插件，生产二进制不受影响。
 *
 * 注意是 **feature 而非 `#[cfg(debug_assertions)]`**：Cargo 的 target 段不支持
 * `debug_assertions`，写了会被忽略并报 warning，依赖照样进 release。故壳必须用
 * `cargo build -p client --features e2e` 构建，否则壳里没有 WebDriver 服务，
 * session 创建必然失败。
 *
 * 原先用 external 走 tauri-driver，但那条路在 Windows 上是死的：
 *   wry 在 `additional_browser_args` 为 None 时会自行构造默认值并调用
 *   `set_additional_browser_arguments()`；而 WebView2 的该属性**优先级高于环境变量**，
 *   于是 tauri-driver 注入的 `--remote-debugging-port` 被静默覆盖
 *   （wry-0.55.1/src/webview2/mod.rs:294-327），调试端口永不打开，
 *   session 创建必然失败并报 `DevToolsActivePort file doesn't exist`。
 *   已实测：手动带该环境变量启动 app，指定端口确实不监听；而不带该变量时
 *   app 本身运行完全正常。
 *
 * `.drivers/` 里的 msedgedriver 仍保留，供将来切回 external 或手动调试时使用；
 * embedded 模式下它不参与。
 *
 * 端口纪律（**这条最重要**）：
 *   `PythonLifecycle::start_background` 会主动 kill 掉自己端口上的既有监听进程
 *   （见 `packages-rs/python/src/lifecycle.rs`）。若 E2E 沿用默认 8787，
 *   跑一次测试就会杀掉开发者正在用的 dev server。故此处强制注入独立端口。
 *   桌面模式的前端经 IPC 拿 `apiBaseUrl`，会自动跟上新端口，无需改前端。
 */
import path from "node:path";
import { fileURLToPath } from "node:url";

// `tauri:options` 不在 WebdriverIO 的标准 capability 里，上游把它定义在
// `TauriCapabilities`（@wdio/tauri-service 导出）上，**而不是**通过
// `declare global` 合并进 `WebdriverIO.Capabilities`。所以直接用对象字面量写
// capabilities 会报 TS2353（`"tauri:options"` does not exist in type
// `RequestedStandaloneCapabilities`）—— 这是上游的类型缺口，不是配置写错了。
// 按上游预期用法给数组加类型标注即可，编译后不残留任何运行时代码。
import type { TauriCapabilities } from "@wdio/tauri-service";

import { isPortListening } from "./helpers/desktop";
import { startStaticServer, type StaticServer } from "./helpers/static-server";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..");

/**
 * 读仓库根的 `.env`（总表见根目录 `.env.example`），用 Node 内置能力，不引依赖。
 *
 * **真实环境变量优先** —— 与 Python 侧 `core.config.load_env()` 同一语义，
 * 所以命令行上的临时覆盖（`DINGDA_E2E_PORT=8801 pnpm …`）依然有效。
 * `.env` 是本地文件、不存在属正常情况，静默跳过。
 *
 * 必须放在读取 `DINGDA_E2E_*` 之前，否则 `.env` 里的值赶不上。
 */
try {
  process.loadEnvFile(path.join(repoRoot, ".env"));
} catch {
  // 没有 .env：按环境变量与用例默认值走
}

/** 测试专用端口，与开发默认的 8787 严格分离。 */
const E2E_PORT = process.env.DINGDA_E2E_PORT ?? "8799";

// 桌面壳启动时读 DINGDA_PORT（PythonConfig::from_env），被拉起的 app 继承本进程环境。
// 必须在 config 被消费前写入，故放在模块顶层。
process.env.DINGDA_PORT = E2E_PORT;

// msedgedriver 前置到 PATH：embedded 模式用不到，但切回 external（tauri-driver）时
// 它会在 PATH 里找，找不到就直接退出（code 1），留着省得下次再踩。
const driversDir = path.join(here, ".drivers");
process.env.PATH = `${driversDir}${path.delimiter}${process.env.PATH ?? ""}`;

// debug 壳走 devUrl（http://localhost:1420）而非嵌入的 frontendDist，
// 故测试期间必须有人在该端口服务 `apps/web/dist`。详见 helpers/static-server.ts。
const FRONTEND_PORT = 1420;
const webDistDir = path.join(repoRoot, "apps", "web", "dist");

let frontendServer: StaticServer | null = null;

const binaryName = process.platform === "win32" ? "client.exe" : "client";

/**
 * 壳二进制路径。
 *
 * 默认 `<repo>/target/debug/client`（= `cargo build -p client --features e2e`）。
 *
 * 为什么要可配：`target/debug/client.exe` 会被**正在运行的 dev 会话**锁住
 * （`pnpm tauri dev` 起的那个进程），此时重链接会直接失败：
 *   LINK : fatal error LNK1104: 无法打开文件 "...\target\debug\deps\client.exe"
 * 不想打断 dev 会话时另建一个 target 目录即可 —— 仓库根的解析不受影响，因为壳的
 * repo_root 来自编译期 `CARGO_MANIFEST_DIR`（见 packages-rs/client/src/lib.rs），
 * 与 target 目录无关：
 *   CARGO_TARGET_DIR=target-e2e cargo build -p client --features e2e
 *   DINGDA_E2E_APP_BINARY=target-e2e/debug/client.exe pnpm --filter @v2/e2e test
 * 相对路径按仓库根解析。
 */
function resolveAppBinary(): string {
  const override = process.env.DINGDA_E2E_APP_BINARY?.trim();
  if (!override) return path.join(repoRoot, "target", "debug", binaryName);
  return path.isAbsolute(override) ? override : path.resolve(repoRoot, override);
}

const appBinary = resolveAppBinary();

// 显式标注为 TauriCapabilities[]（而非内联字面量）：标注后 capability 对象
// 先按 TauriCapabilities 校验（放行 `tauri:options`），再作为非新鲜值赋给
// config.capabilities，从而绕过对 RequestedStandaloneCapabilities 的
// 多余属性检查。用 `satisfies` 不够 —— 它保留字面量类型，赋值时仍会报错。
const capabilities: TauriCapabilities[] = [
  {
    browserName: "tauri",
    "tauri:options": {
      application: appBinary,
    },
  },
];

export const config: WebdriverIO.Config = {
  runner: "local",
  specs: ["./specs/**/*.spec.ts"],
  maxInstances: 1,

  capabilities,

  services: [
    [
      "@wdio/tauri-service",
      {
        driverProvider: "embedded",
        appBinaryPath: appBinary,
        // 内嵌 WebDriver 服务的监听端口（也可由 TAURI_WEBDRIVER_PORT 指定）。
        embeddedPort: 4445,
        // 首次运行可能触发 `uv sync --frozen`（冷缓存下较慢），给足余量。
        startTimeout: 120_000,
        commandTimeout: 30_000,
        // 壳层与前端日志进报告，失败时不必再翻文件。
        captureBackendLogs: true,
        captureFrontendLogs: true,
        backendLogLevel: "info",
        frontendLogLevel: "warn",
      },
    ],
  ],

  logLevel: "info",
  bail: 0,
  waitforTimeout: 15_000,
  connectionRetryTimeout: 120_000,
  connectionRetryCount: 3,

  framework: "mocha",
  mochaOpts: {
    ui: "bdd",
    // 单条用例上限。
    //
    // 180s 只够 desktop-smoke。account-qr 要等后端 120s 扫码窗口 + 超时后的风控
    // 恢复，实测被 180s 直接掐断（报 mocha "Timeout"）—— 且用例里写的
    // `this.timeout(400_000)` **不生效**：WDIO 的 testFrameworkFnWrapper 走自己的
    // 超时（@wdio/utils 的 testFrameworkFnWrapper），不读 mocha 的 this.timeout。
    // 所以只能在这里按最长的那条用例设。
    // desktop-smoke 不受影响：它的断言各自带 15s 级显式等待，不会因此变慢。
    //
    // 2026-09-14 新增 ai-product-search：真实的「一句话找商品」= opencode 调
    // dingda-crawl skill 起浏览器爬平台，skill 文档写明单次 1~5 分钟，叠加上下文与
    // 多轮工具后一轮常见 3~10 分钟。其等待上限由 `DINGDA_E2E_RUN_TIMEOUT_MS`
    // （默认 600_000）控制，故这里必须留足余量。
    //
    // 2026-09-15 ai-codex-product 改成**完整选品链路**（小红书看风向 + 闲鱼核供给，
    // 两次真实抓取 + 长思考），实测 8~15 分钟，等待上限 900_000
    // （`DINGDA_E2E_RUN_TIMEOUT_MS`），故这里再抬一档并留启动/收尾余量。
    // 注意改成更大值只会让「真卡死」的失败等得更久，不改正常用例的速度。
    timeout: 1_800_000,
  },

  reporters: ["spec"],

  /**
   * 起静态前端服务。必须早于壳启动 —— 壳一起来就去拉 devUrl，
   * 那时端口上没人应答就会白屏（见 helpers/static-server.ts 的说明）。
   */
  onPrepare: async () => {
    if (await isPortListening(FRONTEND_PORT)) {
      console.warn(
        `[e2e] 端口 ${FRONTEND_PORT} 已有服务，直接复用（可能你正开着 pnpm tauri dev）。` +
          "若非指向 apps/web/dist，页面内容可能与预期不符。",
      );
      return;
    }

    frontendServer = await startStaticServer(webDistDir, FRONTEND_PORT);
    console.log(`[e2e] 前端静态服务就绪：http://localhost:${FRONTEND_PORT} → ${webDistDir}`);
  },

  onComplete: async () => {
    if (frontendServer) {
      await frontendServer.close();
      frontendServer = null;
      console.log("[e2e] 前端静态服务已关闭。");
    }
  },

  /**
   * 只做诊断，不做判定。
   *
   * 本 hook 早于 tauri-service 在 `onComplete` 停止 app —— 日志里
   * "Stopping N embedded driver process(es)" 排在 afterSession **之后**。
   * 所以在这里查端口释放，等于在 app 还没被停时问"停了吗"，必然得到
   * "仍在监听"；轮询再久也没用。早先写成 warn，两次跑都是误报。
   *
   * 进程回收的确定性验证归 A 路：`cargo test -p python` 直接测
   * `PythonLifecycle::stop` 的进程树清理（`taskkill /PID /T /F` 是否漏杀孙进程）。
   */
  afterSession: async () => {
    const stillUp = await isPortListening(Number(E2E_PORT));
    console.log(
      `[e2e] session 结束时端口 ${E2E_PORT} ` +
        (stillUp ? "仍在监听（app 由 onComplete 停止，属预期）" : "已释放"),
    );
  },
};
