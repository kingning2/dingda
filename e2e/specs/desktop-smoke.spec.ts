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
 *     不依赖 CSS 类名或文案。
 */
import { $, browser, expect } from "@wdio/globals";

import { fetchHealth, isPortListening } from "../helpers/desktop";

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);
/** 开发默认端口：E2E 绝不能占用它。 */
const DEV_PORT = 8787;

type ServerStatus = { ready: boolean; apiBaseUrl: string };

describe("DingDa 桌面端冒烟", () => {
  it("窗口标题为 DingDa v2", async () => {
    await expect(browser).toHaveTitle("DingDa v2");
  });

  it("启动屏被移除，首页渲染完成", async () => {
    await expect($("#boot-splash")).not.toExist();
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
