/**
 * 选品全链路 E2E（真实 LLM + 真实爬虫，不起桌面壳）。
 *
 * 场景：扮演完全不懂电商的新手卖家，在首页输入「不知道卖什么」式的求助，
 * 验证整条链路真实跑通：登录门禁 → 主编排识别选品意图 → select_products
 * （搜索 + 详情 + 确定性打分）→ 右侧「选品候选排名」面板出候选表。
 *
 * 这是真跑：单轮选品预算 900s（见 agent/tools/select.py），主编排按规则至少
 * 两轮量选，加上思考与登录门禁，整体给 30 分钟。视频全程录制。
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const NOVICE_PROMPT = "我是新手小白，第一次在网上卖东西，完全不知道该卖什么，帮我选个品吧";
/** 选品候选排名面板标题（ui-ai/panel/selection-results.tsx 写死）。 */
const PANEL_HEADING = "选品候选排名";

test.setTimeout(30 * 60_000);

interface WorkSummary {
  work_id: string;
}

interface WorkDetail {
  status?: { state?: string };
  selection?: { items?: unknown[] } | null;
}

/** 最新一条工作是否已经收尾（终态 + 选品面板有货）。 */
async function latestWorkSettled(
  request: APIRequestContext,
): Promise<{ workId: string; detail: WorkDetail } | null> {
  const list = await request.get("http://127.0.0.1:8787/v1/agent/works?limit=1");
  if (!list.ok()) return null;
  const payload = (await list.json()) as { items?: WorkSummary[] };
  const workId = payload.items?.[0]?.work_id;
  if (!workId) return null;

  const detailResp = await request.get(
    `http://127.0.0.1:8787/v1/agent/works/${encodeURIComponent(workId)}`,
  );
  if (!detailResp.ok()) return null;
  const detail = ((await detailResp.json()) as { detail?: WorkDetail }).detail;
  if (!detail) return null;
  const done = detail.status?.state === "ready";
  const hasCandidates = (detail.selection?.items?.length ?? 0) > 0;
  return done && hasCandidates ? { workId, detail } : null;
}

/** 把页面的运行状态打印到报告里，失败时好定位卡在哪一步。 */
async function dumpProgress(page: Page): Promise<void> {
  try {
    const text = await page.evaluate(() => document.body.innerText);
    process.stdout.write(`[select-e2e] 页面尾部：…${text.replace(/\s+/g, " ").slice(-260)}\n`);
  } catch (error) {
    process.stdout.write(`[select-e2e] 页面状态读取失败（不中断轮询）：${String(error)}\n`);
  }
}

test("小白求助选品：完整链路出候选排名", async ({ page, request }) => {
  await page.goto("/");
  // 首次启动会触发 Python 预热（浏览器池等），启动屏可能挂几十秒。
  await expect(page.locator("#boot-splash")).toHaveCount(0, { timeout: 60_000 });

  // 记住发送前最新的 work_id：判定「跑完」必须是**新** work，
  // 否则上一轮残留的完成快照会让轮询瞬间误报通过。
  const before = await latestWorkSettled(request);
  const baselineWorkId = before?.workId ?? "";

  const composer = page.locator('textarea[placeholder*="描述你"]');
  await composer.fill(NOVICE_PROMPT);
  await page.locator('button[aria-label="发送"]').click();

  // 轮询落库快照直到这轮收尾（选品本身有 300s 预算，LLM 派活还有额外开销）。
  let settled: { workId: string; detail: WorkDetail } | null = null;
  await expect
    .poll(
      async () => {
        settled = await latestWorkSettled(request);
        if (settled && settled.workId === baselineWorkId) {
          settled = null;
        }
        if (!settled) await dumpProgress(page);
        return settled;
      },
      { timeout: 25 * 60_000, intervals: [10_000, 30_000] },
    )
    .toBeTruthy();

  // 前端把候选排名渲染到右侧面板。
  await expect(page.getByRole("heading", { name: PANEL_HEADING })).toBeVisible();
  const detail = (settled as { detail: WorkDetail }).detail;
  expect(detail.selection?.items?.length ?? 0).toBeGreaterThan(0);
});
