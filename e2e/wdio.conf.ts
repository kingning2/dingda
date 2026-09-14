/**
 * DingDa 桌面端 E2E 配置（WebdriverIO + 应用内嵌 WebDriver）。
 *
 * 被测对象：`target/debug/client`（Tauri 壳），它会自己拉起 Python Server。
 *
 * 驱动方式：`driverProvider: 'embedded'` —— 应用在进程内跑一个 W3C WebDriver
 * 服务，不需要 tauri-driver、不需要 msedgedriver，也不依赖 WebView2 的远程调试
 * 端口。代价是 Rust 侧要引入 `tauri-plugin-wdio-webdriver`；已用
 * `#[cfg(debug_assertions)]` 隔离，release 构建不含该插件，生产二进制不受影响
 * （见 packages-rs/client）。
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

import { isPortListening } from "./helpers/desktop";
import { startStaticServer, type StaticServer } from "./helpers/static-server";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..");

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
const appBinary = path.join(repoRoot, "target", "debug", binaryName);

export const config: WebdriverIO.Config = {
  runner: "local",
  specs: ["./specs/**/*.spec.ts"],
  maxInstances: 1,

  capabilities: [
    {
      browserName: "tauri",
      "tauri:options": {
        application: appBinary,
      },
    },
  ],

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
    // 单条用例上限：要覆盖冷启动 + 预热，比默认 60s 放宽。
    timeout: 180_000,
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
