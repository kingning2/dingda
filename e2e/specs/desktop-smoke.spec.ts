/**
 * 桌面端冒烟：Tauri 壳能起来 → 连上 Python Server → 首页渲染完成。
 *
 * 这组用例刻意保持「少而稳」。它们要回答的是**壳层装配是否正确**，
 * 而不是业务功能是否正确 —— 后者属于 L2/L3（见 e2e/README.md）。
 *
 * 为什么断言点是这些：
 *   - `#boot-splash` 由 `apps/web/index.html` 内联，`BootGate` 放行后由
 *     `dismissBootSplash()` 真正 `remove()`。它消失 = `server-ready` 事件链走通
 *     **且** 首页预载完成。这是壳层装配成功的最强单一信号。
 *   - `[data-testid="home-hero"]` 是仓库里已有的稳定锚点（`ui-home/home-hero.tsx`），
 *     不依赖 CSS 类名或文案。它是**无条件渲染**的，所以「它不存在」等价于
 *     「当时不在首页路由」。
 *
 * ## 为什么本 spec 要先「归位到首页」
 * 本层每个 spec 文件都会拉起一个**新的**应用实例，但**URL（含 hash）会跨实例残留** ——
 * 实测跟在 `agent-runtimes` 后面跑时，本实例起来就是 `#/agents`（WebView2 用户数据目录
 * 恢复了上次的 URL，不是应用层持久化：全仓库没有任何 `localStorage` 用法）。
 * 于是 `home-hero` 必然不存在，而单独跑本 spec 时是通的。
 * 所以这里**显式**把「在首页」变成前置：不在首页就点侧栏「首页」归位（真实点击）。
 */
import { $, browser, expect } from "@wdio/globals";

import { fetchHealth, isPortListening } from "../helpers/desktop";
import { disableAutoFocus, findButtonByText, log, waitUntil } from "../helpers/ui";

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);
/** 开发默认端口：E2E 绝不能占用它。 */
const DEV_PORT = 8787;

const SCOPE = "smoke";

type ServerStatus = { ready: boolean; apiBaseUrl: string };

/** 当前路由 hash（空串与 `#/` 都算首页）。 */
function currentHash(): Promise<string> {
  return browser.execute(() => window.location.hash);
}

describe("DingDa 桌面端冒烟", () => {
  before(async () => {
    // 去掉 tauri-service 每个命令 5 秒的自动聚焦开销（见 helpers/ui.ts 的文件头）。
    await disableAutoFocus();
  });

  it("窗口标题为 DingDa v2", async () => {
    await expect(browser).toHaveTitle("DingDa v2");
  });

  it("启动屏被移除，首页渲染完成", async () => {
    await expect($("#boot-splash")).not.toExist();

    const hash = await currentHash();
    if (hash && hash !== "#/") {
      log(SCOPE, `进入时路由为 "${hash}"（上一个 spec 残留），点侧栏「首页」归位`);
      const home = await findButtonByText("首页", "exact");
      if (!home) throw new Error("侧栏里找不到「首页」导航项");
      await home.click();
      if (!(await waitUntil(async () => ["", "#/"].includes(await currentHash()), 10_000))) {
        throw new Error(`点「首页」后路由仍为 "${await currentHash()}"`);
      }
    } else {
      log(SCOPE, "进入时已在首页路由");
    }

    await expect($('[data-testid="home-hero"]')).toExist();
  });

  it("IPC get_server_status 返回 ready，且 apiBaseUrl 指向测试端口", async () => {
    const status = await browser.execute(async (): Promise<ServerStatus | null> => {
      const internals = (
        window as unknown as {
          __TAURI_INTERNALS__?: {
            invoke?: (cmd: string, args?: unknown) => Promise<unknown>;
          };
        }
      ).__TAURI_INTERNALS__;

      if (!internals?.invoke) return null;
      return (await internals.invoke("get_server_status", {})) as ServerStatus;
    });

    expect(status).not.toBeNull();
    expect(status?.ready).toBe(true);
    // 端口隔离生效的证据：壳层自报的地址必须带测试端口，而不是 8787。
    expect(status?.apiBaseUrl).toContain(String(E2E_PORT));
  });

  it("测试端口的 Server 健康检查通过", async () => {
    const health = await fetchHealth(E2E_PORT);

    expect(health).not.toBeNull();
    expect(health?.status).toBe("ok");
    expect(["shell", "warming", "ready"]).toContain(health?.phase);
  });

  it("Server 实际监听在测试端口", async () => {
    expect(await isPortListening(E2E_PORT)).toBe(true);

    // 8787 若被占用，说明本机另有 dev server 在跑。E2E 用独立端口，
    // 不受影响 —— 仅作诊断提示，不作为失败条件。
    if (await isPortListening(DEV_PORT)) {
      console.warn(
        `[e2e] 开发端口 ${DEV_PORT} 也有监听，可能有 dev server 在运行（本测试不受影响）。`,
      );
    }
  });
});
