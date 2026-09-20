/**
 * Agent 消息块渲染 E2E（web 模式）：预置含全部块类型的落库快照 → 打开工作页 →
 * 逐块断言。与桌面壳无关：web 模式前端默认连 127.0.0.1:8787。
 *
 * 覆盖的块：
 *   - browser_crawl：浏览器直播/截图块（PagePreview）+ 商品条
 *   - login：扫码登录块（独立于直播页卡样式）
 *   - tool：普通工具块（终端折叠区）
 *   - child：子会话块（含收尾摘要）
 *
 * 注意：Collapse 收起时 body 不挂载（collapse.tsx 只在 open 时渲染 children），
 * 所以工具块 / 子会话块要先展开再断言。
 */
import { expect, test } from "@playwright/test";

const WORK_ID = "e2e-agent-blocks-seed";
const CRAWL_STEP_ID = "step-crawl-1";
const CRAWL_PAGE_TITLE = "闲鱼搜索 · 露营折叠桌";
const PRODUCT_TITLE = "折叠露营桌 便携铝合金";

/** 1×1 透明 PNG：只为让截图位有值，触发「有图」分支。 */
const PIXEL_PNG =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

const done = { state: "ready", label: "已完成", hint: null, badge_class: "" };

/** 预置快照：形状对齐 contracts/ai-work.ts 的 AgentWorkDetailView。 */
function seedDetail() {
  return {
    work_id: WORK_ID,
    can_send: true,
    status: done,
    products: {
      items: [
        {
          id: "item-1",
          title: PRODUCT_TITLE,
          price: "129",
          platform: "xianyu",
          crawled_at: new Date().toISOString(),
          step_id: CRAWL_STEP_ID,
          step_label: CRAWL_PAGE_TITLE,
        },
      ],
      total: 1,
      status: done,
    },
    browser_live: { frame_id: "frame-crawl-1", url: "https://www.goofish.com/search?q=露营" },
    browser_history: [
      {
        id: "frame-crawl-1",
        url: "https://www.goofish.com/search?q=露营",
        title: CRAWL_PAGE_TITLE,
        screenshot_url: PIXEL_PNG,
      },
    ],
    messages: [
      {
        id: "msg-user-1",
        role: "user",
        content: "帮我看看露营折叠桌",
        created_at: new Date().toISOString(),
      },
      {
        id: "msg-assistant-1",
        role: "assistant",
        content: "已经量完了，结论如下。",
        created_at: new Date().toISOString(),
        thinking_duration_sec: 3,
        steps: [
          {
            id: CRAWL_STEP_ID,
            label: CRAWL_PAGE_TITLE,
            hint: "正在打开页面…",
            kind: "browser_crawl",
            status: done,
            browser_frame_id: "frame-crawl-1",
            page: {
              url: "https://www.goofish.com/search?q=露营",
              title: CRAWL_PAGE_TITLE,
              focus_label: "正在打开页面…",
              loading: false,
              screenshot_url: PIXEL_PNG,
            },
          },
          {
            id: "step-login-1",
            label: "扫码登录 · 闲鱼",
            hint: "用 App 扫码登录",
            kind: "login",
            status: done,
            page: {
              url: "dingda://login/xianyu",
              title: "扫码登录 · 闲鱼",
              focus_label: "用 App 扫码登录",
              loading: false,
              screenshot_url: PIXEL_PNG,
            },
          },
          {
            id: "step-tool-1",
            label: "select_products",
            hint: "候选排名已出",
            kind: "tool",
            status: done,
            command: "select_products(keywords=[露营折叠桌])",
            output: '{"ok": true, "candidates": 3}',
          },
        ],
        timeline: [
          { kind: "step", id: CRAWL_STEP_ID },
          { kind: "step", id: "step-login-1" },
          { kind: "step", id: "step-tool-1" },
          { kind: "child", id: "child-crawler-1" },
        ],
        children: [
          {
            run_id: "child-crawler-1",
            role: "crawler",
            label: "爬虫",
            phase: "completed",
            status: done,
            step: null,
            steps: [],
            timeline: [],
            content: "拿到 30 条商品。",
            thinking: "",
            summary: "拿到 30 条商品。",
          },
        ],
      },
    ],
  };
}

/** 种子放进 Python 落库（PUT 与前端 flush 持久化同一个接口，幂等覆盖）。 */
test.beforeEach(async ({ request }) => {
  const response = await request.put(`http://127.0.0.1:8787/v1/agent/works/${WORK_ID}`, {
    data: { detail: seedDetail() },
  });
  expect(response.ok()).toBe(true);
});

test.beforeEach(async ({ page }) => {
  await page.goto(`/#/work/${WORK_ID}`);
  // 启动屏移除 = 壳层装配完成（web 模式下是 BootGate 放行）。
  await expect(page.locator("#boot-splash")).toHaveCount(0);
});

test("浏览器爬取块渲染：页面截图 + 关联商品条", async ({ page }) => {
  await expect(page.locator(`img[alt="${CRAWL_PAGE_TITLE}"]`)).toBeVisible();
  // 标题同时出现在结果面板里，收窄到爬虫步骤块内断言商品条。
  const crawlBlock = page
    .locator('[data-testid="step-block"]')
    .filter({ hasText: CRAWL_PAGE_TITLE });
  await expect(crawlBlock.getByText(PRODUCT_TITLE)).toBeVisible();
});

test("扫码登录块渲染：独立登录块 + 二维码图", async ({ page }) => {
  await expect(page.locator('[data-testid="login-block"]')).toBeVisible();
  await expect(page.locator('img[alt="登录二维码"]')).toBeVisible();
});

test("普通工具块渲染：终端折叠区", async ({ page }) => {
  const toolBlock = page
    .locator('[data-testid="step-block"]')
    .filter({ hasText: "select_products" });
  // 收起时 body 不挂载，先展开。
  await toolBlock.locator("summary").click();
  await expect(toolBlock.locator('[data-testid="step-terminal-command"]')).toBeVisible();
  await expect(toolBlock.locator('[data-testid="step-terminal-output"]')).toBeVisible();
});

test("子会话块渲染：收尾摘要", async ({ page }) => {
  const childBlock = page.locator('[data-testid="child-block"]');
  await childBlock.locator("summary").click();
  await expect(page.locator('[data-testid="child-summary"]')).toBeVisible();
});
